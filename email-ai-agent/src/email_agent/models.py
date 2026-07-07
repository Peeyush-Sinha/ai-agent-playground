"""Domain models for the email AI agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EmailMessageRecord:
    """Normalized Gmail message data used by the drafting agent."""

    gmail_id: str
    thread_id: str
    subject: str
    sender: str
    to: str
    cc: str
    date: str
    snippet: str
    body_text: str
    message_id_header: str | None = None
    references_header: str | None = None
    reply_to: str | None = None
    attachment_names: list[str] = field(default_factory=list)

    def to_prompt_dict(self) -> dict[str, Any]:
        """Return a compact dictionary safe to serialize into the model input."""
        return {
            "gmail_id": self.gmail_id,
            "thread_id": self.thread_id,
            "from": self.sender,
            "reply_to": self.reply_to,
            "to": self.to,
            "cc": self.cc,
            "date": self.date,
            "subject": self.subject,
            "snippet": self.snippet,
            "attachments": self.attachment_names,
            "body_text": self.body_text,
        }


@dataclass(frozen=True)
class DraftDecision:
    """Structured output returned by the AI drafting agent."""

    should_reply: bool
    priority: str
    subject: str
    body: str
    notes: str = ""
    reason: str = ""

    @classmethod
    def no_reply(cls, reason: str) -> "DraftDecision":
        return cls(
            should_reply=False,
            priority="low",
            subject="",
            body="",
            notes="",
            reason=reason,
        )
