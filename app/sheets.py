"""Google Sheets API client for writing job applications."""

import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import get_config
from .models import JobApplication

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_credentials() -> Credentials:
    """Get or refresh Sheets API credentials."""
    config_dir = Path(__file__).parent.parent / "config"
    token_path = config_dir / "sheets_token.json"
    credentials_path = config_dir / "credentials.json"

    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Sheets credentials")
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Credentials file not found: {credentials_path}. "
                    "Download credentials.json from Google Cloud Console."
                )
            logger.info("Starting OAuth flow for Sheets")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())
            logger.info(f"Saved Sheets credentials to {token_path}")

    return creds


def ensure_headers(service, spreadsheet_id: str, sheet_name: str) -> None:
    """Ensure the spreadsheet has the correct headers."""
    headers = [
        "Position",
        "Company",
        "Date Applied",
    ]

    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1:C1")
        .execute()
    )

    existing = result.get("values", [[]])[0] if result.get("values") else []

    if existing != headers:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A1:C1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()
        logger.info("Added headers to spreadsheet")


def append_row(job: JobApplication) -> None:
    """Append a job application row to the spreadsheet."""
    config = get_config()
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)

    ensure_headers(service, config.spreadsheet_id, config.sheet_name)

    row = job.to_row()

    service.spreadsheets().values().append(
        spreadsheetId=config.spreadsheet_id,
        range=f"{config.sheet_name}!A:C",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

    logger.info(f"Appended row to spreadsheet: {job.position} - {job.company}")


def append_rows(jobs: list[JobApplication]) -> int:
    """Append multiple job application rows to the spreadsheet."""
    if not jobs:
        return 0

    config = get_config()
    creds = get_credentials()
    service = build("sheets", "v4", credentials=creds)

    ensure_headers(service, config.spreadsheet_id, config.sheet_name)

    rows = [job.to_row() for job in jobs]

    service.spreadsheets().values().append(
        spreadsheetId=config.spreadsheet_id,
        range=f"{config.sheet_name}!A:C",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()

    logger.info(f"Appended {len(rows)} rows to spreadsheet")
    return len(rows)
