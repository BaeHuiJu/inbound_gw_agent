from __future__ import annotations

import re
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, field_validator


class MessageSource(str, Enum):
    OUTLOOK = "outlook"
    TEAMS = "teams"


class InboundMessage(BaseModel):
    id: str
    source: MessageSource
    sender: str
    subject: str | None = None
    body: str
    received_at: datetime
    raw: dict = {}

    @field_validator("body", mode="before")
    @classmethod
    def strip_html(cls, v: str) -> str:
        text = re.sub(r"<[^>]+>", " ", v)
        return re.sub(r"\s+", " ", text).strip()

    @property
    def full_text(self) -> str:
        parts = []
        if self.subject:
            parts.append(self.subject)
        parts.append(self.body)
        return " ".join(parts)
