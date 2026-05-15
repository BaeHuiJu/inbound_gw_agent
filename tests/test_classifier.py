import pytest

from inbound_gw_agent.classifier.rule_classifier import RuleClassifier
from inbound_gw_agent.models.intent import IntentType
from inbound_gw_agent.models.message import InboundMessage


@pytest.fixture
def classifier() -> RuleClassifier:
    return RuleClassifier()


def test_incident_detected(classifier: RuleClassifier, outlook_msg: InboundMessage) -> None:
    intent = classifier.classify(outlook_msg)
    assert intent.type == IntentType.INCIDENT
    assert intent.confidence >= 0.8
    assert intent.classifier == "rule"


def test_inquiry_detected(classifier: RuleClassifier, teams_inquiry_msg: InboundMessage) -> None:
    intent = classifier.classify(teams_inquiry_msg)
    assert intent.type == IntentType.INQUIRY
    assert intent.confidence >= 0.75


def test_request_detected(classifier: RuleClassifier, request_msg: InboundMessage) -> None:
    intent = classifier.classify(request_msg)
    assert intent.type == IntentType.REQUEST
    assert intent.confidence >= 0.8


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
