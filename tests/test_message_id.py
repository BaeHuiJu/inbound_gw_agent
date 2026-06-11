from datetime import datetime, timedelta, timezone

from inbound_gw_agent.utils.message_id import generate_message_id

KST = timezone(timedelta(hours=9))


def test_same_mail_from_graph_and_webhook_paths_yields_same_id():
    # Arrange — Graph API 수집 경로와 webhook 경로가 같은 메일을 전달
    received_at = datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)

    # Act
    graph_id = generate_message_id("user@company.com", received_at, "서버 오류")
    webhook_id = generate_message_id("user@company.com", received_at, "서버 오류")

    # Assert
    assert graph_id == webhook_id
    assert len(graph_id) == 32


def test_microsecond_difference_is_ignored():
    base = datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)
    with_micro = base.replace(microsecond=123456)

    assert generate_message_id("a@b.com", base, "제목") == generate_message_id(
        "a@b.com", with_micro, "제목"
    )


def test_same_instant_in_kst_and_utc_yields_same_id():
    utc_time = datetime(2026, 6, 11, 1, 0, 0, tzinfo=timezone.utc)
    kst_time = datetime(2026, 6, 11, 10, 0, 0, tzinfo=KST)  # 같은 순간

    assert generate_message_id("a@b.com", utc_time, "제목") == generate_message_id(
        "a@b.com", kst_time, "제목"
    )


def test_none_and_empty_subject_yield_same_id():
    received_at = datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)

    assert generate_message_id("a@b.com", received_at, None) == generate_message_id(
        "a@b.com", received_at, ""
    )


def test_none_and_empty_sender_yield_same_id():
    received_at = datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)

    assert generate_message_id(None, received_at, "제목") == generate_message_id(
        "", received_at, "제목"
    )


def test_different_inputs_yield_different_ids():
    received_at = datetime(2026, 6, 11, 10, 0, 0, tzinfo=timezone.utc)
    base_id = generate_message_id("a@b.com", received_at, "제목")

    assert base_id != generate_message_id("other@b.com", received_at, "제목")
    assert base_id != generate_message_id("a@b.com", received_at, "다른 제목")
    assert base_id != generate_message_id(
        "a@b.com", received_at + timedelta(seconds=1), "제목"
    )
