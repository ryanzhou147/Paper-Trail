#!/usr/bin/env bash
# Cron wrapper script for job application tracker
# Opens a terminal window so the user can enter the email count interactively.
#
# Add to crontab:
#   0 12 * * * /path/to/job-tracker/scripts/run.sh
#   0 22 * * * /path/to/job-tracker/scripts/run.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
PYTHON="$PROJECT_DIR/.venv/bin/python"

mkdir -p "$LOG_DIR"

export DISPLAY=$(who | grep -oP '\(:\d+\)' | head -1 | tr -d '()' || echo ":0")
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"

gnome-terminal -- bash -c "
    cd '$PROJECT_DIR'
    echo '======================================' >> '$LOG_DIR/cron.log'
    echo \"Run started at \$(date -Iseconds)\" >> '$LOG_DIR/cron.log'
    echo '======================================' >> '$LOG_DIR/cron.log'

    '$PYTHON' -m app.main 2>&1 | tee -a '$LOG_DIR/cron.log'
    EXIT_CODE=\${PIPESTATUS[0]}

    echo \"Run completed at \$(date -Iseconds) with exit code \$EXIT_CODE\" >> '$LOG_DIR/cron.log'
    echo '' >> '$LOG_DIR/cron.log'

    echo ''
    echo 'Press Enter to close...'
    read
    exit \$EXIT_CODE
"
