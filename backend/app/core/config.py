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

    # --- Exports (Database & Sheets module) ---
    # Folder the scheduled CSV exports are written to. The team opens these in
    # Excel or uploads them to Google Sheets by hand; the Sheets API was ruled
    # out because it needs a Google Cloud service account.
    EXPORT_DIR: str = "exports"


settings = Settings()
