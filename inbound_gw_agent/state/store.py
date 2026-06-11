from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog

log = structlog.get_logger()

KST = timezone(timedelta(hours=9))

# 유사 사례 검색용 키워드 분리 / 불용어
_KEYWORD_SPLIT_RE = re.compile(r"[\s\[\](){}<>,.:;!?/\\|'\"~`@#$%^&*+=\-—]+")
_COMMON_WORDS = {
    "관련", "문의", "요청", "확인", "안내", "공유", "전달", "발생", "처리",
    "부탁드립니다", "드립니다", "합니다", "있습니다", "바랍니다",
    "re", "fw", "fwd", "the", "and", "for",
}

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
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_DDL)
            self._migrate()
            self._conn.commit()

    def _existing_columns(self, table: str) -> set[str]:
        rows = self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}

    def _migrate(self) -> None:
        new_cols = (
            "sender", "subject", "received_at",
            "mine", "personal_priority", "action_required",
            "email_category", "suggested_action",
            "body", "summary", "draft_reply",
            "jira_status", "is_manual", "jira_done_at",
            "fix_suggestion",
        )
        existing = self._existing_columns("processed_messages")
        for col in new_cols:
            if col not in existing:
                self._conn.execute(
                    f"ALTER TABLE processed_messages ADD COLUMN {col} TEXT"
                )
        # 기존 완료 티켓에 jira_done_at 백필 (processed_at 근사값)
        self._conn.execute(
            "UPDATE processed_messages SET jira_done_at = processed_at"
            " WHERE jira_status = '완료' AND jira_done_at IS NULL AND processed_at IS NOT NULL"
        )
        self._conn.commit()

    def is_processed(self, message_id: str, received_at: str | None = None) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM processed_messages WHERE id = ?", (message_id,)
            ).fetchone()
            if row:
                return True
            # received_at은 +09:00 / +00:00 등 timezone 표기가 달라도 같은 시각이므로
            # SQLite datetime()으로 UTC 정규화 후 비교
            if received_at:
                row = self._conn.execute(
                    "SELECT 1 FROM processed_messages WHERE datetime(received_at) = datetime(?)",
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
        is_manual: bool = False,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR IGNORE INTO processed_messages
                   (id, source, intent_type, jira_key, processed_at, sender, subject, received_at,
                    mine, personal_priority, action_required, email_category, suggested_action, body,
                    is_manual)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                    "1" if is_manual else "0",
                ),
            )
            self._conn.commit()

    def get_today_messages(self) -> list[dict]:
        today_kst = datetime.now(KST).date()
        start = datetime(today_kst.year, today_kst.month, today_kst.day, tzinfo=KST).astimezone(timezone.utc)
        end = start + timedelta(days=1)
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, source, sender, subject, intent_type, jira_key,
                          COALESCE(received_at, processed_at) AS received_at,
                          processed_at,
                          mine, personal_priority, action_required, email_category, suggested_action,
                          jira_status
                   FROM processed_messages
                   WHERE COALESCE(received_at, processed_at) >= ? AND COALESCE(received_at, processed_at) < ?
                   ORDER BY COALESCE(received_at, processed_at) DESC""",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        keys = (
            "id", "source", "sender", "subject", "intent_type", "jira_key",
            "received_at", "processed_at",
            "mine", "personal_priority", "action_required", "email_category", "suggested_action",
            "jira_status",
        )
        results = []
        for row in rows:
            d = dict(zip(keys, row))
            d["mine"] = d["mine"] == "1" if d["mine"] is not None else None
            d["action_required"] = d["action_required"] == "1" if d["action_required"] is not None else None
            results.append(d)
        return results

    def get_messages_by_date_range(self, start_date: str, end_date: str) -> list[dict]:
        """KST 기준 날짜 범위(YYYY-MM-DD)로 메시지를 조회한다."""
        start_kst = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=KST)
        end_kst = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1)
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, source, sender, subject, intent_type, jira_key,
                          COALESCE(received_at, processed_at) AS received_at,
                          processed_at,
                          mine, personal_priority, action_required, email_category, suggested_action,
                          SUBSTR(body, 1, 100) AS body_preview,
                          jira_status
                   FROM processed_messages
                   WHERE COALESCE(received_at, processed_at) >= ? AND COALESCE(received_at, processed_at) < ?
                   ORDER BY COALESCE(received_at, processed_at) DESC""",
                (start_kst.astimezone(timezone.utc).isoformat(), end_kst.astimezone(timezone.utc).isoformat()),
            ).fetchall()
        keys = (
            "id", "source", "sender", "subject", "intent_type", "jira_key",
            "received_at", "processed_at",
            "mine", "personal_priority", "action_required", "email_category", "suggested_action",
            "body_preview", "jira_status",
        )
        results = []
        for row in rows:
            d = dict(zip(keys, row))
            d["mine"] = d["mine"] == "1" if d["mine"] is not None else None
            d["action_required"] = d["action_required"] == "1" if d["action_required"] is not None else None
            results.append(d)
        return results

    def get_message_by_id(self, message_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                """SELECT id, source, sender, subject, intent_type, jira_key,
                          received_at, processed_at,
                          mine, personal_priority, action_required, email_category, suggested_action, body,
                          summary, draft_reply, fix_suggestion
                   FROM processed_messages WHERE id = ?""",
                (message_id,),
            ).fetchone()
        if not row:
            return None
        keys = (
            "id", "source", "sender", "subject", "intent_type", "jira_key",
            "received_at", "processed_at",
            "mine", "personal_priority", "action_required", "email_category", "suggested_action", "body",
            "summary", "draft_reply", "fix_suggestion",
        )
        d = dict(zip(keys, row))
        d["mine"] = d["mine"] == "1" if d["mine"] is not None else None
        d["action_required"] = d["action_required"] == "1" if d["action_required"] is not None else None
        return d

    def update_summary(self, message_id: str, summary: str) -> None:
        self._conn.execute(
            "UPDATE processed_messages SET summary = ? WHERE id = ?",
            (summary, message_id),
        )
        self._conn.commit()

    def update_draft_reply(self, message_id: str, draft_reply: str) -> None:
        self._conn.execute(
            "UPDATE processed_messages SET draft_reply = ? WHERE id = ?",
            (draft_reply, message_id),
        )
        self._conn.commit()

    def update_fix_suggestion(self, message_id: str, fix_suggestion: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE processed_messages SET fix_suggestion = ? WHERE id = ?",
                (fix_suggestion, message_id),
            )
            self._conn.commit()

    def find_similar_cases(
        self,
        message_id: str,
        subject: str | None,
        body: str | None = None,
        limit: int = 3,
    ) -> list[dict]:
        """제목 키워드 기반으로 과거 유사 오류 사례를 검색한다.

        해결 이력이 있는 메시지(jira_status='완료')를 우선 반환하고,
        부족하면 분석 요약(summary)이 있는 메시지로 채운다.
        """
        text = f"{subject or ''} {body[:200] if body else ''}"
        keywords = [w for w in _KEYWORD_SPLIT_RE.split(text) if len(w) >= 2]
        # 너무 흔한 단어 제외 후 상위 5개만 사용
        keywords = [w for w in keywords if w not in _COMMON_WORDS][:5]
        if not keywords:
            return []

        like_clause = " OR ".join(["subject LIKE ? OR body LIKE ?"] * len(keywords))
        params: list = []
        for kw in keywords:
            params.extend([f"%{kw}%", f"%{kw}%"])

        with self._lock:
            rows = self._conn.execute(
                f"""SELECT id, subject, received_at, jira_key, jira_status, summary, suggested_action
                    FROM processed_messages
                    WHERE id != ?
                      AND intent_type IN ('urgent', 'task')
                      AND ({like_clause})
                    ORDER BY
                      CASE WHEN jira_status = '완료' THEN 0 ELSE 1 END,
                      CASE WHEN summary IS NOT NULL THEN 0 ELSE 1 END,
                      received_at DESC
                    LIMIT ?""",
                (message_id, *params, limit),
            ).fetchall()

        keys = ("id", "subject", "received_at", "jira_key", "jira_status", "summary", "suggested_action")
        return [dict(zip(keys, row)) for row in rows]

    def update_jira_key(self, message_id: str, jira_key: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE processed_messages SET jira_key = ? WHERE id = ?",
                (jira_key, message_id),
            )
            self._conn.commit()

    def update_jira_status(self, message_id: str, status: str) -> None:
        from datetime import datetime, timezone as _tz
        done_at = datetime.now(_tz.utc).isoformat() if status == "완료" else None
        with self._lock:
            if done_at:
                self._conn.execute(
                    "UPDATE processed_messages SET jira_status = ?, jira_done_at = ? WHERE id = ?",
                    (status, done_at, message_id),
                )
            else:
                self._conn.execute(
                    "UPDATE processed_messages SET jira_status = ? WHERE id = ?",
                    (status, message_id),
                )
            self._conn.commit()

    def clear_jira_key(self, message_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE processed_messages SET jira_key = NULL, jira_status = NULL WHERE id = ?",
                (message_id,),
            )
            self._conn.commit()

    def delete_message(self, message_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM processed_messages WHERE id = ?", (message_id,)
            )
            self._conn.commit()
            return cur.rowcount > 0

    def get_delta_token(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM kv_store WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else None

    def set_delta_token(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO kv_store (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
                (key, value, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def get_manual_messages(self, source: str | None = None) -> list[dict]:
        clause = "WHERE is_manual='1'"
        params: list = []
        if source and source != "all":
            clause += " AND source=?"
            params.append(source)
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT id, source, sender, subject, intent_type, jira_key,
                           COALESCE(received_at, processed_at) AS received_at,
                           processed_at, jira_status,
                           mine, personal_priority, action_required, email_category, suggested_action
                    FROM processed_messages {clause}
                    ORDER BY COALESCE(received_at, processed_at) DESC""",
                params,
            ).fetchall()
        keys = (
            "id", "source", "sender", "subject", "intent_type", "jira_key",
            "received_at", "processed_at", "jira_status",
            "mine", "personal_priority", "action_required", "email_category", "suggested_action",
        )
        results = []
        for row in rows:
            d = dict(zip(keys, row))
            d["mine"] = d["mine"] == "1" if d["mine"] is not None else None
            d["action_required"] = d["action_required"] == "1" if d["action_required"] is not None else None
            results.append(d)
        return results

    def get_sender_history(self, sender: str, limit: int = 10) -> dict:
        """발신자의 메시지 이력과 통계를 반환한다."""
        with self._lock:
            stats_row = self._conn.execute(
                """SELECT
                       COUNT(*) AS total,
                       SUM(CASE WHEN intent_type='urgent' THEN 1 ELSE 0 END) AS urgent_count,
                       AVG(
                           CASE
                               WHEN received_at IS NOT NULL AND processed_at IS NOT NULL
                               THEN (julianday(processed_at) - julianday(received_at)) * 24.0
                               ELSE NULL
                           END
                       ) AS avg_hours
                   FROM processed_messages WHERE sender=?""",
                (sender,),
            ).fetchone()
            rows = self._conn.execute(
                """SELECT id, subject, intent_type, jira_key, jira_status,
                          COALESCE(received_at, processed_at) AS received_at
                   FROM processed_messages WHERE sender=?
                   ORDER BY COALESCE(received_at, processed_at) DESC
                   LIMIT ?""",
                (sender, limit),
            ).fetchall()
        keys = ("id", "subject", "intent_type", "jira_key", "jira_status", "received_at")
        messages = [dict(zip(keys, r)) for r in rows]
        total = stats_row[0] or 0
        urgent_count = stats_row[1] or 0
        avg_hours = round(stats_row[2], 1) if stats_row[2] is not None else None
        return {
            "messages": messages,
            "stats": {"total": total, "urgent_count": urgent_count, "avg_hours": avg_hours},
        }

    def nl_search(
        self,
        date_from: str | None,
        date_to: str | None,
        intent_types: list[str] | None,
        keywords: list[str] | None,
        has_jira: bool | None,
        personal_priority: str | None,
    ) -> list[dict]:
        """자연어 검색 파라미터로 메시지를 조회한다."""
        conditions: list[str] = []
        params: list = []
        if date_from:
            try:
                start_kst = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=KST)
                conditions.append("COALESCE(received_at, processed_at) >= ?")
                params.append(start_kst.astimezone(timezone.utc).isoformat())
            except ValueError:
                pass
        if date_to:
            try:
                end_kst = datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=KST) + timedelta(days=1)
                conditions.append("COALESCE(received_at, processed_at) < ?")
                params.append(end_kst.astimezone(timezone.utc).isoformat())
            except ValueError:
                pass
        if intent_types:
            placeholders = ",".join("?" * len(intent_types))
            conditions.append(f"intent_type IN ({placeholders})")
            params.extend(intent_types)
        if keywords:
            for kw in keywords:
                conditions.append("(subject LIKE ? OR body LIKE ? OR sender LIKE ?)")
                params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
        if has_jira is True:
            conditions.append("jira_key IS NOT NULL")
        elif has_jira is False:
            conditions.append("jira_key IS NULL")
        if personal_priority:
            conditions.append("personal_priority = ?")
            params.append(personal_priority)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT id, source, sender, subject, intent_type, jira_key,
                           COALESCE(received_at, processed_at) AS received_at,
                           processed_at,
                           mine, personal_priority, action_required, email_category, suggested_action,
                           jira_status
                    FROM processed_messages {where}
                    ORDER BY COALESCE(received_at, processed_at) DESC
                    LIMIT 200""",
                params,
            ).fetchall()
        keys = (
            "id", "source", "sender", "subject", "intent_type", "jira_key",
            "received_at", "processed_at",
            "mine", "personal_priority", "action_required", "email_category", "suggested_action",
            "jira_status",
        )
        results = []
        for row in rows:
            d = dict(zip(keys, row))
            d["mine"] = d["mine"] == "1" if d["mine"] is not None else None
            d["action_required"] = d["action_required"] == "1" if d["action_required"] is not None else None
            results.append(d)
        return results

    def close(self) -> None:
        with self._lock:
            self._conn.close()
