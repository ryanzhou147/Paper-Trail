# PaperTrail

Gmail-to-Google-Sheets job application tracker. When run, it prompts you for the number of most recent inbox emails that are job applications, parses them for company/position/date, and appends the results to a Google Sheet.

## Features

- Prompts for how many recent inbox emails to process
- Extracts company name and position using AI (OpenRouter API)
- Writes to Google Sheets: Position | Company | Date Applied
- Moves processed emails to trash
- Deduplicates using SQLite to avoid duplicate entries
- Scheduled via cron

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

### 2. Google Cloud Setup

#### 2.1 Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top and select **New Project**
3. Name it something like "Job Tracker" and click **Create**
4. Make sure your new project is selected in the dropdown

#### 2.2 Enable APIs

1. Go to **APIs & Services > Library**
2. Search for **Gmail API**, click it, and click **Enable**
3. Go back to the Library
4. Search for **Google Sheets API**, click it, and click **Enable**

#### 2.3 Configure OAuth Consent Screen

1. Go to **APIs & Services > OAuth consent screen**
2. Select **External** and click **Create**
3. Fill in required fields (app name, support email, developer email)
4. Click **Save and Continue** through the remaining steps
5. On the Test users page, add your Gmail address

> Your app will be in "Testing" mode. Only test users can authenticate. This is fine for personal use.

#### 2.4 Create OAuth Credentials

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. Select **Desktop app**
4. Click **Create**, then **Download JSON**
5. Save the file as `config/credentials.json`

### 3. Configure the Application

```bash
cp config/config.yaml.example config/config.yaml
```

Edit `config/config.yaml`:

```yaml
# Get this from your Google Sheet URL:
# https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_SPREADSHEET_ID/edit
spreadsheet_id: "your-spreadsheet-id-here"

# The sheet/tab name within the spreadsheet
sheet_name: "Sheet1"

# OpenRouter API key (https://openrouter.ai/)
openrouter_api_key: "your-openrouter-api-key-here"
```

Create a new Google Sheet and copy its ID from the URL.

### 4. First Run (OAuth Authentication)

The first run will open your browser to authenticate with Google:

```bash
.venv/bin/python -m app.main
```

You'll be prompted to sign in and grant permissions for Gmail and Sheets. After successful auth, tokens are saved locally and you won't need to authenticate again unless they expire.

If you get **Error 403: access_denied**, make sure your email is added as a test user in the OAuth consent screen.

### 5. Set Up Automatic Scheduling (Cron)

```bash
crontab -e
```

Add these lines (replace with your actual path):

```
0 12 * * * /path/to/job-tracker/scripts/run.sh
0 22 * * * /path/to/job-tracker/scripts/run.sh
```

A terminal window will pop up at 12pm and 10pm daily asking how many recent emails to process. Enter the number, and it runs. Press Enter to close the window when done.

## Usage

```bash
.venv/bin/python -m app.main
```

The program will ask:

```
How many of your most recent inbox emails are job applications?
```

Enter a number. It fetches that many of your most recent inbox emails, parses each one for company/position/date, appends the results to your Google Sheet, and trashes the processed emails.

## How It Works

1. **Prompt**: Asks the user how many recent inbox emails are job applications
2. **Fetch**: Retrieves that many most recent emails from the Gmail inbox
3. **Parse**: Uses regex and OpenRouter AI (Gemini 2.0 Flash) to extract company, position, and date
4. **Deduplicate**: Checks SQLite database to skip already-processed emails
5. **Write**: Appends rows to Google Sheet (Position | Company | Date Applied)
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
│   ├── config.yaml      # All settings + API key (git-ignored)
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
Add your email as a test user in **APIs & Services > OAuth consent screen**.

### "Sheets API has not been used in project X"
Enable the Sheets API in Google Cloud Console:
https://console.developers.google.com/apis/api/sheets.googleapis.com

### Token expired
Delete the token files and re-run to re-authenticate:
```bash
rm config/token.json config/sheets_token.json
.venv/bin/python -m app.main
```

## Resetting

```bash
# Clear processed emails database
rm data/processed.sqlite

# Clear logs
rm logs/*.log
```

## Security Notes

- All secrets (API keys, OAuth tokens) live in `config/` which is git-ignored
- The Gmail scope allows read/modify (needed to trash emails)
- No email content is permanently stored

## License

MIT
