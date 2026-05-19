"""Thin Google Calendar wrapper.

Loads OAuth credentials from web/config/google_token.json (created by
running setup_google.py once). Exposes create_event() used by the
/api/calendar/book endpoint.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CONFIG_DIR = Path(__file__).parent / "config"
TOKEN_PATH = CONFIG_DIR / "google_token.json"
CALENDAR_ID = "primary"
TIMEZONE = "America/Montreal"
DEFAULT_DURATION_MIN = 90


def _load_credentials() -> Credentials:
    if not TOKEN_PATH.exists():
        raise RuntimeError(
            f"Missing {TOKEN_PATH}. Run `python setup_google.py` first."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds


def create_event(
    name: str,
    phone: str,
    date: str,        # YYYY-MM-DD
    time: str,        # HH:MM (24h)
    party_size: int,
    notes: str = "",
) -> dict[str, Any]:
    creds = _load_credentials()
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    tz = ZoneInfo(TIMEZONE)
    start_dt = datetime.fromisoformat(f"{date}T{time}").replace(tzinfo=tz)
    end_dt = start_dt + timedelta(minutes=DEFAULT_DURATION_MIN)

    body = {
        "summary": f"Reservation: {name} ({party_size})",
        "description": (
            f"Phone: {phone}\n"
            f"Party size: {party_size}\n"
            f"Notes: {notes or '—'}\n"
            f"Booked by Grok voice agent."
        ),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": TIMEZONE},
    }
    event = service.events().insert(calendarId=CALENDAR_ID, body=body).execute()
    return {
        "status": "confirmed",
        "event_id": event.get("id"),
        "html_link": event.get("htmlLink"),
        "start": event["start"],
        "end": event["end"],
    }
