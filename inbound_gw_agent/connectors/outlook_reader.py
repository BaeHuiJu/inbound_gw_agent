from __future__ import annotations

import asyncio
import imaplib
import email as email_lib
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime

import structlog

from inbound_gw_agent.config import get_settings
from inbound_gw_agent.models.message import InboundMessage, MessageSource
from inbound_gw_agent.state.store import StateStore

log = structlog.get_logger()

_MAX_PER_POLL = 50


class OutlookReader:
    """IMAP으로 받은편지함을 폴링합니다. New Outlook / 클래식 Outlook 모두 지원."""

    def __init__(self, store: StateStore) -> None:
        self._store = store
        self._settings = get_settings()

    async def read_new(self) -> list[InboundMessage]:
        return await asyncio.to_thread(self._read_sync)

    def _read_sync(self) -> list[InboundMessage]:
        s = self._settings
        try:
            imap = imaplib.IMAP4_SSL(s.imap_server, s.imap_port)
        except Exception as exc:
            log.error("imap_connect_failed", server=s.imap_server, error=str(exc))
            return []

        try:
            imap.login(s.imap_username, s.imap_password)
            imap.select(s.imap_folder)

            criteria = self._build_criteria()
            _, data = imap.search(None, criteria)
            if not data or not data[0]:
                return []

            msg_ids = data[0].split()[-_MAX_PER_POLL:]  # 최신 최대 50건
            messages: list[InboundMessage] = []

            for mid in msg_ids:
                _, raw_data = imap.fetch(mid, "(RFC822)")
                if not raw_data or raw_data[0] is None:
                    continue
                raw_bytes = raw_data[0][1]
                parsed = self._parse(email_lib.message_from_bytes(raw_bytes))
                if parsed:
                    messages.append(parsed)

            log.info("imap_read", count=len(messages), criteria=criteria)
            return messages

        except imaplib.IMAP4.error as exc:
            log.error("imap_error", error=str(exc),
                      hint="앱 비밀번호 확인 또는 관리자에게 IMAP 허용 요청")
            return []
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def _build_criteria(self) -> str:
        if self._settings.outlook_unread_only:
            return "UNSEEN"
        since = (
            datetime.now() - timedelta(hours=self._settings.outlook_lookback_hours)
        ).strftime("%d-%b-%Y")
        return f"SINCE {since}"

    def _parse(self, msg: email_lib.message.Message) -> InboundMessage | None:
        try:
            subject = self._decode_str(msg["Subject"]) or ""
            from_raw = self._decode_str(msg["From"]) or "unknown"
            msg_id = (msg["Message-ID"] or "").strip()
            if not msg_id:
                return None  # Message-ID 없는 메시지는 중복 추적 불가하여 건너뜀

            date_str = msg["Date"]
            try:
                received_at = parsedate_to_datetime(date_str).astimezone(timezone.utc)
            except Exception:
                received_at = datetime.now(timezone.utc)

            body = self._extract_body(msg)
            prefix = self._settings.teams_bridge_prefix

            if subject.startswith(prefix):
                source = MessageSource.TEAMS
                subject = subject[len(prefix):].strip()
            else:
                source = MessageSource.OUTLOOK

            return InboundMessage(
                id=msg_id,
                source=source,
                sender=from_raw,
                subject=subject or None,
                body=body,
                received_at=received_at,
            )
        except Exception as exc:
            log.warning("imap_parse_failed", error=str(exc))
            return None

    @staticmethod
    def _decode_str(value: str | None) -> str:
        if not value:
            return ""
        parts: list[str] = []
        for chunk, charset in decode_header(value):
            if isinstance(chunk, bytes):
                parts.append(chunk.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(chunk)
        return "".join(parts)

    @staticmethod
    def _extract_body(msg: email_lib.message.Message) -> str:
        # 멀티파트: text/plain 우선, 없으면 text/html
        if msg.is_multipart():
            for content_type in ("text/plain", "text/html"):
                for part in msg.walk():
                    if part.get_content_type() != content_type:
                        continue
                    if "attachment" in str(part.get("Content-Disposition", "")):
                        continue
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
        return ""
