
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.v1.api import api_router

from app.core.database import Base, engine
from app.models.lead import Lead

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

app = FastAPI(title="Mart Lead Generator API", version="1.0.0")
Base.metadata.create_all(bind=engine)

# CORS configuration - allow all origins (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health", tags=["Health"], response_class=JSONResponse)
async def health_check():
    """Simple health check endpoint used by orchestrators and load balancers."""
    return {"status": "ok"}

# Redirect root to docs
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
async def redirect_to_docs():
    return RedirectResponse(url="/docs")


# Include versioned API router
app.include_router(api_router, prefix="/api/v1")