import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Integer, Text, Enum

from app.core.database import Base, GUID


class SyncStatus(str, enum.Enum):
    running = "running"
    success = "success"
    failed = "failed"


class SyncTarget(str, enum.Enum):
    csv = "csv"
    # Kept only so historical rows stay readable. The team chose CSV files
    # over the Sheets API, which would have needed a Google Cloud service
    # account. Nothing writes this value any more.
    google_sheets = "google_sheets"


class SyncRun(Base):
    """
    One row per export attempt (weekly Celery job or manual trigger).

    Exists because the weekly job runs unattended at 06:00 Monday — without a
    record of what happened there's no way to tell "the file is missing
    because the export failed" from "the file is missing because there were no
    new leads".
    """

    __tablename__ = "sync_runs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    target = Column(Enum(SyncTarget), nullable=False, default=SyncTarget.csv)
    status = Column(Enum(SyncStatus), nullable=False, default=SyncStatus.running)

    # "celery_beat" for the scheduled run, or the email of whoever clicked
    # Export in the dashboard.
    triggered_by = Column(String, nullable=True)
    # Name of the file this run produced.
    worksheet = Column(String, nullable=True)

    rows_written = Column(Integer, default=0, nullable=False)
    rows_updated = Column(Integer, default=0, nullable=False)
    rows_skipped = Column(Integer, default=0, nullable=False)

    error = Column(Text, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<SyncRun {self.target} {self.status} +{self.rows_written}/~{self.rows_updated}>"
