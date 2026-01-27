"""Gmail API client for fetching job application emails."""

import base64
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .config import get_config

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

ATS_DOMAINS = [
    # Major ATS platforms
    "greenhouse.io",
    "greenhouse-mail.io",
    "lever.co",
    "ashbyhq.com",
    "smartrecruiters.com",
    "icims.com",
    "jobvite.com",
    "ultipro.com",
    "taleo.net",
    "oraclecloud.com",
    # Workday variants
    "workday.com",
    "myworkday.com",
    "myworkdayjobs.com",
    "wd1.myworkdayjobs.com",
    "wd3.myworkdayjobs.com",
    "wd5.myworkdayjobs.com",
    # Other ATS/HR platforms
    "breezy.hr",
    "bamboohr.com",
    "recruiterbox.com",
    "recruitee.com",
    "workable.com",
    "jazz.co",
    "jazzhr.com",
    "pinpointhq.com",
    "applytojob.com",
    "hire.lever.co",
    "jobs.lever.co",
    "successfactors.com",
    "adp.com",
    "paylocity.com",
    "paycom.com",
    "ceridian.com",
    "dayforce.com",
    # Job boards
    "linkedin.com",
    "indeed.com",
    "ziprecruiter.com",
    "glassdoor.com",
    "angel.co",
    "wellfound.com",
]

SUBJECT_KEYWORDS = [
    # Application confirmations
    "thank you for applying",
    "thanks for applying",
    "thank you for your application",
    "thanks for your application",
    "application received",
    "application submitted",
    "application confirmation",
    "we received your application",
    "we have received your application",
    "your application has been received",
    "your application was received",
    "successfully submitted",
    "successfully applied",
    # Generic
    "application",
    "applied",
    "applying",
    # Interest expressions
    "thank you for your interest",
    "thanks for your interest",
    "interest in joining",
]


def get_credentials() -> Credentials:
    """Get or refresh Gmail API credentials."""
    config_dir = Path(__file__).parent.parent / "config"
    token_path = config_dir / "token.json"
    credentials_path = config_dir / "credentials.json"

    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials")
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Credentials file not found: {credentials_path}. "
                    "Download credentials.json from Google Cloud Console."
                )
            logger.info("Starting OAuth flow for Gmail")
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())
            logger.info(f"Saved credentials to {token_path}")

    return creds


def build_gmail_query(days_back: int = 7) -> str:
    """Build Gmail search query for job application emails."""
    after_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")

    domain_queries = " OR ".join([f"from:{domain}" for domain in ATS_DOMAINS])
    subject_queries = " OR ".join([f'subject:"{kw}"' for kw in SUBJECT_KEYWORDS])

    # Only check Primary inbox category
    query = f"after:{after_date} category:primary ({domain_queries} OR {subject_queries})"
    return query


def fetch_new_emails() -> list[dict[str, Any]]:
    """Fetch new job application emails from Gmail."""
    config = get_config()
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    query = build_gmail_query(config.gmail_query_days)
    logger.info(f"Fetching emails with query: {query}")

    messages = []
    page_token = None

    while True:
        results = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token)
            .execute()
        )

        if "messages" in results:
            messages.extend(results["messages"])

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    logger.info(f"Found {len(messages)} potential application emails")

    full_messages = []
    for msg_ref in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="full")
            .execute()
        )
        full_messages.append(msg)

    return full_messages


def get_email_body(message: dict[str, Any]) -> str:
    """Extract email body text from message."""
    payload = message.get("payload", {})

    def extract_text(part: dict) -> Optional[str]:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif part.get("mimeType") == "text/html":
            data = part.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        return None

    if "parts" in payload:
        for part in payload["parts"]:
            text = extract_text(part)
            if text:
                return text
            if "parts" in part:
                for subpart in part["parts"]:
                    text = extract_text(subpart)
                    if text:
                        return text

    body_data = payload.get("body", {}).get("data", "")
    if body_data:
        return base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

    return ""


def get_email_headers(message: dict[str, Any]) -> dict[str, str]:
    """Extract common headers from email message."""
    headers = {}
    payload = message.get("payload", {})

    for header in payload.get("headers", []):
        name = header.get("name", "").lower()
        if name in ("from", "to", "subject", "date"):
            headers[name] = header.get("value", "")

    return headers


def delete_email(email_id: str) -> None:
    """Delete an email by moving it to trash."""
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    service.users().messages().trash(userId="me", id=email_id).execute()
    logger.info(f"Moved email {email_id} to trash")
