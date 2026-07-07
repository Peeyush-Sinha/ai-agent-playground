"""Command-line interface for the email AI agent."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from email.utils import parseaddr

from googleapiclient.errors import HttpError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import Settings
from .draft_agent import DraftAgent
from .gmail_client import GmailClient, same_email_address
from .state import StateStore

console = Console()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "auth":
        return run_auth(args)
    if args.command == "run":
        return run_agent(args)
    if args.command == "state":
        return run_state(args)

    parser.print_help()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="email-agent",
        description="Draft-only AI email agent for Gmail.",
    )
    subparsers = parser.add_subparsers(dest="command")

    auth_parser = subparsers.add_parser("auth", help="Authenticate Gmail OAuth and show the active Gmail account.")
    auth_parser.add_argument("--env-file", default=None, help="Optional path to a .env file.")

    run_parser = subparsers.add_parser("run", help="Scan Gmail and create AI-generated reply drafts.")
    run_parser.add_argument("--env-file", default=None, help="Optional path to a .env file.")
    run_parser.add_argument("--query", default=None, help="Override the Gmail search query.")
    run_parser.add_argument("--max", type=int, default=None, help="Maximum number of matching emails to process.")
    run_parser.add_argument("--dry-run", action="store_true", help="Preview decisions without creating Gmail drafts or updating state.")
    run_parser.add_argument("--include-own", action="store_true", help="Allow drafting replies to messages sent from your own email address.")

    state_parser = subparsers.add_parser("state", help="Show recently processed Gmail messages.")
    state_parser.add_argument("--env-file", default=None, help="Optional path to a .env file.")
    state_parser.add_argument("--limit", type=int, default=20, help="Number of rows to show.")

    return parser


def run_auth(args: argparse.Namespace) -> int:
    settings = Settings.load(env_file=args.env_file)
    try:
        gmail = GmailClient(settings)
        gmail.authenticate()
        profile_email = gmail.get_profile_email()
    except Exception as exc:
        console.print(f"[red]Gmail authentication failed:[/red] {exc}")
        return 1

    console.print(f"[green]Authenticated Gmail account:[/green] {profile_email}")
    console.print("OAuth token saved to:", settings.gmail_token_file)
    return 0


def run_agent(args: argparse.Namespace) -> int:
    settings = Settings.load(query=args.query, max_emails=args.max, env_file=args.env_file)
    state = StateStore(settings.state_db)

    try:
        gmail = GmailClient(settings)
        gmail.authenticate()
        profile_email = gmail.get_profile_email()
        message_ids = gmail.list_message_ids(query=settings.gmail_query, max_results=settings.max_emails)
    except Exception as exc:
        console.print(f"[red]Could not connect to Gmail:[/red] {exc}")
        return 1

    if not message_ids:
        console.print("No matching Gmail messages found.")
        return 0

    console.print(
        Panel.fit(
            f"Account: {profile_email}\nQuery: {settings.gmail_query}\nMatches: {len(message_ids)}\nDry run: {args.dry_run}",
            title="Email AI Agent",
        )
    )

    try:
        agent = DraftAgent(settings)
    except Exception as exc:
        console.print(f"[red]OpenAI setup failed:[/red] {exc}")
        return 1

    created_count = 0
    skipped_count = 0

    for gmail_id in message_ids:
        if state.has_processed(gmail_id):
            skipped_count += 1
            console.print(f"[yellow]Skipping already processed message:[/yellow] {gmail_id}")
            continue

        try:
            record = gmail.fetch_message(gmail_id)
        except HttpError as exc:
            skipped_count += 1
            console.print(f"[red]Could not fetch {gmail_id}:[/red] {exc}")
            continue

        if not args.include_own and same_email_address(record.sender, profile_email):
            skipped_count += 1
            console.print(f"[yellow]Skipping own message:[/yellow] {record.subject}")
            if not args.dry_run:
                from .models import DraftDecision

                state.mark_processed(
                    gmail_id=record.gmail_id,
                    thread_id=record.thread_id,
                    draft_id=None,
                    subject=record.subject,
                    decision=DraftDecision.no_reply("Message was sent from the authenticated account."),
                )
            continue

        console.rule(f"{record.subject or '(no subject)'}")
        console.print(f"From: {record.sender}")
        console.print(f"Date: {record.date}")

        try:
            decision = agent.draft_reply(record)
        except Exception as exc:
            skipped_count += 1
            console.print(f"[red]Draft generation failed for {gmail_id}:[/red] {exc}")
            continue

        _print_decision(decision)

        if args.dry_run:
            continue

        if not decision.should_reply:
            state.mark_processed(
                gmail_id=record.gmail_id,
                thread_id=record.thread_id,
                draft_id=None,
                subject=record.subject,
                decision=decision,
            )
            skipped_count += 1
            continue

        try:
            draft = gmail.create_reply_draft(
                original=record,
                body=decision.body,
                from_address=profile_email,
                subject=decision.subject or record.subject,
            )
        except HttpError as exc:
            skipped_count += 1
            console.print(f"[red]Could not create draft for {gmail_id}:[/red] {exc}")
            continue

        draft_id = draft.get("id")
        state.mark_processed(
            gmail_id=record.gmail_id,
            thread_id=record.thread_id,
            draft_id=draft_id,
            subject=record.subject,
            decision=decision,
        )
        created_count += 1
        console.print(f"[green]Created Gmail draft:[/green] {draft_id}")

    console.print(
        Panel.fit(
            f"Drafts created: {created_count}\nSkipped/no-reply/already processed: {skipped_count}",
            title="Done",
        )
    )
    return 0


def run_state(args: argparse.Namespace) -> int:
    settings = Settings.load(env_file=args.env_file)
    state = StateStore(settings.state_db)
    rows = state.recent(limit=args.limit)
    if not rows:
        console.print("No processed messages in local state yet.")
        return 0

    table = Table(title=f"Recent processed messages from {settings.state_db}")
    table.add_column("Created")
    table.add_column("Gmail ID")
    table.add_column("Draft ID")
    table.add_column("Subject")
    table.add_column("Reply?")
    for row in rows:
        decision = json.loads(row["decision_json"])
        table.add_row(
            row["created_at"],
            row["gmail_id"],
            row["draft_id"] or "-",
            row["subject"] or "-",
            str(decision.get("should_reply")),
        )
    console.print(table)
    return 0


def _print_decision(decision) -> None:
    if decision.should_reply:
        color = "green"
        heading = f"Reply draft ({decision.priority} priority)"
        body = decision.body or "(empty body)"
    else:
        color = "yellow"
        heading = "No reply recommended"
        body = decision.reason or decision.notes or "No reason provided."

    console.print(Panel(Text(body), title=heading, border_style=color))
    if decision.notes:
        console.print(f"Notes: {decision.notes}")


if __name__ == "__main__":
    sys.exit(main())
