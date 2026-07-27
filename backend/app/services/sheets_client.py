"""
Thin wrapper over the Google Sheets API.

Isolated from sync_leads_to_sheets() so the export logic can be tested without
a network call or credentials — tests (and local runs before the service
account exists) use DryRunSheet, which records what would have been written.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Protocol

from app.core.config import settings

logger = logging.getLogger(__name__)

# Read+write on Sheets, and Drive metadata so gspread can open a spreadsheet
# by title as well as by key.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetBackend(Protocol):
    """What the sync logic needs from a spreadsheet tab."""

    def read_column(self, col: int) -> list[str]: ...
    def ensure_header(self, header: list[str]) -> None: ...
    def append_rows(self, rows: list[list[str]]) -> None: ...
    def update_row(self, row_number: int, values: list[str]) -> None: ...
    def replace_all(self, rows: list[list[str]]) -> None: ...


class SheetsUnavailable(RuntimeError):
    """Raised when credentials or the spreadsheet id are missing/invalid."""


class DryRunSheet:
    """
    Stand-in backend that writes nothing and logs everything.

    Lets the whole weekly pipeline — query, dedup filter, row mapping,
    SyncRun bookkeeping — run and be verified before anyone sets up Google
    Cloud. Swap in the real backend by setting GOOGLE_SHEETS_SPREADSHEET_ID
    and the service account path; no code change needed.
    """

    def __init__(self, existing_ids: Optional[list[str]] = None) -> None:
        self.header: list[str] = []
        self.appended: list[list[str]] = []
        self.updated: dict[int, list[str]] = {}
        self.replaced: list[list[str]] = []
        self._existing_ids = existing_ids or []

    def read_column(self, col: int) -> list[str]:
        return list(self._existing_ids)

    def ensure_header(self, header: list[str]) -> None:
        self.header = list(header)
        logger.info("[dry-run] header: %s", " | ".join(header))

    def append_rows(self, rows: list[list[str]]) -> None:
        self.appended.extend(rows)
        for row in rows:
            logger.info("[dry-run] append: %s", row)

    def update_row(self, row_number: int, values: list[str]) -> None:
        self.updated[row_number] = values
        logger.info("[dry-run] update row %s: %s", row_number, values)

    def replace_all(self, rows: list[list[str]]) -> None:
        self.replaced = list(rows)
        logger.info("[dry-run] replace tab with %s row(s)", len(rows))


class GoogleSheet:
    """Real Google Sheets tab, backed by gspread."""

    def __init__(self, worksheet, column_count: int) -> None:
        self._ws = worksheet
        self._column_count = column_count

    def read_column(self, col: int) -> list[str]:
        return self._ws.col_values(col)

    def ensure_header(self, header: list[str]) -> None:
        current = self._ws.row_values(1)
        if current == header:
            return
        # Widen the sheet first if it has fewer columns than we're about to
        # write, otherwise the update silently truncates.
        if self._ws.col_count < len(header):
            self._ws.add_cols(len(header) - self._ws.col_count)
        self._ws.update(
            range_name=self._a1_range(1, len(header)),
            values=[header],
        )

    def append_rows(self, rows: list[list[str]]) -> None:
        if not rows:
            return
        # USER_ENTERED so numbers and dates land as real values rather than
        # text, which is what makes the sheet sortable for the team.
        self._ws.append_rows(rows, value_input_option="USER_ENTERED")

    def update_row(self, row_number: int, values: list[str]) -> None:
        self._ws.update(
            range_name=self._a1_range(row_number, len(values)),
            values=[values],
            value_input_option="USER_ENTERED",
        )

    def replace_all(self, rows: list[list[str]]) -> None:
        """
        Overwrite the whole tab. Used for the dashboard, which is fully
        recomputed each run rather than upserted row by row.
        """
        self._ws.clear()
        if not rows:
            return

        # Rows are ragged (section headers are 1 cell, data rows are 5), and
        # the Sheets API rejects a jagged range — pad to the widest row.
        width = max(len(row) for row in rows)
        padded = [list(row) + [""] * (width - len(row)) for row in rows]

        if self._ws.col_count < width:
            self._ws.add_cols(width - self._ws.col_count)
        if self._ws.row_count < len(padded):
            self._ws.add_rows(len(padded) - self._ws.row_count)

        self._ws.update(
            range_name=f"A1:{_column_letter(width)}{len(padded)}",
            values=padded,
            value_input_option="USER_ENTERED",
        )

    @staticmethod
    def _a1_range(row: int, width: int) -> str:
        return f"A{row}:{_column_letter(width)}{row}"


def _column_letter(index: int) -> str:
    """1 -> A, 26 -> Z, 27 -> AA."""
    letters = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def open_worksheet(worksheet_name: str, column_count: int) -> SheetBackend:
    """
    Open (or create) a tab in the configured spreadsheet.

    Falls back to DryRunSheet when Sheets isn't configured, so a missing
    service account degrades the weekly job to a no-op with a warning instead
    of a crash loop in Celery.
    """
    spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
    creds_path = settings.GOOGLE_SERVICE_ACCOUNT_JSON_PATH

    if settings.SHEETS_DRY_RUN:
        logger.warning("SHEETS_DRY_RUN is on — export will not touch Google Sheets")
        return DryRunSheet()

    if not spreadsheet_id or not creds_path or not os.path.exists(creds_path):
        logger.warning(
            "Google Sheets not configured (spreadsheet_id=%s, creds_exists=%s) — "
            "falling back to dry run. See backend/docs/google-sheets-setup.md",
            bool(spreadsheet_id),
            bool(creds_path) and os.path.exists(creds_path or ""),
        )
        return DryRunSheet()

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError as exc:  # pragma: no cover - depends on install state
        raise SheetsUnavailable(
            "gspread/google-auth not installed. Run: pip install -r requirements.txt"
        ) from exc

    credentials = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(credentials)
    spreadsheet = client.open_by_key(spreadsheet_id)

    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=worksheet_name, rows=200, cols=max(column_count, 26)
        )

    return GoogleSheet(worksheet, column_count)
