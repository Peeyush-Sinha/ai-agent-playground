"""Gmail API client helpers for listing messages and creating drafts."""

from __future__ import annotations

import base64
import html
import re
from email.message import EmailMessage
from email.utils import getaddresses, parseaddr
from typing import Any

from .config import GMAIL_SCOPES, Settings
from .models import EmailMessageRecord


class GmailClient:
    """Small wrapper around the Gmail API."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.service: Any | None = None

    def authenticate(self) -> Any:
        """Authenticate with OAuth and return an authorized Gmail service."""
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        token_file = self.settings.gmail_token_file
        credentials_file = self.settings.gmail_credentials_file

        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), GMAIL_SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_file.exists():
                    raise FileNotFoundError(
                        f"Missing {credentials_file}. Create a Google OAuth desktop client and save it here."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), GMAIL_SCOPES)
                creds = flow.run_local_server(port=0)

            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(creds.to_json(), encoding="utf-8")

        self.service = build("gmail", "v1", credentials=creds)
        return self.service

    def _require_service(self) -> Any:
        if self.service is None:
            return self.authenticate()
        return self.service

    def get_profile_email(self) -> str:
        service = self._require_service()
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress", "")

    def list_message_ids(self, *, query: str, max_results: int) -> list[str]:
        """Return Gmail message IDs matching a Gmail search query."""
        service = self._require_service()
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return [item["id"] for item in response.get("messages", [])]

    def fetch_message(self, message_id: str) -> EmailMessageRecord:
        """Fetch a Gmail message and normalize common headers/body."""
        service = self._require_service()
        message = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = message.get("payload", {})
        headers = _headers_to_dict(payload.get("headers", []))
        body_text, attachments = _extract_body_text_and_attachments(payload)

        return EmailMessageRecord(
            gmail_id=message.get("id", message_id),
            thread_id=message.get("threadId", ""),
            subject=headers.get("subject", ""),
            sender=headers.get("from", ""),
            to=headers.get("to", ""),
            cc=headers.get("cc", ""),
            date=headers.get("date", ""),
            snippet=message.get("snippet", ""),
            body_text=body_text.strip(),
            message_id_header=headers.get("message-id"),
            references_header=headers.get("references"),
            reply_to=headers.get("reply-to"),
            attachment_names=attachments,
        )

    def create_reply_draft(
        self,
        *,
        original: EmailMessageRecord,
        body: str,
        from_address: str,
        subject: str | None = None,
    ) -> dict[str, Any]:
        """Create a Gmail draft reply in the original thread."""
        service = self._require_service()
        mime_message = build_reply_mime(
            original=original,
            body=body,
            from_address=from_address,
            subject=subject,
        )
        encoded_message = base64.urlsafe_b64encode(mime_message.as_bytes()).decode("utf-8")
        create_body: dict[str, Any] = {
            "message": {
                "raw": encoded_message,
                "threadId": original.thread_id,
            }
        }
        return (
            service.users()
            .drafts()
            .create(userId="me", body=create_body)
            .execute()
        )


def build_reply_mime(
    *,
    original: EmailMessageRecord,
    body: str,
    from_address: str,
    subject: str | None = None,
) -> EmailMessage:
    """Build an RFC 2822 MIME reply message for Gmail draft creation."""
    reply_to = original.reply_to or original.sender
    recipient = _first_email_address(reply_to)
    if not recipient:
        recipient = reply_to

    message = EmailMessage()
    message.set_content(body.strip() + "\n")
    message["To"] = recipient
    message["From"] = from_address
    message["Subject"] = normalize_reply_subject(subject or original.subject)

    if original.message_id_header:
        message["In-Reply-To"] = original.message_id_header
        references = original.references_header or ""
        if original.message_id_header not in references:
            references = f"{references} {original.message_id_header}".strip()
        if references:
            message["References"] = references

    return message


def normalize_reply_subject(subject: str) -> str:
    cleaned = (subject or "").strip()
    if not cleaned:
        return "Re:"
    if re.match(r"^\s*re\s*:", cleaned, flags=re.IGNORECASE):
        return cleaned
    return f"Re: {cleaned}"


def _headers_to_dict(headers: list[dict[str, str]]) -> dict[str, str]:
    return {item.get("name", "").lower(): item.get("value", "") for item in headers}


def _extract_body_text_and_attachments(payload: dict[str, Any]) -> tuple[str, list[str]]:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[str] = []

    def walk(part: dict[str, Any]) -> None:
        filename = part.get("filename") or ""
        body = part.get("body", {})
        if filename and body.get("attachmentId"):
            attachments.append(filename)
            return

        mime_type = part.get("mimeType", "")
        data = body.get("data")
        if data:
            decoded = _decode_base64url_text(data)
            if mime_type == "text/plain":
                plain_parts.append(decoded)
            elif mime_type == "text/html":
                html_parts.append(_html_to_text(decoded))

        for child in part.get("parts", []) or []:
            walk(child)

    walk(payload)
    text = "\n\n".join(part.strip() for part in plain_parts if part.strip())
    if not text:
        text = "\n\n".join(part.strip() for part in html_parts if part.strip())
    return _clean_text(text), attachments


def _decode_base64url_text(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
    return raw.decode("utf-8", errors="replace")


def _html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?i)<\s*br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</\s*(p|div|li|tr|h[1-6])\s*>", "\n", value)
    value = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(value)


def _clean_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _first_email_address(header_value: str) -> str:
    parsed = getaddresses([header_value])
    if parsed:
        return parsed[0][1] or parsed[0][0]
    return parseaddr(header_value)[1]


def same_email_address(left: str, right: str) -> bool:
    """Compare possibly formatted email addresses."""
    left_email = parseaddr(left)[1].lower()
    right_email = parseaddr(right)[1].lower()
    return bool(left_email and right_email and left_email == right_email)
