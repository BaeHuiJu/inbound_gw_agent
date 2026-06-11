from __future__ import annotations

import structlog

from inbound_gw_agent.classifier.llm_classifier import LLMClassifier
from inbound_gw_agent.classifier.rule_classifier import RuleClassifier
from inbound_gw_agent.config import get_settings
from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
from inbound_gw_agent.models.intent import ClassifiedIntent, IntentType
from inbound_gw_agent.models.message import InboundMessage
from inbound_gw_agent.state.store import StateStore

log = structlog.get_logger()


class Pipeline:
    def __init__(self) -> None:
        settings = get_settings()
        self._store = StateStore(settings.state_db_path)
        self._rule = RuleClassifier()
        self._llm = LLMClassifier()
        self._handler = JiraTicketHandler() if settings.jira_enabled else None
        self._threshold = settings.rule_confidence_threshold
        if settings.jira_enabled:
            log.info("jira_enabled", project=settings.jira_project_key)
        else:
            log.info("jira_disabled")

    async def process_message(self, msg: InboundMessage, classify_only: bool = False) -> None:
        received_at_str = msg.received_at.isoformat() if msg.received_at else None
        if self._store.is_processed(msg.id, received_at=received_at_str):
            log.debug("message_already_processed", id=msg.id[:8])
            return
        await self._process(msg, classify_only=classify_only)

    async def _process(self, msg: InboundMessage, classify_only: bool = False) -> None:
        intent = await self._classify(msg)
        log.info(
            "message_classified",
            id=msg.id[:8],
            source=msg.source.value,
            intent=intent.type.value,
            confidence=round(intent.confidence, 2),
            classifier=intent.classifier,
        )

        settings = get_settings()

        if intent.type == IntentType.URGENT and (
            settings.teams_alert_webhook_url or settings.slack_alert_webhook_url
        ):
            from inbound_gw_agent.handlers.alert_handler import send_urgent_alert
            await send_urgent_alert(
                sender=msg.sender or "",
                subject=msg.subject or "(제목 없음)",
                body_preview=msg.body or "",
                teams_url=settings.teams_alert_webhook_url,
                slack_url=settings.slack_alert_webhook_url,
            )

        jira_key: str | None = None
        _skip_jira = {IntentType.INFO, IntentType.SPAM, IntentType.UNKNOWN}
        if not classify_only and self._handler and intent.type not in _skip_jira and settings.jira_auto_create:
            jira_key = await self._handler.handle(msg, intent)

        self._store.mark_processed(
            message_id=msg.id,
            source=msg.source.value,
            intent_type=intent.type.value,
            jira_key=jira_key,
            sender=msg.sender,
            subject=msg.subject,
            received_at=msg.received_at.isoformat() if msg.received_at else None,
            mine=intent.mine,
            personal_priority=intent.personal_priority,
            action_required=intent.action_required,
            email_category=intent.email_category,
            suggested_action=intent.suggested_action,
            body=msg.body,
        )

    async def _classify(self, msg: InboundMessage) -> ClassifiedIntent:
        rule_intent = self._rule.classify(msg)

        if rule_intent.confidence >= self._threshold and self._llm.has_personal_config:
            # 규칙 분류기가 의도를 확정했더라도 개인 중요도는 LLM에서 가져온다
            # LLM 실패 시 None으로 덮어쓰지 않기 위해 None이 아닌 경우만 반영
            llm_intent = await self._llm.classify(msg)
            if llm_intent.mine is not None:
                rule_intent.mine = llm_intent.mine
            if llm_intent.personal_priority is not None:
                rule_intent.personal_priority = llm_intent.personal_priority
            if llm_intent.action_required is not None:
                rule_intent.action_required = llm_intent.action_required
            if llm_intent.email_category is not None:
                rule_intent.email_category = llm_intent.email_category
            if llm_intent.suggested_action is not None:
                rule_intent.suggested_action = llm_intent.suggested_action
            return rule_intent

        if rule_intent.confidence < self._threshold:
            intent = await self._llm.classify(msg)
            if intent.confidence < 0.7:
                return ClassifiedIntent(
                    type=IntentType.UNKNOWN,
                    confidence=intent.confidence,
                    classifier=intent.classifier,
                    fallback=True,
                    mine=intent.mine,
                    personal_priority=intent.personal_priority,
                    action_required=intent.action_required,
                    email_category=intent.email_category,
                    suggested_action=intent.suggested_action,
                )
            return intent

        return rule_intent

    def reload_llm(self) -> None:
        get_settings.cache_clear()
        self._llm = LLMClassifier()
        log.info("llm_reloaded", has_personal_config=self._llm.has_personal_config)

    def close(self) -> None:
        self._store.close()
