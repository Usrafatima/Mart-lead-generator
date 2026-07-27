# Google Sheets setup

The export works **without** any of this — with no credentials configured it
runs in dry-run mode, doing everything except the final write and logging each
row it would have sent. Follow this only when you want rows to actually land in
a real spreadsheet.

Takes about five minutes. You need a Google account.

---

## 1. Create a Google Cloud project

1. Go to <https://console.cloud.google.com/>
2. Project dropdown (top left) → **New Project**
3. Name it `mart-lead-generator` → **Create**

## 2. Enable the two APIs

With the project selected, enable both:

- <https://console.cloud.google.com/apis/library/sheets.googleapis.com> → **Enable**
- <https://console.cloud.google.com/apis/library/drive.googleapis.com> → **Enable**

Drive is needed as well as Sheets — without it the client can't open a
spreadsheet it didn't create.

## 3. Create a service account

A service account is a robot Google account. The Celery worker runs
unattended at 06:00 on Mondays, so it can't use a login that needs a human to
click "Allow".

1. **APIs & Services → Credentials → Create Credentials → Service account**
2. Name: `leadgen-sheets-writer` → **Create and continue** → **Done**
   (no roles needed — access is granted per-spreadsheet in step 5)
3. Click the new service account → **Keys** tab → **Add key → Create new key**
4. Choose **JSON** → **Create**. A `.json` file downloads.

**Treat that file like a password.** It grants write access to any sheet it's
been shared with. Never commit it.

## 4. Put the key where the app expects it

```bash
mkdir -p backend/secrets
mv ~/Downloads/mart-lead-generator-*.json backend/secrets/google_service_account.json
```

`backend/secrets/` is gitignored.

## 5. Share the spreadsheet with the service account

1. Open `backend/secrets/google_service_account.json` and copy the
   `"client_email"` value — it looks like
   `leadgen-sheets-writer@mart-lead-generator.iam.gserviceaccount.com`
2. Create (or open) the Google Sheet the team will use
3. **Share** → paste that email → give it **Editor** → **Send**

Skipping this step is the single most common cause of a `SpreadsheetNotFound`
error. The service account can only see sheets explicitly shared with it.

## 6. Configure the app

Grab the spreadsheet id from its URL:

```
https://docs.google.com/spreadsheets/d/1AbC...XyZ/edit
                                      ^^^^^^^^^^^ this part
```

In `backend/.env`:

```ini
GOOGLE_SHEETS_SPREADSHEET_ID=1AbC...XyZ
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=/app/secrets/google_service_account.json
GOOGLE_SHEETS_WORKSHEET=Leads
SHEETS_DRY_RUN=false
```

The path is `/app/secrets/...` when running under Docker (the backend mounts
itself at `/app`). Running uvicorn directly instead, use a local path such as
`secrets/google_service_account.json`.

## 7. Verify

```bash
cd backend
python -c "from app.services.sheets_sync import sync_leads_to_sheets; print(sync_leads_to_sheets(triggered_by='manual-test'))"
```

Expected: a summary dict with `"dry_run": False` and a non-zero row count, and
the rows visible in the sheet. If it says `"dry_run": True`, credentials
weren't picked up — re-check steps 4 and 6.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| `"dry_run": true` in the result | Spreadsheet id blank, or the JSON file isn't at the configured path |
| `SpreadsheetNotFound` | Step 5 skipped — the sheet isn't shared with the service account |
| `403 Google Sheets API has not been used` | Step 2 skipped, or the wrong project is selected |
| `Quota exceeded` | Google allows 60 write requests/minute. The export batches all new rows into one call, but a very large first run can still hit it. The Celery task retries automatically at 60s, 120s, 240s. |
| Rows appended twice | Only possible if the `Lead ID` column was edited or reordered by hand — that's the key the upsert matches on. |
