from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, businesses, leads
from app.api.v1.api import api_router

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
app.include_router(leads.router)
app.include_router(api_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
