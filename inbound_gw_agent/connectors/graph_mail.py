from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone

import httpx
import msal
import structlog

log = structlog.get_logger()

_SCOPES = ["https://graph.microsoft.com/Mail.Read"]
_DEFAULT_AUTHORITY = "https://login.microsoftonline.com/common"
_GRAPH_URL = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
KST = timezone(timedelta(hours=9))

# Microsoft 공개 Graph Explorer 클라이언트 ID (앱 등록 불필요)
_PUBLIC_CLIENT_ID = "de8bc8b5-d9f9-48b1-a8ad-b748da725064"


class GraphMailClient:
    def __init__(self, client_id: str = _PUBLIC_CLIENT_ID, tenant_id: str = "common", cache_path: str = ".token_cache.bin") -> None:
        self._cache = msal.SerializableTokenCache()
        self._cache_path = cache_path
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                self._cache.deserialize(f.read())
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        self._app = msal.PublicClientApplication(
            client_id,
            authority=authority,
            token_cache=self._cache,
        )

    def _save_cache(self) -> None:
        if self._cache.has_state_changed:
            with open(self._cache_path, "w", encoding="utf-8") as f:
                f.write(self._cache.serialize())

    def _acquire_token(self) -> str:
        accounts = self._app.get_accounts()
        result = None
        if accounts:
            result = self._app.acquire_token_silent(_SCOPES, account=accounts[0])
        if not result:
            flow = self._app.initiate_device_flow(scopes=_SCOPES)
            if "error" in flow:
                raise RuntimeError(f"device_flow_failed: {flow['error']} - {flow.get('error_description', '')}")
            print("\n" + "=" * 60)
            print(flow["message"])
            print("=" * 60 + "\n")
            result = self._app.acquire_token_by_device_flow(flow)
        self._save_cache()
        if "access_token" not in result:
            raise RuntimeError(f"인증 실패: {result.get('error_description', result)}")
        return result["access_token"]

    async def get_today_emails(self) -> list[dict]:
        token = await asyncio.to_thread(self._acquire_token)
        today = datetime.now(KST).date()
        since = datetime(today.year, today.month, today.day, tzinfo=KST).astimezone(timezone.utc)
        params = {
            "$filter": f"receivedDateTime ge {since.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "$select": "subject,from,receivedDateTime,bodyPreview",
            "$top": "50",
            "$orderby": "receivedDateTime desc",
        }
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(_GRAPH_URL, headers=headers, params=params)
            resp.raise_for_status()
        return resp.json().get("value", [])
