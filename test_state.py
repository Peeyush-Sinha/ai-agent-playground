from email_agent.models import DraftDecision
from email_agent.state import StateStore


def test_state_store_tracks_processed_messages(tmp_path):
    db = tmp_path / "state.sqlite3"
    store = StateStore(db)
    assert store.has_processed("msg") is False

    store.mark_processed(
        gmail_id="msg",
        thread_id="thread",
        draft_id="draft",
        subject="Hello",
        decision=DraftDecision(
            should_reply=True,
            priority="normal",
            subject="Re: Hello",
            body="Hello, how are you",
            notes="",
            reason="",
        ),
    )

    assert store.has_processed("msg") is True
    rows = store.recent(limit=1)
    assert rows[0]["gmail_id"] == "msg"
    assert rows[0]["draft_id"] == "draft"
