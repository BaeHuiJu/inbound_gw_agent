from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import structlog

log = structlog.get_logger()
KST = timezone(timedelta(hours=9))


def _resolve_sender_address(msg: object) -> str:
    """Exchange DN 형식을 SMTP 주소로 변환한다.

    내부 사용자의 SenderEmailAddress는 '/O=EXCHANGELABS/...' 형식(Exchange DN)을
    반환할 수 있다. 이 경우 GetExchangeUser()로 실제 SMTP 주소를 조회하고,
    실패하면 SenderName(표시 이름)으로 폴백한다.
    """
    raw = getattr(msg, "SenderEmailAddress", "") or ""
    if raw and not raw.upper().startswith("/O="):
        return raw  # 이미 정상적인 SMTP 주소

    # Exchange DN → SMTP 변환 시도
    try:
        sender_obj = getattr(msg, "Sender", None)
        if sender_obj is not None:
            exchange_user = sender_obj.GetExchangeUser()
            if exchange_user is not None:
                smtp = getattr(exchange_user, "PrimarySmtpAddress", "") or ""
                if smtp:
                    return smtp
    except Exception:
        pass

    # 폴백: 표시 이름 (예: "홍길동")
    return getattr(msg, "SenderName", "") or raw


class OutlookComClient:
    """Classic Outlook COM 자동화 — 별도 인증 불필요, 현재 로그인된 Outlook 사용."""

    def _get_today_emails_sync(self) -> list[dict]:
        import win32com.client  # type: ignore[import]
        from datetime import date as _date

        outlook = win32com.client.Dispatch("Outlook.Application")
        ns = outlook.GetNamespace("MAPI")
        inbox = ns.GetDefaultFolder(6)  # olFolderInbox = 6

        today_kst = datetime.now(KST).date()
        items = inbox.Items
        items.Sort("[ReceivedTime]", True)  # 최신순 정렬

        log.info("outlook_com_inbox_scanned", total=items.Count, today_kst=str(today_kst))

        emails: list[dict] = []
        # Restrict 필터 대신 Python 쪽에서 날짜 비교 — 로케일 무관
        msg = items.GetFirst()
        while msg is not None:
            try:
                if hasattr(msg, "ReceivedTime"):
                    r = msg.ReceivedTime
                    msg_date = _date(r.year, r.month, r.day)
                    if msg_date < today_kst:
                        break  # 최신순이므로 여기서부터는 오늘 이전
                    if msg_date == today_kst:
                        # COM ReceivedTime은 로컬(KST)이므로 +09:00 명시
                        sender_addr = _resolve_sender_address(msg)
                        emails.append({
                            "from": {"emailAddress": {"address": sender_addr}},
                            "subject": getattr(msg, "Subject", "") or "",
                            "body": getattr(msg, "Body", "") or "",
                            "receivedDateTime": (
                                f"{r.year:04d}-{r.month:02d}-{r.day:02d}"
                                f"T{r.hour:02d}:{r.minute:02d}:{r.second:02d}+09:00"
                            ),
                        })
            except Exception:
                pass
            msg = items.GetNext()
        return emails

    async def get_today_emails(self) -> list[dict]:
        return await asyncio.to_thread(self._get_today_emails_sync)
