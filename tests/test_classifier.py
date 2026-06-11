import pytest

from inbound_gw_agent.classifier.rule_classifier import RuleClassifier
from inbound_gw_agent.models.intent import IntentType
from inbound_gw_agent.models.message import InboundMessage


@pytest.fixture
def classifier() -> RuleClassifier:
    return RuleClassifier()


def test_urgent_detected(classifier: RuleClassifier, outlook_msg: InboundMessage) -> None:
    intent = classifier.classify(outlook_msg)
    assert intent.type == IntentType.URGENT
    assert intent.confidence >= 0.8
    assert intent.classifier == "rule"


def test_inquiry_detected(classifier: RuleClassifier, teams_inquiry_msg: InboundMessage) -> None:
    intent = classifier.classify(teams_inquiry_msg)
    assert intent.type == IntentType.INQUIRY
    assert intent.confidence >= 0.75


def test_task_detected(classifier: RuleClassifier, task_msg: InboundMessage) -> None:
    intent = classifier.classify(task_msg)
    assert intent.type == IntentType.TASK
    assert intent.confidence >= 0.8


def _make_msg(body: str, subject: str | None = None, sender: str = "user@example.com") -> InboundMessage:
    from datetime import datetime, timezone
    from inbound_gw_agent.models.message import MessageSource

    return InboundMessage(
        id="tie-test",
        source=MessageSource.OUTLOOK,
        sender=sender,
        subject=subject,
        body=body,
        received_at=datetime.now(timezone.utc),
    )


def test_tie_urgent_beats_task(classifier: RuleClassifier) -> None:
    # URGENT(안 됩니다 0.9)와 TASK(처리해 0.9) 동점 → URGENT 우선
    intent = classifier.classify(_make_msg("결재 화면이 작동이 안 됩니다. 처리해 주세요."))
    assert intent.type == IntentType.URGENT


def test_tie_spam_beats_task(classifier: RuleClassifier) -> None:
    # SPAM(newsletter 0.9)과 TASK(부탁 0.9) 동점 → SPAM 우선 (광고가 티켓으로 새지 않도록)
    intent = classifier.classify(_make_msg("newsletter 구독 부탁드립니다."))
    assert intent.type == IntentType.SPAM


def test_automated_info_still_beats_task_by_weight(classifier: RuleClassifier) -> None:
    # 자동발송 메일은 INFO 가중치(0.95)가 TASK(0.9)보다 높아 동점이 아님 → INFO 유지
    intent = classifier.classify(_make_msg("티켓 처리해 주세요.", sender="jira@company.atlassian.net"))
    assert intent.type == IntentType.INFO


def test_unknown_for_unrelated_message(classifier: RuleClassifier) -> None:
    from datetime import datetime, timezone
    from inbound_gw_agent.models.message import MessageSource

    msg = InboundMessage(
        id="x",
        source=MessageSource.TEAMS,
        sender="bot",
        body="안녕하세요! 반갑습니다.",
        received_at=datetime.now(timezone.utc),
    )
    intent = classifier.classify(msg)
    assert intent.type == IntentType.UNKNOWN


def test_html_stripped_from_body() -> None:
    from datetime import datetime, timezone
    from inbound_gw_agent.models.message import MessageSource

    msg = InboundMessage(
        id="html-1",
        source=MessageSource.OUTLOOK,
        sender="x@x.com",
        body="<html><body><p>시스템 <b>오류</b> 발생!</p></body></html>",
        received_at=datetime.now(timezone.utc),
    )
    assert "<html>" not in msg.body
    assert "오류" in msg.body
