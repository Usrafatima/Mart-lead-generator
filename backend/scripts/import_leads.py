"""
Load a lead sheet (.csv / .xlsx) into PostgreSQL.

    python -m scripts.import_leads data/sample_leads.csv
    python -m scripts.import_leads "C:/path/to/Bristol_Dubai.xlsx" --assigned-to Haifa
    python -m scripts.import_leads data/sample_leads.csv --dry-run

Run from the backend/ directory. Safe to re-run: rows are matched against
existing businesses and merged rather than duplicated.
"""

from __future__ import annotations

import argparse
import logging
import sys

from app.core.database import SessionLocal
from app.services.dedup import backfill_duplicates, ensure_pg_trgm
from app.services.importer import import_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a lead sheet into PostgreSQL")
    parser.add_argument("path", help="Path to a .csv or .xlsx lead sheet")
    parser.add_argument(
        "--assigned-to",
        default=None,
        help="Intern name to tag every row with (overrides an 'Assigned To' column)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and match everything, then roll back without saving",
    )
    parser.add_argument(
        "--backfill-duplicates",
        action="store_true",
        help="After importing, re-scan the whole table for duplicates",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    db = SessionLocal()
    try:
        ensure_pg_trgm(db)
        summary = import_file(db, args.path, assigned_to=args.assigned_to)

        if args.backfill_duplicates and not args.dry_run:
            summary["backfilled_duplicates"] = backfill_duplicates(db)

        if args.dry_run:
            db.rollback()
            print("DRY RUN — nothing was saved")

        print(
            f"created={summary['created']} "
            f"merged={summary['merged_as_duplicate']} "
            f"skipped={summary['skipped']}"
        )
        return 0

    except Exception as exc:
        db.rollback()
        print(f"Import failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
