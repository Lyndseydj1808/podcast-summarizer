from datetime import datetime, timezone

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from . import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Assumes a tab named "Sheet1" (Google's default name for a new sheet) with
# four columns: Show, Episode, Summary, Date Processed.
APPEND_RANGE = "Sheet1!A:D"


class SheetsError(Exception):
    """Raised when writing to the Google Sheet fails, with a message describing
    what specifically went wrong."""


def _get_access_token() -> str:
    """Use the service account's private key to obtain a short-lived access token.
    Google's own library handles the actual cryptographic signing here, we just
    hand it the key file and scopes."""
    if not config.GOOGLE_SERVICE_ACCOUNT_PATH:
        raise SheetsError("GOOGLE_SERVICE_ACCOUNT_FILE isn't set in .env yet")

    try:
        credentials = service_account.Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_PATH, scopes=SCOPES
        )
        credentials.refresh(Request())
    except FileNotFoundError as e:
        raise SheetsError(f"Couldn't find the service account key file at {config.GOOGLE_SERVICE_ACCOUNT_PATH}") from e
    except Exception as e:
        raise SheetsError(f"Couldn't authenticate with Google: {e}") from e

    return credentials.token


def append_summary_row(show_name: str, episode_name: str, summary: str) -> None:
    """Add a new row to the Google Sheet with an episode's summary."""
    if not config.GOOGLE_SHEET_ID:
        raise SheetsError("GOOGLE_SHEET_ID isn't set in .env yet")

    access_token = _get_access_token()
    processed_at = datetime.now(timezone.utc).isoformat()

    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{config.GOOGLE_SHEET_ID}"
        f"/values/{APPEND_RANGE}:append"
    )

    try:
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
            json={"values": [[show_name, episode_name, summary, processed_at]]},
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise SheetsError(
            f"Google Sheets rejected this request ({e.response.status_code}): {e.response.text[:300]}"
        ) from e
    except httpx.RequestError as e:
        raise SheetsError(f"Couldn't reach Google Sheets: {e}") from e
