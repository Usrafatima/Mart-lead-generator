from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, businesses, discovery, leads
from app.api.v1.api import api_router
from app.api.v1 import exports  # Database & Sheets module: CSV + Google Sheets export
from app.api.v1 import reports  # Database & Sheets module: weekly dashboard
from app.core.config import settings
from app.core.database import Base, engine
from app.models import business, lead, sync_run, user  # noqa: F401

app = FastAPI(
    title="Lead Generation System - Backend API",
    description="Auth for the frontend, and lead management/AI classification for the Lead Generation System.",
    version="0.2.0",
)

# Allow the Next.js frontend to call this API. Restrict origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: replace with actual frontend URL before production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(businesses.router)
app.include_router(discovery.router)
app.include_router(leads.router)
app.include_router(exports.router)
app.include_router(reports.router)
app.include_router(api_router)


@app.on_event("startup")
def create_local_sqlite_tables():
    """Let local dev run without Docker/Postgres."""
    if settings.DATABASE_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    return {"status": "ok"}
