"""One-time OAuth flow for Google Calendar.

Prereqs:
  1. Go to https://console.cloud.google.com/
  2. Create (or pick) a project, enable the "Google Calendar API".
  3. APIs & Services → Credentials → Create Credentials → OAuth client ID
     → Application type: "Desktop app".
  4. Download the JSON, save it as web/config/google_oauth_client.json
  5. Run:    python setup_google.py
     A browser opens, you grant access, the token is saved.
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

CONFIG_DIR = Path(__file__).parent / "web" / "config"
CLIENT_PATH = CONFIG_DIR / "google_oauth_client.json"
TOKEN_PATH = CONFIG_DIR / "google_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def main() -> None:
    if not CLIENT_PATH.exists():
        raise SystemExit(
            f"Place your OAuth desktop client JSON at {CLIENT_PATH} first.\n"
            "See instructions at the top of this file."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved token → {TOKEN_PATH}")


if __name__ == "__main__":
    main()
