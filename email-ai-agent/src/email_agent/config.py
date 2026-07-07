"""Configuration loading for the email AI agent."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables and CLI overrides."""

    openai_api_key: str | None
    openai_model: str
    gmail_credentials_file: Path
    gmail_token_file: Path
    gmail_query: str
    max_emails: int
    state_db: Path
    user_style_profile: str
    email_signature: str

    @classmethod
    def load(
        cls,
        *,
        query: str | None = None,
        max_emails: int | None = None,
        env_file: str | Path | None = None,
    ) -> "Settings":
        """Load settings from .env and environment variables."""
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.5"),
            gmail_credentials_file=Path(os.getenv("GMAIL_CREDENTIALS_FILE", "credentials.json")),
            gmail_token_file=Path(os.getenv("GMAIL_TOKEN_FILE", "token.json")),
            gmail_query=query or os.getenv(
                "GMAIL_QUERY",
                "in:inbox is:unread -category:promotions -category:social",
            ),
            max_emails=max_emails or _parse_int(os.getenv("MAX_EMAILS"), default=10),
            state_db=Path(os.getenv("STATE_DB", ".email_agent_state.sqlite3")),
            user_style_profile=os.getenv(
                "USER_STYLE_PROFILE",
                "Friendly, concise, professional. Prefer clear next steps.",
            ),
            email_signature=os.getenv("EMAIL_SIGNATURE", ""),
        )

    def require_openai_key(self) -> None:
        if not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Copy .env.example to .env and set your OpenAI API key."
            )


def _parse_int(value: str | None, *, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(parsed, 1)
