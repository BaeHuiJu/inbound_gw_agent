from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def generate_message_id(
    sender: str | None,
    received_at: datetime,
    subject: str | None,
) -> str:
    """발신자 + 수신시각(초 단위 UTC) + 제목 기반 중복 방지 ID.

    Graph API 수집(__main__.py)과 webhook(webhook_receiver.py) 양쪽에서
    동일 메일이 들어와도 같은 ID가 나오도록 공통으로 사용한다.
    """
    received_at_norm = (
        received_at.replace(microsecond=0).astimezone(timezone.utc).isoformat()
    )
    raw_id = f"{sender or ''}|{received_at_norm}|{subject or ''}"
    return hashlib.sha256(raw_id.encode()).hexdigest()[:32]
