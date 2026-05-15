from unittest.mock import MagicMock, patch

import pytest

from inbound_gw_agent.models.intent import ClassifiedIntent, IntentType


@pytest.mark.asyncio
async def test_jira_ticket_created(outlook_msg):
    mock_issue = MagicMock()
    mock_issue.key = "PROJ-42"

    with (
        patch("inbound_gw_agent.handlers.ticket_handler.JIRA") as MockJira,
        patch("inbound_gw_agent.handlers.ticket_handler.get_settings") as mock_settings,
    ):
        settings = MagicMock()
        settings.jira_server = "https://test.atlassian.net"
        settings.jira_email = "test@test.com"
        settings.jira_api_token = "token"
        settings.jira_project_key = "PROJ"
        mock_settings.return_value = settings

        MockJira.return_value.create_issue.return_value = mock_issue

        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler

        handler = JiraTicketHandler()
        intent = ClassifiedIntent(
            type=IntentType.INCIDENT,
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
    ):
        settings = MagicMock()
        settings.jira_server = "https://test.atlassian.net"
        settings.jira_email = "test@test.com"
        settings.jira_api_token = "token"
        settings.jira_project_key = "PROJ"
        mock_settings.return_value = settings

        MockJira.return_value.create_issue.side_effect = Exception("connection error")

        from inbound_gw_agent.handlers.ticket_handler import JiraTicketHandler

        handler = JiraTicketHandler()
        intent = ClassifiedIntent(type=IntentType.INCIDENT, confidence=0.9, classifier="rule")

        key = await handler.handle(outlook_msg, intent)
        assert key is None
