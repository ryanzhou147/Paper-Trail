#!/usr/bin/env bash
# Cron wrapper script for job application tracker
# Usage: ./scripts/run.sh
# Add to crontab: 0 9 * * * /path/to/job-tracker/scripts/run.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$LOG_DIR"

cd "$PROJECT_DIR"

LOG_FILE="$LOG_DIR/cron.log"

echo "======================================" >> "$LOG_FILE"
echo "Run started at $(date -Iseconds)" >> "$LOG_FILE"
echo "======================================" >> "$LOG_FILE"

if command -v uv &> /dev/null; then
    uv run python -m app.main >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
else
    echo "Error: uv not found. Please install uv first." >> "$LOG_FILE"
    EXIT_CODE=1
fi

echo "Run completed at $(date -Iseconds) with exit code $EXIT_CODE" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

exit $EXIT_CODE
