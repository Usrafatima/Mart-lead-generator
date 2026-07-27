from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central app configuration. Values are loaded from environment variables
    (or a .env file locally). Every other module in the app should import
    `settings` from here instead of reading os.environ directly.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    DATABASE_URL: str = "postgresql://leadgen_user:leadgen_pass@db:5432/leadgen_db"

    # --- JWT (used for owner/team member login on the frontend) ---
    JWT_SECRET_KEY: str = "dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --- Internal API key (used by scraper bots + AI service to push data in) ---
    INTERNAL_API_KEY: str = "dev-internal-key-change-me"

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- Google Sheets (only referenced here, actual sync logic lives in the
    # Database & Sheets module, but the backend needs the id to trigger jobs) ---
    GOOGLE_SHEETS_SPREADSHEET_ID: str = ""
    GOOGLE_SERVICE_ACCOUNT_JSON_PATH: str = ""
    # Tab the weekly export writes to.
    GOOGLE_SHEETS_WORKSHEET: str = "Leads"
    # Separate tab for the weekly dashboard, which is fully rebuilt each run.
    GOOGLE_SHEETS_DASHBOARD_WORKSHEET: str = "Weekly Dashboard"
    # Force the export to log rows instead of writing them. Leave False: the
    # export already falls back to dry run on its own when credentials are
    # missing. This is for deliberately rehearsing a run against a real setup.
    SHEETS_DRY_RUN: bool = False


settings = Settings()
