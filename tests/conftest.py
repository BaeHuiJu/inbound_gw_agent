from datetime import datetime, timezone

import pytest

from inbound_gw_agent.models.message import InboundMessage, MessageSource


@pytest.fixture
def outlook_msg() -> InboundMessage:
    return InboundMessage(
        id="test-outlook-001",
        source=MessageSource.OUTLOOK,
        sender="user@example.com",
        subject="시스템 오류 발생",
        body="오늘 오전부터 결재 시스템 접속이 안 됩니다. 빠른 조치 부탁드립니다.",
        received_at=datetime(2026, 5, 14, 9, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def teams_inquiry_msg() -> InboundMessage:
    return InboundMessage(
        id="test-teams-001",
        source=MessageSource.TEAMS,
        sender="홍길동",
        subject="일반 문의",
        body="연차 신청 방법이 어떻게 되나요? 알려주세요.",
        received_at=datetime(2026, 5, 14, 10, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def task_msg() -> InboundMessage:
    # "보고서"(INFO 0.9)와 "처리해"(TASK 0.9)가 동점인 문구 — tie-break로 TASK가 이겨야 함
    return InboundMessage(
        id="test-teams-002",
        source=MessageSource.TEAMS,
        sender="김철수",
        subject=None,
        body="보고서 양식 수정 작업 처리해 주세요.",
        received_at=datetime(2026, 5, 14, 11, 0, tzinfo=timezone.utc),
    )
