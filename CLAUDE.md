# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Job Application Tracker that automatically scans Gmail for job application confirmation emails and writes structured records (company, position, date applied) to a Google Sheet. Runs unattended on a headless Linux server via cron.

## Architecture

```
User applies to job
        ↓
Confirmation email arrives in Gmail
        ↓
Cron triggers tracker script
        ↓
Gmail API fetches new emails
        ↓
Parser extracts company / role / date
        ↓
Deduplication check (SQLite)
        ↓
Append row to Google Sheet
```

## Tech Stack

- Python 3.14+
- Gmail API (read-only scope)
- Google Sheets API
- SQLite (local cache for processed email IDs)
- cron for scheduling

## Directory Structure

```
job-tracker/
  app/
    main.py
    gmail_client.py
    parser.py
    sheets.py
    dedupe.py
    models.py
  config/
    credentials.json
    token.json
  data/
    processed.sqlite
  scripts/
    run.sh
  logs/
```

## Commands

```bash
# Run the application
uv run python app/main.py

# Add dependencies
uv add <package-name>

# Run via cron wrapper
./scripts/run.sh
```

## Data Model

Each job application entry:
```json
{
  "company": "Stripe",
  "position": "Software Engineer Intern",
  "date_applied": "2026-01-23",
  "source_email_id": "18c9f2...",
  "confidence": 0.94
}
```

Spreadsheet columns: Company, Position, Date Applied, Source (ATS/domain), Email ID, Notes, Created At

## Email Processing

**Fetch targets:**
- Subject keywords: "application", "applied", "thank you", "received"
- ATS domains: greenhouse.io, lever.co, workday.com, ashbyhq.com, smartrecruiters.com

**Classification:** Heuristic filter (subject + sender) with optional LLM fallback for edge cases

**Extraction:** HTML→text parsing, regex templates for common ATS formats, LLM fallback if regex confidence < threshold

**Deduplication:** Store processed Gmail message IDs in SQLite; secondary key is (company, position, date_applied ± 1 day)

## Design Principles

- API-first (no browser automation for Gmail)
- Idempotent (safe to re-run)
- Headless & unattended
- Deterministic parsing + optional LLM fallback
- Spreadsheet as system of record

## Concurrency Protection

Use filelock to prevent overlapping cron runs:
```python
from filelock import FileLock
with FileLock("/tmp/job_tracker.lock"):
    run_pipeline()
```

## Security Notes

- OAuth tokens encrypted at rest
- Read-only Gmail scope only
- No permanent storage of full email bodies
- config/ directory excluded from git
