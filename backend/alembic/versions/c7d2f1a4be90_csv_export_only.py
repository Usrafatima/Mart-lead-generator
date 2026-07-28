"""csv export only: rename synced_to_sheets, default sync target to csv

The team decided against the Google Sheets API (it needs a Google Cloud
service account) and settled on CSV files instead. This drops the
Sheets-specific naming from the schema:

  * leads.synced_to_sheets -> leads.exported_at, since nothing syncs to
    Sheets any more and the old name would mislead whoever reads it next.
  * sync_runs.target now defaults to 'csv'.

The 'google_sheets' value is deliberately left in the synctarget enum.
Removing a value from a Postgres enum means recreating the type and rewriting
every dependent column, which is real risk for no benefit — and it keeps
historical rows readable if Sheets is ever revisited.

Revision ID: c7d2f1a4be90
Revises: 9c41e07b52d3
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d2f1a4be90'
down_revision: Union[str, Sequence[str], None] = '9c41e07b52d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A rename rather than drop-and-add, so any export timestamps already
    # recorded survive.
    op.alter_column('leads', 'synced_to_sheets', new_column_name='exported_at')

    op.alter_column(
        'sync_runs', 'target',
        existing_type=sa.Enum('google_sheets', 'csv', name='synctarget'),
        server_default='csv',
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'sync_runs', 'target',
        existing_type=sa.Enum('google_sheets', 'csv', name='synctarget'),
        server_default='google_sheets',
        existing_nullable=False,
    )
    op.alter_column('leads', 'exported_at', new_column_name='synced_to_sheets')
