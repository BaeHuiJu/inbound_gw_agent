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

_DRAFT_REPLY_SYSTEM = """\
당신은 업무 이메일 답장을 대신 작성해 주는 AI입니다.
아래 수신 메일을 읽고, [USER_NAME] 본인이 보내는 답장 이메일 본문만 작성하세요.

규칙:
1. 첫 줄은 반드시 "안녕하세요. [USER_NAME]입니다." 로 시작합니다.
2. 수신 메일의 요청이나 질문에 직접 답변하세요. 받은 내용을 그대로 나열하거나 요약하지 마세요.
3. 일정을 언급할 때는 "빠른 시일 내", "추후" 같은 모호한 표현 대신 구체적인 기한을 사용하세요.
   확인이 필요해 기한을 모를 경우: "확인 후 회신드리겠습니다"로 열어 두세요.
4. 수신 메일이 영어인 경우, 영어로 답장하세요. 첫 줄은 "Hello, this is [USER_NAME]." 으로 시작합니다.
5. 한자나 중국어 문자는 절대 쓰지 마세요. 순한글과 영문만 사용하세요.
6. 답장 이메일 본문 외에 제목, 설명, 주석은 추가하지 마세요.
7. 마지막 줄은 "감사합니다." 다음 줄에 "[USER_NAME]" 으로 끝냅니다.

유형별 작성 방향:
- 요청 메일: 수락·일정 안내 / 부분 수락 시 가능 범위 명시 / 거절 시 사유 한 줄 + 대안 제시
- 질문 메일: 답을 알면 직접 답변 / 모르면 확인 후 회신 예정 안내
- 공지·공유 메일: 수신 확인 한 줄 + 필요시 후속 조치 한 줄
- 불만·긴급 메일: 첫 문장에 신속 대응 의지 표현 + 처리 기한 또는 담당자 안내

예시 (WBS 공유 요청 메일에 대한 답장):
안녕하세요. 홍길동입니다.

WBS 관련 문의 주셔서 감사합니다.
이번 주 금요일까지 최신본을 정리하여 공유드리겠습니다.
추가로 확인이 필요하신 사항이 있으시면 말씀해 주세요.

감사합니다.
홍길동
"""

_ERROR_ANALYZE_SYSTEM = """\
You are an IT error analysis expert. Analyze the email below and respond ONLY with valid JSON.
Do NOT include any explanation, markdown, or text outside the JSON object.
If the email is not an error notification, make your best guess based on available content.

Required JSON format (all fields mandatory):
{"system":"affected system or service name","occurred_at":"error time string or null","error_message":"one-line error summary","impact":"scope of impact","causes":[{"desc":"cause description","likelihood":"high|medium|low"}],"immediate_action":"immediate steps to take","prevention":"steps to prevent recurrence"}

Respond in Korean. Output the JSON object only.
"""


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
        self._cloud = ".atlassian.net" in (settings.jira_server or "").lower()

    def _user_ref(self, account_id: str) -> dict:
        """Cloud는 accountId, Server/DC는 name 필드로 사용자를 참조한다."""
        return {"accountId": account_id} if self._cloud else {"name": account_id}

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

        account_id = get_settings().jira_account_id.strip()
        if account_id:
            ref = self._user_ref(account_id)
            fields["assignee"] = ref
            fields["reporter"] = ref

        for attempt in ["full", "no_assignee"]:
            try:
                issue = await asyncio.to_thread(self._jira.create_issue, fields=fields)
                log.info("jira_ticket_created", key=issue.key, intent=intent.type.value)
                return issue.key
            except Exception as exc:
                if attempt == "full" and ("assignee" in fields or "reporter" in fields):
                    fields.pop("assignee", None)
                    fields.pop("reporter", None)
                else:
                    log.error("jira_ticket_failed", error=str(exc), msg_id=msg.id)
                    return None
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

    async def generate_draft_reply(self, msg: InboundMessage) -> str:
        settings = get_settings()
        user_display_name = settings.user_name or "담당자"
        system_prompt = _DRAFT_REPLY_SYSTEM.replace("[USER_NAME]", user_display_name)
        user_content = (
            f"발신자: {msg.sender}\n"
            f"제목: {msg.subject or '(없음)'}\n"
            f"본문:\n{msg.body[:2000]}"
        )
        try:
            response = await self._ollama.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            return response.message.content.strip()
        except Exception as exc:
            log.warning("draft_reply_failed", error=str(exc)[:120])
            return ""

    async def analyze_error(self, msg: InboundMessage) -> dict:
        """오류 알림 메일에서 시스템·원인·조치 방법을 추출한다. 실패 시 빈값 dict 반환."""
        import json as _json
        import re as _re
        user_content = (
            f"발신자: {msg.sender}\n"
            f"제목: {msg.subject or '(없음)'}\n"
            f"본문:\n{msg.body[:3000]}"
        )
        raw = ""
        try:
            response = await self._ollama.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": _ERROR_ANALYZE_SYSTEM},
                    {"role": "user", "content": user_content},
                ],
            )
            raw = response.message.content.strip()

            # 방법 1: 직접 파싱
            try:
                return _json.loads(raw)
            except _json.JSONDecodeError:
                pass

            # 방법 2: 마크다운 코드 블록에서 추출
            if "```" in raw:
                for part in raw.split("```")[1::2]:
                    candidate = part.lstrip("json \n\r").strip()
                    try:
                        return _json.loads(candidate)
                    except _json.JSONDecodeError:
                        pass

            # 방법 3: 중괄호 범위로 JSON 객체 추출
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            if m:
                try:
                    return _json.loads(m.group())
                except _json.JSONDecodeError:
                    pass

            # 모든 파싱 실패 → raw 응답을 immediate_action에 담아 반환
            log.warning("error_analyze_no_json", raw=raw[:200])
            return {
                "system": msg.subject or "",
                "occurred_at": None,
                "error_message": "(LLM이 JSON을 반환하지 않았습니다)",
                "impact": "",
                "causes": [],
                "immediate_action": raw[:1000] if raw else "(응답 없음)",
                "prevention": "",
            }
        except Exception as exc:
            log.warning("error_analyze_failed", error=str(exc)[:120])
            return {
                "system": "",
                "occurred_at": None,
                "error_message": msg.subject or "",
                "impact": "",
                "causes": [],
                "immediate_action": raw[:500] if raw else "(LLM 호출 실패)",
                "prevention": "",
            }

    def _find_sprint_id(self, sprint_name: str) -> int | None:
        """프로젝트 보드에서 sprint_name과 일치하는 Sprint ID를 반환한다."""
        try:
            boards = self._jira.boards(projectKeyOrID=self._project)
            for board in boards:
                try:
                    sprints = self._jira.sprints(board.id, state="active,future")
                    for sprint in sprints:
                        if sprint.name == sprint_name:
                            return sprint.id
                except Exception:
                    continue
        except Exception as exc:
            log.warning("sprint_lookup_failed", error=str(exc)[:120])
        return None

    async def create_story(
        self,
        msg: InboundMessage,
        md: float,
        team: str,
        task_summary: str,
        labels: list[str] | None = None,
        due_date: str | None = None,
        start_date: str | None = None,
        priority: str | None = None,
        custom_title: str | None = None,
    ) -> str | None:
        """Jira Story 이슈를 생성하고 key를 반환한다."""
        settings = get_settings()
        md_str = str(int(md)) if md == int(md) else str(md)
        summary = custom_title if custom_title else f"[{team}] {task_summary} ({md_str} M/D)"
        sender_name = _extract_sender_name(msg.sender)
        user_name = settings.user_name or ""
        description = (
            f"요청자 : {sender_name}\n"
            f"요청 팀 : {team}\n\n"
            f"핵심 업무 : {task_summary}\n"
            f"예상 소요 : {md_str} M/D\n\n"
            f"담당자 : {user_name}\n"
            f"보고자 : {user_name}\n\n"
            f"[메일 본문]\n{msg.body}"
        )
        all_labels = [f"auto-{msg.source.value}", "story-from-mail"]
        if labels:
            all_labels.extend(labels)
        fields: dict = {
            "project": {"key": self._project},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Story"},
            "labels": all_labels,
        }

        if priority:
            fields["priority"] = {"name": priority}
        if due_date:
            fields["duedate"] = due_date
        if start_date:
            fields["customfield_10015"] = start_date

        # Epic 연결 (Classic 방식 먼저)
        epic_key = settings.jira_story_epic_key.strip()
        if epic_key:
            fields["customfield_10014"] = epic_key

        # Sprint 연결
        sprint_name = settings.jira_story_sprint_name.strip()
        if sprint_name:
            sprint_id = await asyncio.to_thread(self._find_sprint_id, sprint_name)
            if sprint_id:
                fields["customfield_10020"] = sprint_id
                log.info("sprint_resolved", sprint_id=sprint_id, sprint_name=sprint_name)
            else:
                log.warning("sprint_not_found", sprint_name=sprint_name)

        account_id = settings.jira_account_id.strip()
        if account_id:
            ref = self._user_ref(account_id)
            fields["assignee"] = ref
            fields["reporter"] = ref

        # 생성 시도 — 실패 시 필드 제거 후 재시도
        for attempt in ["full", "no_assignee", "nextgen_epic", "no_epic", "no_startdate"]:
            try:
                issue = await asyncio.to_thread(self._jira.create_issue, fields=fields)
                log.info("jira_story_created", key=issue.key, attempt=attempt)
                return issue.key
            except Exception as exc:
                err = str(exc)
                if attempt == "full" and ("assignee" in fields or "reporter" in fields):
                    fields.pop("assignee", None)
                    fields.pop("reporter", None)
                elif attempt == "no_assignee" and "customfield_10014" in fields:
                    # Classic Epic 실패 → Next-gen parent 방식 시도
                    fields.pop("customfield_10014")
                    if epic_key:
                        fields["parent"] = {"key": epic_key}
                elif attempt == "nextgen_epic":
                    # Epic 없이 시도
                    fields.pop("parent", None)
                elif attempt == "no_epic":
                    # start date 필드가 지원되지 않는 경우 제거 후 재시도
                    fields.pop("customfield_10015", None)
                else:
                    log.error("jira_story_failed", error=err[:200])
                    return None
        return None
