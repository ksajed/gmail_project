#!/bin/bash

# =================================================
# Script CRON — Synchronisation Gmail (Pharmacie)
# =================================================

PROJECT_DIR="/home/ksajed/gmail_project/gmail_manager"
VENV_DIR="/home/ksajed/gmail_project/venv"
LOG_FILE="/home/ksajed/gmail_project/logs/fetch_gmail.log"

echo "--------------------------------------------" >> "$LOG_FILE"
echo "$(date) — DÉBUT SYNCHRO GMAIL" >> "$LOG_FILE"

cd "$PROJECT_DIR" || exit 1

source "$VENV_DIR/bin/activate"

python manage.py fetch_gmail >> "$LOG_FILE" 2>&1

echo "$(date) — FIN SYNCHRO GMAIL" >> "$LOG_FILE"
