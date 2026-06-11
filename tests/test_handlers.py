from unittest.mock import MagicMock, patch

import pytest

from inbound_gw_agent.models.intent import ClassifiedIntent, IntentType


def _mock_settings():
    settings = MagicMock()
    settings.jira_server = "https://test.atlassian.net"
    settings.jira_email = "test@test.com"
    settings.jira_api_token = "token"
    settings.jira_project_key = "PROJ"
    settings.jira_account_id = ""
    settings.user_name = "테스트유저"
    settings.ollama_base_url = "http://localhost:11434"
    settings.ollama_model = "llama3.2"
    return settings


def _make_handler(MockJira, mock_settings, issue_key="PROJ-42"):
    mock_settings.return_value = _mock_settings()
    mock_issue = MagicMock()
    mock_issue.key = issue_key
    MockJira.return_value.create_issue.return_value = mock_issue
    from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
    return JiraTicketHandler()


@pytest.mark.asyncio
async def test_jira_ticket_created(outlook_msg):
    with (
        patch("inbound_gw_agent.handlers.ticket_handler.JIRA") as MockJira,
        patch("inbound_gw_agent.handlers.ticket_handler.get_settings") as mock_settings,
        patch("inbound_gw_agent.handlers.ticket_handler.ollama"),
    ):
        handler = _make_handler(MockJira, mock_settings, "PROJ-42")
        intent = ClassifiedIntent(
            type=IntentType.URGENT,
            confidence=0.9,
            summary="결재 시스템 접속 불가 장애",
            classifier="rule",
            keywords=["오류", "접속"],
        )

        key = await handler.handle(outlook_msg, intent)
        assert key == "PROJ-42"
        MockJira.return_value.create_issue.assert_called_once()


@pytest.mark.asyncio
async def test_jira_ticket_failure_returns_none(outlook_msg):
    with (
        patch("inbound_gw_agent.handlers.ticket_handler.JIRA") as MockJira,
        patch("inbound_gw_agent.handlers.ticket_handler.get_settings") as mock_settings,
        patch("inbound_gw_agent.handlers.ticket_handler.ollama"),
    ):
        mock_settings.return_value = _mock_settings()
        MockJira.return_value.create_issue.side_effect = Exception("connection error")

        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
        handler = JiraTicketHandler()
        intent = ClassifiedIntent(type=IntentType.URGENT, confidence=0.9, classifier="rule")

        key = await handler.handle(outlook_msg, intent)
        assert key is None


@pytest.mark.asyncio
async def test_assignee_preserved_when_reporter_fails(outlook_msg):
    """reporter 설정 실패 시 assignee는 유지된 채로 재시도해야 한다."""
    call_count = 0
    captured_fields = []

    def fake_create_issue(fields):
        nonlocal call_count
        call_count += 1
        captured_fields.append(dict(fields))
        if call_count == 1:
            raise Exception("reporter field not allowed")
        mock_issue = MagicMock()
        mock_issue.key = "PROJ-99"
        return mock_issue

    with (
        patch("inbound_gw_agent.handlers.ticket_handler.JIRA") as MockJira,
        patch("inbound_gw_agent.handlers.ticket_handler.get_settings") as mock_settings,
        patch("inbound_gw_agent.handlers.ticket_handler.ollama"),
    ):
        settings = _mock_settings()
        settings.jira_account_id = "712020:1cffed93-f372-418c-9a8d-c9cc05e4463a"
        mock_settings.return_value = settings
        MockJira.return_value.create_issue.side_effect = fake_create_issue

        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler
        handler = JiraTicketHandler()
        intent = ClassifiedIntent(type=IntentType.URGENT, confidence=0.9, classifier="rule")

        key = await handler.handle(outlook_msg, intent)

        assert key == "PROJ-99", "재시도 후 티켓이 생성되어야 한다"
        assert call_count == 2, "총 2번 시도해야 한다"
        # 1차 시도: reporter + assignee 모두 있음
        assert "reporter" in captured_fields[0]
        assert "assignee" in captured_fields[0]
        # 2차 시도: reporter 제거, assignee 유지
        assert "reporter" not in captured_fields[1]
        assert "assignee" in captured_fields[1], "assignee가 제거되면 안 된다"


@pytest.mark.asyncio
async def test_ticket_has_no_auto_labels(outlook_msg):
    with (
        patch("inbound_gw_agent.handlers.ticket_handler.JIRA") as MockJira,
        patch("inbound_gw_agent.handlers.ticket_handler.get_settings") as mock_settings,
        patch("inbound_gw_agent.handlers.ticket_handler.ollama"),
    ):
        handler = _make_handler(MockJira, mock_settings)
        intent = ClassifiedIntent(
            type=IntentType.URGENT,
            confidence=0.9,
            summary="시스템 장애",
            classifier="rule",
        )

        await handler.handle(outlook_msg, intent)

        call_kwargs = MockJira.return_value.create_issue.call_args
        fields = call_kwargs.kwargs.get("fields") or call_kwargs.args[0]
        assert fields["labels"] == [], f"자동 레이블이 포함됨: {fields['labels']}"


@pytest.mark.asyncio
async def test_story_has_no_auto_labels(outlook_msg):
    with (
        patch("inbound_gw_agent.handlers.ticket_handler.JIRA") as MockJira,
        patch("inbound_gw_agent.handlers.ticket_handler.get_settings") as mock_settings,
        patch("inbound_gw_agent.handlers.ticket_handler.ollama"),
    ):
        handler = _make_handler(MockJira, mock_settings)

        await handler.create_story(
            msg=outlook_msg,
            md=3.0,
            team="개발팀",
            task_summary="보고서 양식 수정",
        )

        call_kwargs = MockJira.return_value.create_issue.call_args
        fields = call_kwargs.kwargs.get("fields") or call_kwargs.args[0]
        assert fields["labels"] == [], f"자동 레이블이 포함됨: {fields['labels']}"


@pytest.mark.asyncio
async def test_story_explicit_labels_preserved(outlook_msg):
    with (
        patch("inbound_gw_agent.handlers.ticket_handler.JIRA") as MockJira,
        patch("inbound_gw_agent.handlers.ticket_handler.get_settings") as mock_settings,
        patch("inbound_gw_agent.handlers.ticket_handler.ollama"),
    ):
        handler = _make_handler(MockJira, mock_settings)

        await handler.create_story(
            msg=outlook_msg,
            md=2.0,
            team="기획팀",
            task_summary="기능 명세 작성",
            labels=["urgent", "q2"],
        )

        call_kwargs = MockJira.return_value.create_issue.call_args
        fields = call_kwargs.kwargs.get("fields") or call_kwargs.args[0]
        assert fields["labels"] == ["urgent", "q2"]
