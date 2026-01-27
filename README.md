# PaperTrail$

Automatically scans your Gmail inbox for job application confirmation emails and logs them to a Google Sheet. Runs unattended via cron on a Linux system.

## Features

- Scans Gmail Primary inbox for job application confirmations
- Extracts company name and position using AI (OpenRouter API)
- Writes to Google Sheets: Position | Company | Date Applied
- Moves processed emails to trash (not permanently deleted)
- Deduplicates using SQLite to avoid duplicate entries
- Filters out incomplete/started applications
- Runs automatically every hour via cron

## Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) package manager
- Google account with Gmail
- Google Cloud project (free tier works)
- OpenRouter API key (for AI extraction)

## Setup

### 1. Clone and Install Dependencies

```bash
git clone <repo-url>
cd job-tracker
uv sync
```

### 2. Google Cloud Setup (The Tricky Part)

This is the most involved step. You need to create a Google Cloud project and enable the Gmail and Sheets APIs.

#### 2.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top and select **New Project**
3. Name it something like "Job Tracker" and click **Create**
4. Make sure your new project is selected in the dropdown

#### 2.2 Enable APIs

You need to enable two APIs:

1. Go to **APIs & Services → Library**
2. Search for **Gmail API** and click on it
3. Click **Enable**
4. Go back to the Library
5. Search for **Google Sheets API** and click on it
6. Click **Enable**

#### 2.3 Configure OAuth Consent Screen

Before creating credentials, you must configure the consent screen:

1. Go to **APIs & Services → OAuth consent screen**
2. Select **External** and click **Create**
3. Fill in the required fields:
   - App name: "Job Tracker"
   - User support email: your email
   - Developer contact email: your email
4. Click **Save and Continue**
5. On the Scopes page, click **Save and Continue** (no scopes needed here)
6. On the Test users page, click **Add Users**
7. **Important:** Add your Gmail address (the one you want to scan)
8. Click **Save and Continue**

> **Note:** Your app will be in "Testing" mode. Only emails added as test users can authenticate. This is fine for personal use.

#### 2.4 Create OAuth Credentials

1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Select **Desktop app** as the application type
4. Name it "Job Tracker Desktop"
5. Click **Create**
6. Click **Download JSON**
7. Save the file as `config/credentials.json` in your project folder

### 3. OpenRouter API Key

1. Go to [OpenRouter](https://openrouter.ai/)
2. Sign up and get an API key
3. You'll set this as an environment variable later

### 4. Configure the Application

1. Copy the example config:
   ```bash
   cp config/config.yaml.example config/config.yaml
   ```

2. Edit `config/config.yaml`:
   ```yaml
   # Get this from your Google Sheet URL:
   # https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_SPREADSHEET_ID/edit
   spreadsheet_id: "your-spreadsheet-id-here"

   # The sheet/tab name within the spreadsheet
   sheet_name: "Sheet1"

   # How many days back to search for emails
   gmail_query_days: 7

   # Minimum confidence to accept (0.0 to 1.0)
   confidence_threshold: 0.3
   ```

3. Create a new Google Sheet and copy its ID from the URL

### 5. First Run (OAuth Authentication)

The first run will open your browser to authenticate with Google:

```bash
OPENROUTER_API_KEY=your-openrouter-key uv run python -m app.main
```

You'll see:
1. A browser window opens asking you to sign in to Google
2. Select your Gmail account (must be a test user you added earlier)
3. You'll see a warning "Google hasn't verified this app" - click **Continue**
4. Grant permissions for Gmail (read/modify) and Sheets (edit)
5. The browser will say "The authentication flow has completed"

If you get **Error 403: access_denied**, make sure:
- Your email is added as a test user in OAuth consent screen
- You're signing in with the correct Google account

After successful auth, tokens are saved to `config/token.json` and `config/sheets_token.json`. You won't need to authenticate again unless the tokens expire.

### 6. Set Up Automatic Scheduling (Cron)

To run the tracker every hour:

```bash
crontab -e
```

Add this line (replace with your actual paths and API key):

```
0 * * * * OPENROUTER_API_KEY=your-openrouter-key /path/to/job-tracker/scripts/run.sh
```

This runs at the top of every hour (10:00, 11:00, etc.).

Other scheduling options:
- Every 30 minutes: `*/30 * * * *`
- Every 6 hours: `0 */6 * * *`
- Once daily at 9am: `0 9 * * *`

### 7. Verify It's Working

Check the logs after the next scheduled run:

```bash
cat logs/app.log
cat logs/cron.log
```

You should see entries like:
```
INFO - Found 3 potential application emails
INFO - Parsed application: Google - Software Engineer Intern (confidence: 0.87)
INFO - Added 2 applications to spreadsheet
INFO - Moved email abc123 to trash
INFO - Pipeline complete: 3 fetched, 1 skipped, 2 added, 2 deleted
```

## Manual Run

You can run it manually anytime:

```bash
OPENROUTER_API_KEY=your-key uv run python -m app.main
```

The FileLock prevents conflicts if a cron job is already running.

## How It Works

1. **Email Fetching**: Queries Gmail for emails matching:
   - From ATS domains: greenhouse.io, lever.co, workday.com, myworkday.com, ashbyhq.com, icims.com, etc.
   - Subject keywords: "thank you for applying", "application received", "application submitted", etc.
   - Only checks the Primary inbox (not Promotions/Social/Updates)

2. **Filtering**: Skips emails that indicate incomplete applications:
   - "Thanks for starting your application"
   - "Complete your application"
   - "Application incomplete"

3. **Parsing**: Uses OpenRouter AI (Gemini 2.0 Flash) to extract:
   - Company name
   - Position/job title (or "N/A" if not found)

4. **Deduplication**: Checks SQLite database to skip already-processed emails

5. **Writing**: Appends to Google Sheet with columns:
   - Position | Company | Date Applied

6. **Cleanup**: Moves processed emails to Gmail trash

## File Structure

```
job-tracker/
├── app/
│   ├── main.py          # Pipeline orchestration
│   ├── gmail_client.py  # Gmail API client
│   ├── parser.py        # Email parsing + AI extraction
│   ├── sheets.py        # Google Sheets client
│   ├── dedupe.py        # SQLite deduplication
│   ├── models.py        # Data models
│   └── config.py        # Configuration loading
├── config/
│   ├── config.yaml      # Your configuration (git-ignored)
│   ├── config.yaml.example
│   ├── credentials.json # OAuth client (git-ignored)
│   ├── token.json       # Gmail token (git-ignored)
│   └── sheets_token.json # Sheets token (git-ignored)
├── data/
│   └── processed.sqlite # Processed email IDs (git-ignored)
├── logs/
│   ├── app.log          # Application logs
│   └── cron.log         # Cron execution logs
├── scripts/
│   └── run.sh           # Cron wrapper script
├── pyproject.toml
└── README.md
```

## Troubleshooting

### "Gmail API has not been used in project X"
Enable the Gmail API in Google Cloud Console:
https://console.developers.google.com/apis/api/gmail.googleapis.com

### "Error 403: access_denied"
Add your email as a test user:
1. Google Cloud Console → APIs & Services → OAuth consent screen
2. Scroll to "Test users" → Add your email

### "Sheets API has not been used in project X"
Enable the Sheets API in Google Cloud Console:
https://console.developers.google.com/apis/api/sheets.googleapis.com

### No emails found
- Check that job confirmation emails are in your Primary inbox (not Promotions)
- Verify `gmail_query_days` in config covers the date range
- Run with `log_level: "DEBUG"` for more details

### Token expired
Delete the token files and re-run to re-authenticate:
```bash
rm config/token.json config/sheets_token.json
OPENROUTER_API_KEY=your-key uv run python -m app.main
```

## Resetting

To start fresh:

```bash
# Clear processed emails database
rm data/processed.sqlite

# Clear logs
rm logs/*.log
```

## Security Notes

- OAuth tokens are stored locally (never commit them)
- The Gmail scope allows read/modify (needed to trash emails)
- No email content is permanently stored
- API keys should be set as environment variables, not in code

## License

MIT
