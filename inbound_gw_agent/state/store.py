from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

log = structlog.get_logger()

KST = timezone(timedelta(hours=9))

_DDL = """
CREATE TABLE IF NOT EXISTS processed_messages (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    intent_type TEXT,
    jira_key    TEXT,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kv_store (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class StateStore:
    def __init__(self, db_path: str = "state.db") -> None:
        self._conn = sqlite3.connect(Path(db_path), check_same_thread=False)
        self._conn.executescript(_DDL)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        new_cols = (
            "sender", "subject", "received_at",
            "mine", "personal_priority", "action_required",
            "email_category", "suggested_action",
            "body",
        )
        for col in new_cols:
            try:
                self._conn.execute(
                    f"ALTER TABLE processed_messages ADD COLUMN {col} TEXT"
                )
            except sqlite3.OperationalError:
                pass  # column already exists

    def is_processed(self, message_id: str, received_at: str | None = None) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM processed_messages WHERE id = ?", (message_id,)
        ).fetchone()
        if row:
            return True
        # 발신자 형식 변경 등으로 ID가 달라져도 received_at 기준으로 중복 방지
        if received_at:
            row = self._conn.execute(
                "SELECT 1 FROM processed_messages WHERE received_at = ?",
                (received_at,),
            ).fetchone()
            return row is not None
        return False

    def mark_processed(
        self,
        message_id: str,
        source: str,
        intent_type: str | None = None,
        jira_key: str | None = None,
        sender: str | None = None,
        subject: str | None = None,
        received_at: str | None = None,
        mine: bool | None = None,
        personal_priority: str | None = None,
        action_required: bool | None = None,
        email_category: str | None = None,
        suggested_action: str | None = None,
        body: str | None = None,
    ) -> None:
        self._conn.execute(
            """INSERT OR IGNORE INTO processed_messages
               (id, source, intent_type, jira_key, processed_at, sender, subject, received_at,
                mine, personal_priority, action_required, email_category, suggested_action, body)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                message_id,
                source,
                intent_type,
                jira_key,
                datetime.now(timezone.utc).isoformat(),
                sender,
                subject,
                received_at,
                ("1" if mine else "0") if mine is not None else None,
                personal_priority,
                ("1" if action_required else "0") if action_required is not None else None,
                email_category,
                suggested_action,
                body,
            ),
        )
        self._conn.commit()

    def get_today_messages(self) -> list[dict]:
        today_kst = datetime.now(KST).date()
        start = datetime(today_kst.year, today_kst.month, today_kst.day, tzinfo=KST).astimezone(timezone.utc)
        end = start + timedelta(days=1)
        rows = self._conn.execute(
            """SELECT id, source, sender, subject, intent_type, jira_key,
                      COALESCE(received_at, processed_at) AS received_at,
                      processed_at,
                      mine, personal_priority, action_required, email_category, suggested_action
               FROM processed_messages
               WHERE COALESCE(received_at, processed_at) >= ? AND COALESCE(received_at, processed_at) < ?
               ORDER BY COALESCE(received_at, processed_at) DESC""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        keys = (
            "id", "source", "sender", "subject", "intent_type", "jira_key",
            "received_at", "processed_at",
            "mine", "personal_priority", "action_required", "email_category", "suggested_action",
        )
        results = []
        for row in rows:
            d = dict(zip(keys, row))
            # SQLite TEXT → Python bool 변환
            d["mine"] = d["mine"] == "1" if d["mine"] is not None else None
            d["action_required"] = d["action_required"] == "1" if d["action_required"] is not None else None
            results.append(d)
        return results

    def get_messages_by_date_range(self, start_date: str, end_date: str) -> list[dict]:
        """KST 기준 날짜 범위(YYYY-MM-DD)로 메시지를 조회한다."""
        start_kst = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=KST)
        end_kst = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1)
        rows = self._conn.execute(
            """SELECT id, source, sender, subject, intent_type, jira_key,
                      COALESCE(received_at, processed_at) AS received_at,
                      processed_at,
                      mine, personal_priority, action_required, email_category, suggested_action,
                      SUBSTR(body, 1, 100) AS body_preview
               FROM processed_messages
               WHERE COALESCE(received_at, processed_at) >= ? AND COALESCE(received_at, processed_at) < ?
               ORDER BY COALESCE(received_at, processed_at) DESC""",
            (start_kst.astimezone(timezone.utc).isoformat(), end_kst.astimezone(timezone.utc).isoformat()),
        ).fetchall()
        keys = (
            "id", "source", "sender", "subject", "intent_type", "jira_key",
            "received_at", "processed_at",
            "mine", "personal_priority", "action_required", "email_category", "suggested_action",
            "body_preview",
        )
        results = []
        for row in rows:
            d = dict(zip(keys, row))
            d["mine"] = d["mine"] == "1" if d["mine"] is not None else None
            d["action_required"] = d["action_required"] == "1" if d["action_required"] is not None else None
            results.append(d)
        return results

    def get_message_by_id(self, message_id: str) -> dict | None:
        row = self._conn.execute(
            """SELECT id, source, sender, subject, intent_type, jira_key,
                      received_at, processed_at,
                      mine, personal_priority, action_required, email_category, suggested_action, body
               FROM processed_messages WHERE id = ?""",
            (message_id,),
        ).fetchone()
        if not row:
            return None
        keys = (
            "id", "source", "sender", "subject", "intent_type", "jira_key",
            "received_at", "processed_at",
            "mine", "personal_priority", "action_required", "email_category", "suggested_action", "body",
        )
        d = dict(zip(keys, row))
        d["mine"] = d["mine"] == "1" if d["mine"] is not None else None
        d["action_required"] = d["action_required"] == "1" if d["action_required"] is not None else None
        return d

    def update_jira_key(self, message_id: str, jira_key: str) -> None:
        self._conn.execute(
            "UPDATE processed_messages SET jira_key = ? WHERE id = ?",
            (jira_key, message_id),
        )
        self._conn.commit()

    def delete_message(self, message_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM processed_messages WHERE id = ?", (message_id,)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_delta_token(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM kv_store WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else None

    def set_delta_token(self, key: str, value: str) -> None:
        self._conn.execute(
            """INSERT INTO kv_store (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, value, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
