from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class IntentType(str, Enum):
    URGENT = "urgent"
    TASK = "task"
    INQUIRY = "inquiry"
    PROJECT = "project"
    INFO = "info"
    SPAM = "spam"
    UNKNOWN = "unknown"


_PRIORITY: dict[IntentType, str | None] = {
    IntentType.URGENT: "P1",
    IntentType.TASK: "P2",
    IntentType.INQUIRY: "P3",
    IntentType.PROJECT: "P2",
    IntentType.INFO: "P4",
    IntentType.SPAM: None,
    IntentType.UNKNOWN: "P2",
}

_ACTION: dict[IntentType, str] = {
    IntentType.URGENT: "즉시 알림 + 티켓 생성",
    IntentType.TASK: "담당자 할당 + 기한 파악",
    IntentType.INQUIRY: "FAQ 자동 응답 시도",
    IntentType.PROJECT: "프로젝트 폴더 생성 + 담당자 알림",
    IntentType.INFO: "카테고리 태깅 + 아카이브",
    IntentType.SPAM: "자동 아카이브",
    IntentType.UNKNOWN: "사람에게 검토 요청",
}


class ClassifiedIntent(BaseModel):
    type: IntentType
    confidence: float
    summary: str | None = None
    classifier: str  # "rule" | "llm"
    keywords: list[str] = []
    fallback: bool = False
    # Personal email relevance (LLM combined classification)
    mine: bool | None = None
    personal_priority: str | None = None   # "high" | "medium" | "low"
    action_required: bool | None = None
    email_category: str | None = None      # "긴급처리" | "내업무" | "참조" | "무시"
    suggested_action: str | None = None

    @property
    def priority(self) -> str | None:
        return _PRIORITY[self.type]

    @property
    def action(self) -> str:
        return _ACTION[self.type]

    def to_result(self) -> dict:
        return {
            "category": self.type.value.upper(),
            "confidence": round(self.confidence, 2),
            "priority": self.priority,
            "action": self.action,
            "reason": self.summary or "",
            "fallback": self.fallback,
        }
