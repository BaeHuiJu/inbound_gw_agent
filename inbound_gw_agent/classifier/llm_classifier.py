from __future__ import annotations

import json
import re

import ollama
import structlog

from inbound_gw_agent.config import get_settings
from inbound_gw_agent.models.intent import ClassifiedIntent, IntentType
from inbound_gw_agent.models.message import InboundMessage

log = structlog.get_logger()

_SYSTEM_PROMPT_BASE = """\
당신은 업무 메시지 분류 AI입니다. 아래 두 가지를 함께 분석하여 JSON만 반환합니다.

[1단계] 메시지 종류 분류:
- urgent: 시스템 오류, 서비스 장애, 보안 이슈, 긴급 상황
- task: 특정 작업 처리 요청, 업무 의뢰, 수정/변경/추가 요청
- inquiry: 답변으로 해결되는 단순 문의, 질문, 정보 요청
- project: 신규 프로젝트 제안, 협업 요청, 기획 검토 의뢰
- info: 공지사항, 뉴스레터, 보고서, 일방적 정보 전달
- spam: 광고, 홍보, 수신거부 메시지
- unknown: 위 항목에 해당하지 않거나 판단 불가

[2단계] 개인 중요도 판단:
수신자: {user_name} ({user_email})
담당 업무/프로젝트 키워드: {user_keywords}
(키워드 매칭은 대소문자를 구분하지 않는다)

판단 기준:
1. 수신자가 직접 액션(답장, 처리, 결정)을 해야 하는가?
2. 담당 업무/프로젝트 키워드와 관련 있는가? (대소문자 무관)
3. 위 기준이 애매하면 본문 내용으로 종합 판단한다.

priority 기준:
- high: 즉시 처리 필요, 직접 액션 필수
- medium: 오늘 중 처리, 관련 업무
- low: 참조/FYI, 직접 처리 불필요

category 기준 (반드시 아래 4개 중 하나만 사용, 다른 값 절대 금지):
- "긴급처리": type=urgent이고 action_required=true인 경우
- "내업무": 수신자가 직접 답장·처리·결정해야 하는 업무
- "참조": 알아두어야 하지만 수신자가 직접 처리할 필요 없는 경우
- "무시": spam, 광고, 시스템 자동 알림, 수신자와 무관한 내용

반드시 아래 JSON 형식으로만 응답하세요 (설명 없음, category는 위 4개 중 하나만):
{{"type": "urgent|task|inquiry|project|info|spam|unknown", "confidence": 0.0, "summary": "한 줄", "mine": true, "priority": "high|medium|low", "action_required": true, "category": "긴급처리|내업무|참조|무시", "suggested_action": "할 일 또는 null"}}
"""

_SYSTEM_PROMPT_SIMPLE = """\
당신은 업무 메시지 분류 AI입니다. 수신된 메시지를 아래 7가지 중 하나로 분류하세요.

분류 기준:
- urgent: 시스템 오류, 서비스 장애, 보안 이슈, 긴급 상황
- task: 특정 작업 처리 요청, 업무 의뢰, 수정/변경/추가 요청
- inquiry: 답변으로 해결되는 단순 문의, 질문, 정보 요청
- project: 신규 프로젝트 제안, 협업 요청, 기획 검토 의뢰
- info: 공지사항, 뉴스레터, 보고서, 일방적 정보 전달
- spam: 광고, 홍보, 수신거부 메시지
- unknown: 위 항목에 해당하지 않거나 판단 불가

반드시 다음 JSON 형식으로만 응답하세요:
{"type": "urgent|task|inquiry|project|info|spam|unknown", "confidence": 0.0, "summary": "분류 근거 한 줄"}
"""

_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


class LLMClassifier:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = ollama.AsyncClient(host=settings.ollama_base_url)
        self._model = settings.ollama_model
        self._system_prompt = self._build_prompt(settings)
        self.has_personal_config = bool(
            settings.user_name or settings.user_email or settings.user_keywords
        )

    @staticmethod
    def _build_prompt(settings) -> str:
        if settings.user_name or settings.user_email or settings.user_keywords:
            # 키워드를 소문자로 정규화하여 대소문자 무관 매칭 유도
            raw_kw = settings.user_keywords or "없음"
            normalized_kw = ", ".join(k.strip().lower() for k in raw_kw.split(",") if k.strip()) or "없음"
            return _SYSTEM_PROMPT_BASE.format(
                user_name=settings.user_name or "미설정",
                user_email=settings.user_email or "미설정",
                user_keywords=normalized_kw,
            )
        return _SYSTEM_PROMPT_SIMPLE

    async def classify(self, msg: InboundMessage) -> ClassifiedIntent:
        user_content = (
            f"발신자: {msg.sender}\n"
            f"제목: {msg.subject or '(없음)'}\n"
            f"내용: {msg.body[:1000]}"
        )

        try:
            response = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": user_content},
                ],
            )
            return self._parse_response(response.message.content)
        except Exception as exc:
            log.warning("llm_classify_failed", error=str(exc))
            return ClassifiedIntent(type=IntentType.UNKNOWN, confidence=0.0, classifier="llm")

    @staticmethod
    def _parse_response(raw: str) -> ClassifiedIntent:
        match = _JSON_RE.search(raw)
        if not match:
            return ClassifiedIntent(type=IntentType.UNKNOWN, confidence=0.0, classifier="llm")
        try:
            data = json.loads(match.group())
            return ClassifiedIntent(
                type=IntentType(data.get("type", "unknown")),
                confidence=float(data.get("confidence", 0.5)),
                summary=data.get("summary"),
                classifier="llm",
                mine=data.get("mine"),
                personal_priority=data.get("priority"),
                action_required=data.get("action_required"),
                email_category=data.get("category"),
                suggested_action=data.get("suggested_action") if data.get("suggested_action") != "null" else None,
            )
        except (ValueError, KeyError):
            return ClassifiedIntent(type=IntentType.UNKNOWN, confidence=0.0, classifier="llm")
