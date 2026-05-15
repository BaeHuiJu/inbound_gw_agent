from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone

import structlog
import uvicorn

from inbound_gw_agent.config import get_settings
from inbound_gw_agent.connectors.webhook_receiver import create_app
from inbound_gw_agent.models.message import InboundMessage, MessageSource
from inbound_gw_agent.pipeline import Pipeline

log = structlog.get_logger()


async def _fetch_and_store_today_emails(pipeline: Pipeline) -> None:
    settings = get_settings()
    emails: list[dict] | None = None

    # 1순위: Classic Outlook COM (인증 불필요)
    try:
        from inbound_gw_agent.connectors.outlook_com import OutlookComClient
        client_com = OutlookComClient()
        emails = await client_com.get_today_emails()
        log.info("emails_fetched_via_outlook_com", count=len(emails))
    except ImportError:
        log.info("pywin32_not_installed_skip_com")
    except Exception as exc:
        log.info("outlook_com_failed_fallback", error=repr(exc)[:120])

    # 2순위: Microsoft Graph API (AZURE_CLIENT_ID 설정 시 활성화)
    if emails is None and settings.azure_client_id:
        try:
            from inbound_gw_agent.connectors.graph_mail import GraphMailClient
            client_graph = GraphMailClient(
                client_id=settings.azure_client_id,
                tenant_id=settings.azure_tenant_id,
                cache_path=settings.token_cache_path,
            )
            emails = await client_graph.get_today_emails()
            log.info("emails_fetched_via_graph", count=len(emails))
        except Exception as exc:
            log.warning("startup_email_fetch_failed", error=repr(exc)[:200])
            emails = []

    if emails is None:
        emails = []

    classified = 0
    for email in emails:
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "")
        subject = email.get("subject", "")
        body = email.get("body", "") or email.get("bodyPreview", "")
        received_str = email.get("receivedDateTime", "")
        received_at = (
            datetime.fromisoformat(received_str.replace("Z", "+00:00"))
            if received_str else datetime.now(timezone.utc)
        )
        raw_id = f"{received_at.isoformat()}|{subject}|{body[:50]}"
        msg_id = hashlib.sha256(raw_id.encode()).hexdigest()[:32]

        msg = InboundMessage(
            id=msg_id,
            source=MessageSource.OUTLOOK,
            sender=sender,
            subject=subject,
            body=body or "(내용 없음)",
            received_at=received_at,
        )
        await pipeline.process_message(msg, classify_only=True)
        classified += 1
    log.info("startup_emails_classified", total=len(emails), classified=classified)


async def _poll_loop(pipeline: Pipeline, interval: int = 300) -> None:
    """Outlook COM 주기적 폴링 — interval초마다 오늘 메일 재수집."""
    while True:
        await asyncio.sleep(interval)
        log.info("poll_loop_tick")
        try:
            await _fetch_and_store_today_emails(pipeline)
        except Exception as exc:
            log.warning("poll_loop_error", error=repr(exc)[:200])


async def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]
    )

    settings = get_settings()
    pipeline = Pipeline()

    log.info("fetching_today_emails")
    await _fetch_and_store_today_emails(pipeline)

    app = create_app(pipeline)

    poll_interval = settings.poll_interval_seconds
    asyncio.create_task(_poll_loop(pipeline, interval=poll_interval))
    log.info("poll_loop_started", interval_seconds=poll_interval)

    config = uvicorn.Config(
        app,
        host=settings.webhook_host,
        port=settings.webhook_port,
        log_level="warning",  # uvicorn 로그는 최소화, 앱 로그는 structlog 사용
    )
    server = uvicorn.Server(config)

    log.info(
        "agent_started",
        host=settings.webhook_host,
        port=settings.webhook_port,
        hint=f"ngrok 실행: ngrok http {settings.webhook_port}",
    )

    try:
        await server.serve()
    finally:
        pipeline.close()
        log.info("agent_stopped")


if __name__ == "__main__":
    asyncio.run(main())
