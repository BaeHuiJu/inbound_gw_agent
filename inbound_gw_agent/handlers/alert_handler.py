from __future__ import annotations

import httpx
import structlog

log = structlog.get_logger()


async def send_urgent_alert(
    sender: str,
    subject: str,
    body_preview: str,
    teams_url: str = "",
    slack_url: str = "",
) -> None:
    text = f"[긴급] {subject}\n발신: {sender}\n{body_preview[:200]}"

    async with httpx.AsyncClient(timeout=10) as client:
        if teams_url:
            try:
                await client.post(teams_url, json={"text": text})
                log.info("urgent_alert_teams_sent", subject=subject)
            except Exception as e:
                log.warning("urgent_alert_teams_failed", error=str(e))

        if slack_url:
            try:
                await client.post(slack_url, json={"text": text})
                log.info("urgent_alert_slack_sent", subject=subject)
            except Exception as e:
                log.warning("urgent_alert_slack_failed", error=str(e))
