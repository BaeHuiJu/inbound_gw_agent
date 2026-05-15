from __future__ import annotations

from abc import ABC, abstractmethod

from inbound_gw_agent.models.intent import ClassifiedIntent
from inbound_gw_agent.models.message import InboundMessage


class BaseHandler(ABC):
    @abstractmethod
    async def handle(self, msg: InboundMessage, intent: ClassifiedIntent) -> str | None:
        """Process the message and return an external reference ID (e.g. Jira key)."""
