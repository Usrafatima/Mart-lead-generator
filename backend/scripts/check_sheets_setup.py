"""
Verify the Google Sheets setup, step by step, without writing any lead data.

    python -m scripts.check_sheets_setup

Checks each thing that can go wrong independently and says exactly which one
failed and how to fix it — rather than the single opaque error the Google
client raises. Safe to run repeatedly; the only write is one cell in a
scratch tab, which it removes afterwards.
"""

from __future__ import annotations

import json
import os
import sys

from app.core.config import settings

OK = "  [OK]  "
FAIL = " [FAIL] "
WARN = " [WARN] "


def _fail(message: str, fix: str) -> bool:
    print(f"{FAIL}{message}")
    print(f"         Fix: {fix}")
    return False


def check_packages() -> bool:
    try:
        import gspread  # noqa: F401
        from google.oauth2.service_account import Credentials  # noqa: F401
    except ImportError as exc:
        return _fail(
            f"Google client libraries not installed ({exc})",
            "pip install -r requirements.txt",
        )
    print(f"{OK}gspread and google-auth are installed")
    return True


def check_spreadsheet_id() -> bool:
    if not settings.GOOGLE_SHEETS_SPREADSHEET_ID:
        return _fail(
            "GOOGLE_SHEETS_SPREADSHEET_ID is empty",
            "Copy the id from the sheet URL "
            "(docs.google.com/spreadsheets/d/<THIS PART>/edit) into backend/.env",
        )
    print(f"{OK}Spreadsheet id is set ({settings.GOOGLE_SHEETS_SPREADSHEET_ID[:12]}...)")
    return True


def check_credentials_file() -> tuple[bool, str | None]:
    path = settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH
    if not path:
        return _fail(
            "GOOGLE_SERVICE_ACCOUNT_JSON_PATH is empty",
            "Set it in backend/.env to where you saved the service account JSON",
        ), None

    if not os.path.exists(path):
        return _fail(
            f"No credentials file at {path}",
            "Download the service account key (docs/google-sheets-setup.md step 3) "
            "and save it there. If running outside Docker, the path is usually "
            "'secrets/google_service_account.json' rather than '/app/secrets/...'.",
        ), None

    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return _fail(
            f"Credentials file at {path} isn't valid JSON ({exc})",
            "Re-download the key — the file is probably truncated",
        ), None

    email = data.get("client_email")
    if not email:
        return _fail(
            "Credentials file has no 'client_email'",
            "You may have downloaded an OAuth client id instead of a service "
            "account key. Redo step 3 of docs/google-sheets-setup.md.",
        ), None

    print(f"{OK}Credentials file found, service account: {email}")
    return True, email


def check_can_open_spreadsheet(service_account_email: str | None) -> bool:
    import gspread
    from google.oauth2.service_account import Credentials

    from app.services.sheets_client import SCOPES

    try:
        credentials = Credentials.from_service_account_file(
            settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH, scopes=SCOPES
        )
        client = gspread.authorize(credentials)
        spreadsheet = client.open_by_key(settings.GOOGLE_SHEETS_SPREADSHEET_ID)
    except gspread.SpreadsheetNotFound:
        return _fail(
            "The service account can't see that spreadsheet",
            f"Open the sheet, click Share, and give Editor access to "
            f"{service_account_email or 'the service account email above'}. "
            f"This is the most common setup mistake.",
        )
    except Exception as exc:
        message = str(exc)
        if "has not been used" in message or "disabled" in message:
            return _fail(
                "The Sheets or Drive API isn't enabled for this project",
                "Enable both at console.cloud.google.com (step 2 of the setup guide)",
            )
        return _fail(f"Couldn't open the spreadsheet: {type(exc).__name__}: {exc}", "See the error above")

    print(f"{OK}Opened spreadsheet: {spreadsheet.title!r}")

    try:
        tabs = [ws.title for ws in spreadsheet.worksheets()]
        print(f"{OK}Existing tabs: {', '.join(tabs)}")
    except Exception:
        pass

    return True


def check_can_write() -> bool:
    import gspread
    from google.oauth2.service_account import Credentials

    from app.services.sheets_client import SCOPES

    credentials = Credentials.from_service_account_file(
        settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH, scopes=SCOPES
    )
    spreadsheet = gspread.authorize(credentials).open_by_key(
        settings.GOOGLE_SHEETS_SPREADSHEET_ID
    )

    scratch = "_leadgen_write_test"
    worksheet = None
    try:
        worksheet = spreadsheet.add_worksheet(title=scratch, rows=2, cols=2)
        worksheet.update(range_name="A1", values=[["write test ok"]])
        print(f"{OK}Write access confirmed")
        return True
    except Exception as exc:
        message = str(exc)
        if "permission" in message.lower() or "403" in message:
            return _fail(
                "The service account can read but not write",
                "Re-share the sheet with Editor (not Viewer) access",
            )
        return _fail(f"Write test failed: {type(exc).__name__}: {exc}", "See the error above")
    finally:
        if worksheet is not None:
            try:
                spreadsheet.del_worksheet(worksheet)
            except Exception:
                print(f"{WARN}Couldn't remove the '{scratch}' test tab — delete it by hand")


def main() -> int:
    print("Checking Google Sheets setup\n")

    if settings.SHEETS_DRY_RUN:
        print(f"{WARN}SHEETS_DRY_RUN is true — exports will not write to Google")
        print("         Set SHEETS_DRY_RUN=false in backend/.env when you're ready\n")

    if not check_packages():
        return 1

    id_ok = check_spreadsheet_id()
    creds_ok, email = check_credentials_file()

    if not (id_ok and creds_ok):
        print("\nSetup incomplete — the export will run in dry-run mode until this is fixed.")
        print("See backend/docs/google-sheets-setup.md")
        return 1

    if not check_can_open_spreadsheet(email):
        return 1
    if not check_can_write():
        return 1

    print("\nAll checks passed. Google Sheets export is ready to use:")
    print("  python -c \"from app.services.sheets_sync import sync_leads_to_sheets; "
          "print(sync_leads_to_sheets(triggered_by='manual'))\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
