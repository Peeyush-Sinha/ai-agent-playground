from email import message_from_bytes

from email_agent.gmail_client import build_reply_mime, normalize_reply_subject, same_email_address
from email_agent.models import EmailMessageRecord


def sample_record() -> EmailMessageRecord:
    return EmailMessageRecord(
        gmail_id="abc123",
        thread_id="thread123",
        subject="Project update",
        sender="Client Name <client@example.com>",
        to="me@example.com",
        cc="",
        date="Mon, 1 Jan 2026 10:00:00 +0000",
        snippet="Can you send an update?",
        body_text="Can you send an update?",
        message_id_header="<original-message-id@example.com>",
        references_header="<earlier@example.com>",
        reply_to=None,
        attachment_names=[],
    )


def test_normalize_reply_subject_adds_re_prefix():
    assert normalize_reply_subject("Project update") == "Re: Project update"


def test_normalize_reply_subject_preserves_existing_re():
    assert normalize_reply_subject("Re: Project update") == "Re: Project update"


def test_build_reply_mime_sets_threading_headers():
    msg = build_reply_mime(
        original=sample_record(),
        body="Thanks, I will send this today.",
        from_address="me@example.com",
    )
    parsed = message_from_bytes(msg.as_bytes())
    assert parsed["To"] == "client@example.com"
    assert parsed["From"] == "me@example.com"
    assert parsed["Subject"] == "Re: Project update"
    assert parsed["In-Reply-To"] == "<original-message-id@example.com>"
    assert "<original-message-id@example.com>" in parsed["References"]


def test_same_email_address_handles_display_names():
    assert same_email_address("Client <a@example.com>", "a@example.com") is True
    assert same_email_address("Client <a@example.com>", "other@example.com") is False
