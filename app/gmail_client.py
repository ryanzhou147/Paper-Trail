"""Gmail API client for fetching emails."""

import base64
import logging
from pathlib import Path
from typing import Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


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



def fetch_recent_emails(count: int) -> list[dict[str, Any]]:
    """Fetch the N most recent emails from the inbox."""
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    logger.info(f"Fetching {count} most recent inbox emails")

    results = (
        service.users()
        .messages()
        .list(userId="me", q="in:inbox", maxResults=count)
        .execute()
    )

    messages = results.get("messages", [])
    logger.info(f"Found {len(messages)} emails")

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
