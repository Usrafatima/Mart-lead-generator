# Database & Google Sheets Integration

Module owner: **Haifa** (Bristol + Dubai)

Covers the four tasks assigned to this role: design the database, store leads,
remove duplicates, export to Google Sheets, and schedule the weekly job.

---

## What's in it

| File | Does |
|---|---|
| `app/models/business.py` | Business table — scraped data plus the lead-sheet columns |
| `app/models/lead.py` | Lead table — classification + outreach tracking |
| `app/models/sync_run.py` | Audit row per export attempt |
| `app/core/assignments.py` | Who covers which cities, and the weekly targets |
| `app/services/dedup.py` | Duplicate detection and the `upsert_business()` entry point |
| `app/services/export_mapping.py` | The single definition of the sheet's columns |
| `app/services/sheets_client.py` | Google Sheets wrapper + dry-run backend |
| `app/services/sheets_sync.py` | The leads export and the dashboard export |
| `app/services/csv_export.py` | CSV download for the dashboard |
| `app/services/importer.py` | Loads hand-filled .csv/.xlsx sheets into Postgres |
| `app/services/discovery_ingest.py` | Bridge from the Google Maps bot into the database |
| `app/services/reports.py` | Weekly Lead Generation Dashboard |
| `app/api/v1/exports.py` | `/api/v1/exports/*` endpoints |
| `app/api/v1/reports.py` | `/api/v1/reports/*` endpoints |
| `scripts/import_leads.py` | CLI wrapper around the importer |
| `scripts/discover_leads.py` | Scrape a city straight into the database |
| `scripts/check_sheets_setup.py` | Verifies Google credentials, step by step |
| `alembic/versions/9c41e07b52d3_*.py` | Migration for all of the above |

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

Both exports share `export_mapping.SHEET_COLUMNS`, so CSV and Sheets can never
drift into different column orders.

The Sheets export is an **idempotent upsert keyed on Lead ID**, not an append.
Re-running the weekly job, or clicking Export twice, updates existing rows
instead of duplicating them — which also means edits made since the last run
get picked up.

| Endpoint | Who | Does |
|---|---|---|
| `GET /api/v1/exports/csv` | any logged-in user | CSV download, honours the dashboard's filters |
| `POST /api/v1/exports/sheets` | owner only | queues a Sheets export now |
| `GET /api/v1/exports/runs` | any logged-in user | export history — this is how you check Monday's job ran |
| `GET /api/v1/reports/weekly` | any logged-in user | the full weekly dashboard |
| `GET /api/v1/reports/weekly/interns` | any logged-in user | just the per-intern progress table |
| `GET /api/v1/reports/assignments` | any logged-in user | intern → cities mapping and targets |
| `POST /api/v1/reports/weekly/sync-to-sheets` | owner only | rebuilds the dashboard tab |

The Sheets export is queued through Celery rather than run inline: a full
export can take a minute against Google's API and would otherwise hold the
HTTP request open until the browser times out. It retries at 60s / 120s / 240s,
because the usual failure is a transient quota error and the next scheduled
attempt is a week away.

### Scheduled jobs

In `app/workers/celery_worker.py`:

| Job | When | Does |
|---|---|---|
| `sync_leads_to_sheets` | Mondays 06:00 UTC | full leads export |
| `sync_dashboard_to_sheets` | daily 06:15 UTC | rebuilds the dashboard tab |

The Monday schedule was written by the backend module; this module filled in
the task body it was calling and added the dashboard job. The dashboard runs
daily rather than weekly because a progress report six days stale can't be
acted on.

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

Needs Playwright browsers: `playwright install chromium`.

### Without credentials

The export falls back to dry-run: it runs the full pipeline and logs every row
it would have written, instead of crash-looping in Celery. See
[google-sheets-setup.md](google-sheets-setup.md) to switch it on for real.

---

## Importing an existing sheet

```bash
cd backend
python -m scripts.import_leads data/sample_leads.csv --assigned-to Haifa
python -m scripts.import_leads "C:/path/to/Bristol_Dubai.xlsx" --assigned-to Haifa
python -m scripts.import_leads data/sample_leads.csv --dry-run   # parse, don't save
```

Rows go through `upsert_business()`, so re-importing the same file — or
importing two interns' sheets that overlap — merges instead of duplicating.
Headers are matched case-insensitively with common variants aliased, and
`"N/A"` / `"Not Available"` become NULL rather than literal strings.

`data/` holds every intern's sheet collected so far:

| File | Intern | Cities | Rows |
|---|---|---|---|
| `sample_leads.csv` | Haifa | Bristol, Dubai | 15 |
| `leads_inza_london_dammam.csv` | Inza | London | 5 (partial) |
| `leads_abdulbasit_manchester_leeds.csv` | Abdul Basit | Manchester, Leeds | 16 |
| `leads_usman_islamabad_rawalpindi.csv` | Usman | Islamabad, Rawalpindi | 16 |
| `leads_aiza_lahore_faisalabad.csv` | Aiza | Lahore, Faisalabad | 16 |

Load them all:

```bash
python -m scripts.import_leads data/sample_leads.csv --assigned-to Haifa
python -m scripts.import_leads data/leads_inza_london_dammam.csv --assigned-to Inza
python -m scripts.import_leads data/leads_abdulbasit_manchester_leeds.csv --assigned-to "Abdul Basit"
python -m scripts.import_leads data/leads_usman_islamabad_rawalpindi.csv --assigned-to Usman
python -m scripts.import_leads data/leads_aiza_lahore_faisalabad.csv --assigned-to Aiza
```

That yields **65 businesses** — 68 rows minus the shared `ABC Mart` template
row, which appears in four sheets and collapses to one lead.

Still missing: Fajar (Birmingham, Liverpool), Fatima (Abu Dhabi, Sharjah),
Kristina (Karachi, Riyadh), and Inza's Dammam half.

### Known data problems in the source sheets

The importer handles these rather than failing, but they're worth fixing at
source:

| Problem | Where | Handling |
|---|---|---|
| Phones mangled to `4.41317E+11` | Abdul Basit, Inza | Imported blank — the digits are unrecoverable and a wrong number is worse than none. Re-enter the column as **text** in Excel. |
| One phone on two different shops | Usman (C-Mart / Save Mart) | Not merged, thanks to the name-corroboration guard |
| `nan`, `To Verify`, `unkown`, `—`, `Not listed` | all sheets | Treated as blank |
| Week written as `30`, `52`, `Week 1`, `week1` | all sheets | Normalised to an integer |
| Review counts as `120+`, `800+` | Abdul Basit | Parsed as the number |
| Lead IDs as `L-LON-001` | Inza | Ignored; the database assigns its own sequential Lead ID |

---

## Running it

```bash
cd backend
cp .env.example .env
docker compose up -d db redis
alembic upgrade head
python -m scripts.import_leads data/sample_leads.csv --assigned-to Haifa
uvicorn app.main:app --reload
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
