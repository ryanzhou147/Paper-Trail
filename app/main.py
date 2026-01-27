"""Main pipeline orchestration for job application tracker."""

import logging
import sys
from pathlib import Path

from filelock import FileLock, Timeout

from .config import get_config, load_config
from .dedupe import init_db, is_duplicate, is_processed, mark_processed
from .gmail_client import delete_email, fetch_new_emails
from .parser import parse_email
from .sheets import append_rows

LOCK_FILE = Path("/tmp/job_tracker.lock")
LOG_DIR = Path(__file__).parent.parent / "logs"


def setup_logging() -> None:
    """Configure logging for the application."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / "app.log"

    config = get_config()
    level = getattr(logging, config.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run_pipeline() -> dict:
    """Run the main email processing pipeline."""
    logger = logging.getLogger(__name__)
    config = get_config()

    stats = {
        "emails_fetched": 0,
        "emails_skipped": 0,
        "emails_parsed": 0,
        "duplicates": 0,
        "applications_added": 0,
        "emails_deleted": 0,
        "errors": 0,
    }

    logger.info("Starting job application tracker pipeline")

    init_db()

    logger.info("Fetching emails from Gmail...")
    try:
        emails = fetch_new_emails()
        stats["emails_fetched"] = len(emails)
    except Exception as e:
        logger.error(f"Failed to fetch emails: {e}")
        raise

    applications_to_add = []

    for email in emails:
        email_id = email.get("id", "")

        if is_processed(email_id):
            logger.debug(f"Skipping already processed email: {email_id}")
            stats["emails_skipped"] += 1
            continue

        try:
            job = parse_email(email)

            if job is None:
                logger.debug(f"Could not parse email: {email_id}")
                stats["errors"] += 1
                continue

            stats["emails_parsed"] += 1

            if job.confidence < config.confidence_threshold:
                logger.info(
                    f"Skipping low confidence ({job.confidence}) application: "
                    f"{job.company} - {job.position}"
                )
                mark_processed(email_id, job)
                continue

            if is_duplicate(job.company, job.position, job.date_applied):
                logger.info(
                    f"Skipping duplicate application: {job.company} - {job.position}"
                )
                stats["duplicates"] += 1
                mark_processed(email_id, job)
                continue

            applications_to_add.append(job)
            mark_processed(email_id, job)

        except Exception as e:
            logger.error(f"Error processing email {email_id}: {e}")
            stats["errors"] += 1

    if applications_to_add:
        try:
            count = append_rows(applications_to_add)
            stats["applications_added"] = count
            logger.info(f"Added {count} applications to spreadsheet")

            # Delete emails after successful write to spreadsheet
            for job in applications_to_add:
                try:
                    delete_email(job.source_email_id)
                    stats["emails_deleted"] += 1
                except Exception as e:
                    logger.error(f"Failed to delete email {job.source_email_id}: {e}")

        except Exception as e:
            logger.error(f"Failed to write to spreadsheet: {e}")
            raise

    logger.info(
        f"Pipeline complete: {stats['emails_fetched']} fetched, "
        f"{stats['emails_skipped']} skipped, "
        f"{stats['applications_added']} added, "
        f"{stats['emails_deleted']} deleted"
    )

    return stats


def main() -> int:
    """Main entry point with concurrency protection."""
    try:
        load_config()
        setup_logging()
    except FileNotFoundError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    logger = logging.getLogger(__name__)

    try:
        with FileLock(LOCK_FILE, timeout=10):
            logger.info("Acquired lock, starting pipeline")
            stats = run_pipeline()
            return 0 if stats["errors"] == 0 else 1

    except Timeout:
        logger.warning("Could not acquire lock - another instance is running")
        return 0

    except Exception as e:
        logger.exception(f"Pipeline failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
