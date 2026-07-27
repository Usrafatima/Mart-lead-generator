def sync_leads_to_sheets():
    """
    Stub. The teammate working on the "Database & Google Sheets Integration"
    module will implement the real export logic here (pull leads from
    PostgreSQL, push rows to Google Sheets API, mark Lead.synced_to_sheets).

    Kept here so the backend module's Celery task has a stable import path
    to call into, regardless of when that module's code lands.
    """
    raise NotImplementedError("Google Sheets sync will be implemented by the Database/Sheets module")
