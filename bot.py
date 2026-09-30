#!/usr/bin/env python3
"""
Oksana 365 Assistant — FULL VERSION
Telegram Bot + Google Calendar + Notifications + JSON Store
"""

import os
import json
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# === КОНФІГ ===
TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    print("❌ TELEGRAM_TOKEN не встановлено!")
    exit(1)

WORK_DIR = Path(__file__).parent
CALENDAR_CREDS_FILE = WORK_DIR / "calendar_credentials.json"
CALENDAR_TOKEN_FILE = WORK_DIR / "calendar_token.pickle"
TASKS_JSON_FILE = WORK_DIR / "tasks.json"

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

CATEGORIES = {
    'medical': '💊 Медичне',
    'personnel': '👥 Персонал',
    'equipment': '⚙️ Обладнання',
    'pm': '📊 PM/KPI',
    'production': '🏭 Ключові',
