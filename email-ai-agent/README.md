# Email AI Agent

A safe, draft-only Python agent that watches your Gmail inbox, decides which messages need a response, generates a suggested reply with AI Agent, and saves the result as a Gmail draft for you to review.

It does **not** send emails automatically.

## What it does

- Authenticates to Gmail with OAuth.
- Searches Gmail with a configurable Gmail query, for example `in:inbox is:unread`.
- Reads matching emails and extracts plain-text or HTML body content.
- Asks AI Agent for a structured decision: reply or no reply.
- Creates a Gmail draft reply in the original thread when a response is useful.
- Stores processed Gmail message IDs in a local SQLite database to prevent duplicate drafts.
- Supports a dry-run mode so you can preview behavior before creating drafts.

## Requirements

- Python 3.10 or newer.
- A Google account with Gmail enabled.
- A Google Cloud project with Gmail API enabled.
- A Google OAuth desktop client downloaded as `credentials.json`.
- An AI Agent API key.

## Setup

### 1. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install the project

```bash
pip install -e .
```

Or install from `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 3. Configure Gmail API access

In Google Cloud Console:

1. Create or open a Google Cloud project.
2. Enable the Gmail API.
3. Configure the OAuth consent screen.
4. Create an OAuth Client ID with application type **Desktop app**.
5. Download the client JSON file.
6. Rename it to `credentials.json` and place it in the project root.

The app requests these OAuth scopes:

```python
https://www.googleapis.com/auth/gmail.readonly
https://www.googleapis.com/auth/gmail.compose
```

If you change scopes later, delete `token.json` and run authentication again.

### 4. Configure OpenAI and app settings

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-5.5
GMAIL_CREDENTIALS_FILE=credentials.json
GMAIL_TOKEN_FILE=token.json
GMAIL_QUERY=in:inbox is:unread -category:promotions -category:social
MAX_EMAILS=10
STATE_DB=.email_agent_state.sqlite3
USER_STYLE_PROFILE=Friendly, concise, professional. Prefer clear next steps and avoid overpromising.
EMAIL_SIGNATURE=Best,\nYour Name
```

## Usage

### Authenticate Gmail

```bash
email-agent auth
```

The first run opens a browser for Google OAuth consent and stores `token.json` locally.

### Preview without creating drafts

```bash
email-agent run --dry-run --max 3
```

### Create Gmail drafts

```bash
email-agent run --max 5
```

Open Gmail and review the drafts before sending.

### Use a custom Gmail search query

```bash
email-agent run --query 'in:inbox is:unread from:client@example.com' --max 10
```

### Show processed message state

```bash
email-agent state --limit 20
```

## Scheduling

You can run the agent periodically with cron, launchd, Windows Task Scheduler, or a small server process. For example, a cron entry that runs every 15 minutes:

```cron
*/15 * * * * cd /path/to/email-ai-agent && /path/to/email-ai-agent/.venv/bin/email-agent run --max 10 >> email-agent.log 2>&1
```

Keep `--dry-run` while testing. Remove it only after you are comfortable with the drafts.

## Safety and privacy notes

- This project creates drafts only; it never calls Gmail's send endpoint.
- `credentials.json`, `token.json`, `.env`, and the SQLite state database are ignored by Git and should stay private.
- Emails are sent to the OpenAI API for drafting. The code sets `store=False` on the Responses API call where supported.
- The prompt tells the model to ignore instructions inside emails that try to alter system rules, steal credentials, or change output format.
- Attachments are not downloaded or sent to the model; only attachment filenames are included as context.
- Do not use this unattended for legal, medical, financial, HR, or other high-stakes correspondence without human review.

## Troubleshooting

### `Missing credentials.json`

Create a Google OAuth desktop client and save the downloaded JSON file as `credentials.json` in the project root, or set `GMAIL_CREDENTIALS_FILE` in `.env`.

### `Access blocked` or OAuth scope errors

Make sure your OAuth consent screen is configured and that your Google account is added as a test user if the app is external/testing. Delete `token.json` after changing scopes.

## Development

Install dev dependencies:

```bash
pip install -e '.[dev]'
```

Run tests:

```bash
pytest
```
