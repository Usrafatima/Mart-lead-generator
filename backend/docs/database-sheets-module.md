# Database & Export Integration

Assigned as **"Database & Google Sheets Integration"**.
Module owner: **Haifa** (Bristol + Dubai)

Covers the five tasks assigned to this role: design the database, store leads,
remove duplicates, export the leads, and schedule the weekly job.

> **Why it's CSV and not the Sheets API:** pushing to Google Sheets needs a
> Google Cloud service account, and the team decided against setting one up.
> Exports are **CSV files** instead — same 22 columns, same data, same
> schedule, opened directly in Excel or uploaded to Sheets by hand. Nothing
> else about the module changed.

---

## What's in it

| File | Does |
|---|---|
| `app/models/business.py` | Business table — scraped data plus the lead-sheet columns |
| `app/models/lead.py` | Lead table — classification + outreach tracking |
| `app/models/sync_run.py` | Audit row per export attempt |
| `app/core/assignments.py` | Who covers which cities, and the weekly targets |
| `app/services/dedup.py` | Duplicate detection and the `upsert_business()` entry point |
| `app/services/export_mapping.py` | The single definition of the export's columns |
| `app/services/csv_export.py` | Builds the CSV, on demand and for download |
| `app/services/scheduled_export.py` | The weekly job: writes the CSV files to disk |
| `app/services/importer.py` | One-off migration of hand-filled .csv/.xlsx sheets |
| `app/services/discovery_ingest.py` | Bridge from the Google Maps bot into the database |
| `app/services/reports.py` | Weekly Lead Generation Dashboard |
| `app/api/v1/exports.py` | `/api/v1/exports/*` endpoints |
| `app/api/v1/reports.py` | `/api/v1/reports/*` endpoints |
| `scripts/discover_leads.py` | Scrape a city straight into the database |
| `scripts/import_leads.py` | CLI wrapper around the one-off importer |
| `alembic/versions/9c41e07b52d3_*.py` | Schema, dedup keys, sync_runs |
| `alembic/versions/c7d2f1a4be90_*.py` | CSV-only rename of the export timestamp |

---

## Schema

`businesses` holds one row per real-world shop. All three scraper bots write
to it; later bots enrich the same row rather than inserting a new one.

Beyond what the bots scrape, it carries the columns the team fills in by hand
— `business_type`, `country`, `owner_manager_name`, `reviews_count` — plus
three **normalized key columns** used only for matching:

| Column | Example |
|---|---|
| `name_key` | `Wai Yee Hong Chinese Supermarket Ltd.` → `chinese hong wai yee` |
| `phone_key` | `+44 117 952 4240` and `0117 952 4240` → `1179524240` |
| `domain_key` | `https://www.WaiYeeHong.com/contact` → `waiyeehong.com` |

`leads` is one-to-one with a business, created once the AI service classifies
it. `lead_ref` is a short sequential number (the sheet's "Lead ID") backed by
a Postgres sequence — UUIDs are unreadable in a spreadsheet, and it doubles as
the key the export upserts on.

`order_method` stays as the AI service's four-value enum for filtering;
`order_method_detail` keeps the sheet's original wording ("Walk-in +
Delivery") for display. Widening the enum would have broken the AI
Classification Service's contract.

`sync_runs` records every export attempt. Without it there's no way to tell
"the sheet is empty because the sync failed" from "the sheet is empty because
there were no new leads".

---

## Duplicate detection

**Every bot should insert via `upsert_business()`, not `db.add(Business(...))`.**

```python
from app.services.dedup import upsert_business

business, created = upsert_business(db, Business(name=..., city=..., phone=...))
if created:
    queue_ai_classification(business.id)
```

Matching, cheapest check first:

0. **Google `place_id`** — Google's own identifier for the physical location.
   Definitive when both records have one; only the Maps bot supplies it.
1. **Phone**, corroborated. A shared direct line is strong evidence, but it
   needs two guards, both learned from the team's real sheets:
   - chain-wide **service numbers are ignored entirely** (`is_shared_line`).
     Tesco's `0345…`, Heron and ALDI's `0800…`, and Al Fatah's Pakistani UAN
     `042-111-933-933` are published by every branch. Without this, the UAN
     merged two Al Fatah branches 300 km apart.
   - the **city must match and the names be loosely similar** (≥ 0.45).
     Usman's sheet has one number typed against two different Rawalpindi
     shops; merging them silently destroyed a real lead.
2. **Website domain**, same city. Chains share a domain across branches, so
   the city has to agree too.
3. **Exact normalized name**, same city.
4. **Fuzzy name**, same city, at or above `NAME_SIMILARITY_THRESHOLD` (0.82).

The fuzzy score is the higher of character similarity (catches typos, "Baqer"
/ "Bager") and token containment (catches extra words, "Wai Yee Hong" vs "Wai
Yee Hong Chinese"). Containment is ignored for one-word names so "Mini Market"
doesn't swallow "Mini Super".

Duplicates are **flagged, never deleted**: `is_duplicate=True` and
`duplicate_of_id` points at the survivor. Fuzzy matching will occasionally be
wrong, and this makes undoing a bad merge a one-line UPDATE. Exports filter
them out.

Merging only ever **fills blanks**. A scraper must not overwrite a value
someone corrected in the dashboard.

If the threshold is retuned, or rows were inserted before this module existed,
re-scan everything:

```python
from app.services.dedup import backfill_duplicates
backfill_duplicates(db)   # or the backfill_duplicate_businesses Celery task
```

---

## Export

Everything exports as CSV, and every path shares
`export_mapping.SHEET_COLUMNS`, so the on-demand download, the scheduled file
and the dashboard can never drift into different column orders.

Files are written with a UTF-8 BOM. Without it Excel on Windows falls back to
the system codepage and mangles accented and Arabic business names.

| Endpoint | Who | Does |
|---|---|---|
| `GET /api/v1/exports/csv` | any logged-in user | immediate CSV download, honours the dashboard's filters |
| `POST /api/v1/exports/weekly-file` | owner only | queues the weekly file now, instead of waiting for Monday |
| `GET /api/v1/exports/runs` | any logged-in user | export history — this is how you check Monday's job ran |
| `GET /api/v1/reports/weekly` | any logged-in user | the full weekly dashboard as JSON |
| `GET /api/v1/reports/weekly/csv` | any logged-in user | the dashboard as a CSV download |
| `GET /api/v1/reports/weekly/interns` | any logged-in user | just the per-intern progress table |
| `GET /api/v1/reports/assignments` | any logged-in user | intern → cities mapping and targets |

`GET /exports/csv` streams inline for an instant download.
`POST /exports/weekly-file` is queued through Celery instead, because writing
every lead to disk would otherwise hold the HTTP request open. It retries at
60s / 120s / 240s, since the usual failure is transient and the next scheduled
attempt is a week away.

### Scheduled jobs

In `app/workers/celery_worker.py`:

| Job | When | Writes |
|---|---|---|
| `export_leads_csv` | daily 06:00 UTC | `exports/leads_week<NN>.csv` |
| `export_dashboard_csv` | daily 06:15 UTC | `exports/dashboard_week<NN>.csv` |

Files are named by ISO week, not by timestamp, so re-running the same week
overwrites rather than piling up near-identical files.

Both jobs run **daily**, but the output is still one file per week — which is
the weekly artefact the requirement asks for. Running daily just means the
current week's file is never more than a day old; a Monday-only schedule left
it six days stale by Sunday, which is no use for chasing targets mid-week.

The original Monday 06:00 schedule was written by the backend module; this
module filled in the task body it was calling.

Output goes to `EXPORT_DIR` (default `backend/exports/`, gitignored — it's
generated output, not source).

---

## Weekly Dashboard

`GET /api/v1/reports/weekly` reproduces the spreadsheet dashboard the team was
maintaining with `WEEKNUM` + `COUNTIFS` formulas — the one that showed
`#VALUE!` for every intern because it depended on eight people typing a column
consistently.

Four sections: headline (this week vs the 100/week target), by country, by
intern, and by business type (all time).

Every tracked intern, country and business type is always present, at zero if
there's no data. A progress report that omits the person with no leads is
worse than useless.

Leads are credited to an intern by their explicit `assigned_to`, falling back
to whoever owns the city in `app/core/assignments.py` — the scraper bots know
which city they searched but not who asked for it. Duplicates never count
towards a target; padding the numbers is what this project exists to stop.

---

## Adding a new city

Nothing is hardcoded per city, so a new market is an argument, not a code
change:

```bash
cd backend
python -m scripts.discover_leads --city "Karachi" --category "supermarket"
```

That runs the Google Maps bot, then pushes its results straight into Postgres
through `upsert_business()`. The bot only wrote CSV files before — this is the
bridge its docstring asked for.

Add the city to `INTERNS` in `app/core/assignments.py` so its leads count
towards someone's weekly target; otherwise the script warns and the leads are
stored unattributed.

Needs Playwright browsers: `playwright install chromium`. Note the project's
Dockerfile doesn't install them yet — that's the scraping module's file.

---

## Importing an existing sheet (one-off migration)

**This is not how the system runs.** Leads come from the discovery bot; this
exists only to carry across work done in spreadsheets before the system
existed, so none of it is lost.

```bash
cd backend
python -m scripts.import_leads "C:/path/to/old_leads.xlsx" --assigned-to Haifa
python -m scripts.import_leads old_leads.csv --dry-run   # parse, don't save
```

Rows go through `upsert_business()`, so re-importing the same file — or
importing two people's sheets that overlap — merges instead of duplicating.
Headers are matched case-insensitively with common variants aliased.

No spreadsheets are kept in the repo. The parsing quirks the team's real
sheets exposed are pinned down in `tests/test_sheet_cleaning.py` instead:

| Problem seen in real sheets | Handling |
|---|---|
| Phones mangled by Excel to `4.41317E+11` | Imported blank. The digits are unrecoverable, and a wrong number looks callable and lets dedup match unrelated shops. Format phone columns as **Text** before typing. |
| One phone typed against two different shops | Not merged, thanks to the name-corroboration guard |
| `nan`, `To Verify`, `unkown`, `—`, `Not listed`, `TBD` | Treated as blank, not stored as text |
| Week written as `30`, `52`, `Week 1`, `week1` | Normalised to an integer |
| Review counts as `120+`, `800+` | Parsed as the number |
| Lead IDs as `L-LON-001` | Ignored; the database assigns its own |
| `Contacted – Interested` (en dash), `Attempted – No Answer` | Mapped to the right status |
| `Manual (likely)`, `Semi-Automated?` | Mapped to the right status |

---

## Running it

```bash
cd backend
cp .env.example .env
docker compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload
```

Populate it by discovering leads, not by importing a sheet:

```bash
python -m scripts.discover_leads --city Bristol --category "mini mart"
```

Tests need no services running — they use in-memory SQLite:

```bash
pytest tests -q
```

---

## Notes for the rest of the team

- **Bots**: please call `upsert_business()` instead of inserting directly, or
  duplicate detection can't see your rows until someone runs the backfill.
  The Maps bot can also go straight in via `scripts/discover_leads.py`.
- **Frontend**: `GET /api/v1/exports/csv` accepts `city`, `country`,
  `priority`, `week_number` — the same filters as the leads table.
  `GET /api/v1/reports/weekly` returns the dashboard ready to render.
- **AI service**: your `LeadClassifyInput` contract is unchanged. Every column
  added here is nullable or defaulted.

### Two issues found outside this module

Flagged rather than fixed, since they belong to other people's files:

1. **`alembic/versions/78730a42a068` (initial migration)** — its `downgrade()`
   drops the tables but not the `userrole` enum type, so a
   `downgrade base` → `upgrade head` cycle fails with *"type userrole already
   exists"*. The fix is one line: `sa.Enum(name='userrole').drop(op.get_bind())`
   at the end of `downgrade()`.
2. **`requirements.txt` was missing the scraper dependencies** —
   `beautifulsoup4`, `requests`, `lxml` and `playwright` are imported by
   `app/bots/` but weren't pinned, so a clean `pip install -r requirements.txt`
   produced an app that couldn't start (`ModuleNotFoundError: No module named
   'bs4'` on importing `app.main`). Added here, since nothing runs without it.
