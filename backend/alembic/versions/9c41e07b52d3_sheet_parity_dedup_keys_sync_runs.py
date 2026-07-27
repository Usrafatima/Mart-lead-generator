"""sheet parity columns, dedup keys, lead_ref sequence, sync_runs

Adds everything the Database & Google Sheets module needs:

  * the lead-sheet columns the team fills in by hand (business type, country,
    owner name, reviews count, call status, follow-up date, week number)
  * normalized key columns + indexes that duplicate detection matches on
  * a human-readable Lead ID backed by a Postgres sequence
  * the sync_runs audit table for the weekly export

Every added column is nullable or has a server default, so the existing bot
and API code keeps working without changes and this can be applied to a
database that already holds scraped rows.

Revision ID: 9c41e07b52d3
Revises: 78730a42a068
Create Date: 2026-07-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9c41e07b52d3'
down_revision: Union[str, Sequence[str], None] = '78730a42a068'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# create_type=False on all three: we create each type explicitly with
# .create(checkfirst=True) before it's used. Without this flag SQLAlchemy also
# emits a CREATE TYPE as part of the add_column/create_table DDL, and Postgres
# fails the second one with "type already exists". SQLite never surfaces this,
# so it only shows up against a real database.
call_status_enum = postgresql.ENUM(
    'not_contacted', 'contacted', 'no_answer', 'callback_scheduled',
    'interested', 'not_interested',
    name='callstatus',
    create_type=False,
)
sync_status_enum = postgresql.ENUM(
    'running', 'success', 'failed', name='syncstatus', create_type=False
)
sync_target_enum = postgresql.ENUM(
    'google_sheets', 'csv', name='synctarget', create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()

    # Speeds up the fuzzy name matching in app/services/dedup.py. Optional:
    # the service falls back to a Python implementation if this isn't
    # available, so don't fail the migration when the role can't create it.
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    except Exception:  # pragma: no cover - depends on DB privileges
        pass

    # --- businesses: sheet parity + dedup keys -----------------------------
    op.add_column('businesses', sa.Column('business_type', sa.String(), nullable=True))
    op.add_column('businesses', sa.Column('country', sa.String(), nullable=True))
    op.add_column('businesses', sa.Column('owner_manager_name', sa.String(), nullable=True))
    op.add_column('businesses', sa.Column('reviews_count', sa.Integer(), nullable=True))
    op.add_column('businesses', sa.Column('assigned_to', sa.String(), nullable=True))

    op.add_column(
        'businesses',
        sa.Column('website_available', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Google's own identifier for a place — the strongest dedup signal we get.
    op.add_column('businesses', sa.Column('place_id', sa.String(), nullable=True))
    op.add_column('businesses', sa.Column('maps_url', sa.String(), nullable=True))
    op.create_index(op.f('ix_businesses_place_id'), 'businesses', ['place_id'], unique=True)

    op.add_column('businesses', sa.Column('name_key', sa.String(), nullable=True))
    op.add_column('businesses', sa.Column('phone_key', sa.String(), nullable=True))
    op.add_column('businesses', sa.Column('domain_key', sa.String(), nullable=True))
    op.add_column('businesses', sa.Column('duplicate_of_id', sa.UUID(), nullable=True))

    op.create_foreign_key(
        'fk_businesses_duplicate_of_id',
        'businesses', 'businesses',
        ['duplicate_of_id'], ['id'],
    )

    # is_duplicate was nullable; dedup and the export both branch on it, and
    # NULL would silently fall out of both filters.
    op.execute("UPDATE businesses SET is_duplicate = false WHERE is_duplicate IS NULL")
    op.alter_column(
        'businesses', 'is_duplicate',
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    )

    # Backfill website_available from the website column so existing rows
    # aren't all exported as "No".
    op.execute(
        "UPDATE businesses SET website_available = true "
        "WHERE website IS NOT NULL AND btrim(website) <> ''"
    )

    op.create_index(op.f('ix_businesses_business_type'), 'businesses', ['business_type'])
    op.create_index(op.f('ix_businesses_country'), 'businesses', ['country'])
    op.create_index(op.f('ix_businesses_assigned_to'), 'businesses', ['assigned_to'])
    op.create_index(op.f('ix_businesses_name_key'), 'businesses', ['name_key'])
    op.create_index(op.f('ix_businesses_phone_key'), 'businesses', ['phone_key'])
    op.create_index(op.f('ix_businesses_domain_key'), 'businesses', ['domain_key'])
    op.create_index('ix_businesses_city_name_key', 'businesses', ['city', 'name_key'])
    op.create_index('ix_businesses_country_city', 'businesses', ['country', 'city'])

    # --- leads: human-readable id + outreach columns -----------------------
    op.execute("CREATE SEQUENCE IF NOT EXISTS lead_ref_seq START 1")

    op.add_column(
        'leads',
        sa.Column('lead_ref', sa.Integer(), nullable=True, server_default=sa.text("nextval('lead_ref_seq')")),
    )
    # Existing rows all took the same default in one statement, so number them
    # explicitly by creation order instead.
    op.execute(
        """
        UPDATE leads SET lead_ref = numbered.rn
        FROM (
            SELECT id, row_number() OVER (ORDER BY created_at NULLS FIRST, id) AS rn
            FROM leads
        ) AS numbered
        WHERE leads.id = numbered.id
        """
    )
    # Move the sequence past whatever we just assigned, so the next insert
    # doesn't collide with a backfilled number.
    op.execute("SELECT setval('lead_ref_seq', GREATEST((SELECT COALESCE(MAX(lead_ref), 0) FROM leads), 1))")

    op.create_index(op.f('ix_leads_lead_ref'), 'leads', ['lead_ref'], unique=True)

    op.add_column('leads', sa.Column('order_method_detail', sa.String(), nullable=True))
    op.add_column('leads', sa.Column('automation_status_detail', sa.String(), nullable=True))
    op.add_column('leads', sa.Column('follow_up_date', sa.Date(), nullable=True))
    op.add_column('leads', sa.Column('week_number', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_leads_week_number'), 'leads', ['week_number'])

    call_status_enum.create(bind, checkfirst=True)
    op.add_column(
        'leads',
        sa.Column(
            'call_status',
            call_status_enum,
            nullable=False,
            server_default='not_contacted',
        ),
    )

    # --- sync_runs ---------------------------------------------------------
    sync_status_enum.create(bind, checkfirst=True)
    sync_target_enum.create(bind, checkfirst=True)

    op.create_table(
        'sync_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('target', sync_target_enum, nullable=False, server_default='google_sheets'),
        sa.Column('status', sync_status_enum, nullable=False, server_default='running'),
        sa.Column('triggered_by', sa.String(), nullable=True),
        sa.Column('worksheet', sa.String(), nullable=True),
        sa.Column('rows_written', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rows_updated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rows_skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sync_runs_started_at'), 'sync_runs', ['started_at'])


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index(op.f('ix_sync_runs_started_at'), table_name='sync_runs')
    op.drop_table('sync_runs')
    sync_target_enum.drop(bind, checkfirst=True)
    sync_status_enum.drop(bind, checkfirst=True)

    op.drop_column('leads', 'call_status')
    call_status_enum.drop(bind, checkfirst=True)

    op.drop_index(op.f('ix_leads_week_number'), table_name='leads')
    op.drop_column('leads', 'week_number')
    op.drop_column('leads', 'follow_up_date')
    op.drop_column('leads', 'automation_status_detail')
    op.drop_column('leads', 'order_method_detail')

    op.drop_index(op.f('ix_leads_lead_ref'), table_name='leads')
    op.drop_column('leads', 'lead_ref')
    op.execute("DROP SEQUENCE IF EXISTS lead_ref_seq")

    op.drop_index('ix_businesses_country_city', table_name='businesses')
    op.drop_index('ix_businesses_city_name_key', table_name='businesses')
    op.drop_index(op.f('ix_businesses_domain_key'), table_name='businesses')
    op.drop_index(op.f('ix_businesses_phone_key'), table_name='businesses')
    op.drop_index(op.f('ix_businesses_name_key'), table_name='businesses')
    op.drop_index(op.f('ix_businesses_assigned_to'), table_name='businesses')
    op.drop_index(op.f('ix_businesses_country'), table_name='businesses')
    op.drop_index(op.f('ix_businesses_business_type'), table_name='businesses')
    op.drop_index(op.f('ix_businesses_place_id'), table_name='businesses')

    op.alter_column(
        'businesses', 'is_duplicate',
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )

    op.drop_constraint('fk_businesses_duplicate_of_id', 'businesses', type_='foreignkey')
    op.drop_column('businesses', 'duplicate_of_id')
    op.drop_column('businesses', 'maps_url')
    op.drop_column('businesses', 'place_id')
    op.drop_column('businesses', 'domain_key')
    op.drop_column('businesses', 'phone_key')
    op.drop_column('businesses', 'name_key')
    op.drop_column('businesses', 'website_available')
    op.drop_column('businesses', 'assigned_to')
    op.drop_column('businesses', 'reviews_count')
    op.drop_column('businesses', 'owner_manager_name')
    op.drop_column('businesses', 'country')
    op.drop_column('businesses', 'business_type')
