from __future__ import annotations

import asyncio
import re

import ollama
import structlog
from jira import JIRA

from inbound_gw_agent.config import get_settings
from inbound_gw_agent.handlers.base import BaseHandler
from inbound_gw_agent.models.intent import ClassifiedIntent, IntentType
from inbound_gw_agent.models.message import InboundMessage

log = structlog.get_logger()

_ISSUE_TYPE: dict[IntentType, str] = {
    IntentType.URGENT: "Bug",
    IntentType.TASK: "Task",
    IntentType.INQUIRY: "Task",
    IntentType.PROJECT: "Task",
}

_JIRA_PRIORITY: dict[IntentType, str] = {
    IntentType.URGENT: "Highest",
    IntentType.TASK: "High",
    IntentType.INQUIRY: "Medium",
    IntentType.PROJECT: "High",
}

_SUMMARIZE_SYSTEM = """\
당신은 업무 메일 요약 AI입니다.
아래 이메일의 핵심 요청사항을 3~5줄로 요약하세요.
육하원칙(누가/언제/어디서/무엇을/어떻게/왜) 기준으로 명확하게 작성하세요.
요약문만 반환하세요 (다른 설명이나 제목 없이).
"""

_STORY_ANALYZE_SYSTEM = """\
당신은 업무 이메일 분석 AI입니다.
아래 이메일을 분석하여 다음 JSON 형식으로만 응답하세요:
{
  "team": "요청 팀 또는 부서명 (예: 그룹웨어팀, IT인프라팀, 인사팀)",
  "task_summary": "핵심 업무 한 줄 요약 (예: 전자결재 시스템 모바일 연동 개발)",
  "deadline_str": "기한 문자열 (예: 2026.06.30) 또는 null",
  "is_overdue": true 또는 false
}
JSON 외 다른 텍스트는 포함하지 마세요.
"""

_EMAIL_RE = re.compile(r"<(.+?)>")


def _extract_sender_name(sender: str) -> str:
    """'홍길동 <hong@mastern.co.kr>' → '홍길동', 'hong@mastern.co.kr' → 'hong'"""
    # "이름 <이메일>" 형식
    name_part = _EMAIL_RE.sub("", sender).strip().strip('"')
    if name_part:
        return name_part
    # 순수 이메일만 있는 경우
    if "@" in sender:
        return sender.split("@")[0]
    return sender


class JiraTicketHandler(BaseHandler):
    def __init__(self) -> None:
        settings = get_settings()
        self._jira = JIRA(
            server=settings.jira_server,
            basic_auth=(settings.jira_email, settings.jira_api_token),
        )
        self._project = settings.jira_project_key
        self._ollama = ollama.AsyncClient(host=settings.ollama_base_url)
        self._model = settings.ollama_model

    async def handle(self, msg: InboundMessage, intent: ClassifiedIntent) -> str | None:
        summary = intent.summary or (msg.subject or msg.body[:80])
        content_summary = await self._summarize(msg, intent)
        description = self._build_description(msg, content_summary)
        fields = {
            "project": {"key": self._project},
            "summary": summary,
            "description": description,
            "issuetype": {"name": _ISSUE_TYPE.get(intent.type, "Task")},
            "priority": {"name": _JIRA_PRIORITY.get(intent.type, "Medium")},
            "labels": [f"auto-{msg.source.value}", f"category-{intent.type.value}"],
        }

        try:
            issue = await asyncio.to_thread(self._jira.create_issue, fields=fields)
            log.info("jira_ticket_created", key=issue.key, intent=intent.type.value)
            return issue.key
        except Exception as exc:
            log.error("jira_ticket_failed", error=str(exc), msg_id=msg.id)
            return None

    async def _summarize(self, msg: InboundMessage, intent: ClassifiedIntent) -> str:
        user_content = (
            f"발신자: {msg.sender}\n"
            f"제목: {msg.subject or '(없음)'}\n"
            f"본문:\n{msg.body[:2000]}"
        )
        try:
            response = await self._ollama.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SUMMARIZE_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
            )
            return response.message.content.strip()
        except Exception as exc:
            log.warning("jira_summarize_failed", error=str(exc)[:120])
            return intent.summary or msg.subject or msg.body[:200]

    @staticmethod
    def _build_description(msg: InboundMessage, content_summary: str) -> str:
        sender_name = _extract_sender_name(msg.sender)
        return (
            f"요청자 : {sender_name}\n\n"
            f"내용 :\n{content_summary}\n\n"
            f"메일 내용 캡처 :\n{msg.body}"
        )

    async def analyze_for_story(self, msg: InboundMessage) -> dict:
        """메일에서 팀명·요약·기한을 추출한다. 실패 시 빈값 dict 반환."""
        import json as _json
        user_content = (
            f"발신자: {msg.sender}\n"
            f"제목: {msg.subject or '(없음)'}\n"
            f"본문:\n{msg.body[:3000]}"
        )
        try:
            response = await self._ollama.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": _STORY_ANALYZE_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[-2].lstrip("json").strip()
            return _json.loads(raw)
        except Exception as exc:
            log.warning("story_analyze_failed", error=str(exc)[:120])
            return {"team": "", "task_summary": msg.subject or "", "deadline_str": None, "is_overdue": False}

    async def create_story(self, msg: InboundMessage, md: float, team: str, task_summary: str) -> str | None:
        """Jira Story 이슈를 생성하고 key를 반환한다."""
        settings = get_settings()
        md_str = str(int(md)) if md == int(md) else str(md)
        summary = f"[{team}] {task_summary} ({md_str} M/D)"
        sender_name = _extract_sender_name(msg.sender)
        description = (
            f"요청자 : {sender_name}\n"
            f"요청 팀 : {team}\n\n"
            f"핵심 업무 : {task_summary}\n"
            f"예상 소요 : {md_str} M/D\n\n"
            f"[메일 본문]\n{msg.body}"
        )
        fields: dict = {
            "project": {"key": self._project},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Story"},
            "labels": [f"auto-{msg.source.value}", "story-from-mail"],
        }
        if settings.user_name:
            fields["assignee"] = {"name": settings.user_name}
        try:
            issue = await asyncio.to_thread(self._jira.create_issue, fields=fields)
            log.info("jira_story_created", key=issue.key)
            return issue.key
        except Exception as exc:
            if "assignee" in fields:
                fields.pop("assignee")
                try:
                    issue = await asyncio.to_thread(self._jira.create_issue, fields=fields)
                    log.info("jira_story_created_no_assignee", key=issue.key)
                    return issue.key
                except Exception as exc2:
                    log.error("jira_story_failed", error=str(exc2))
                    return None
            log.error("jira_story_failed", error=str(exc))
            return None
