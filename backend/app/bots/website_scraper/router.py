from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.bots.website_scraper.scraper import WebsiteScraper

router = APIRouter()

class ScrapeRequest(BaseModel):
    website: str

@router.get("/status", tags=["Website Scraper"])
async def scraper_status():
    """Simple status endpoint for the website scraper bot."""
    return {"service": "website scraper", "status": "ready"}

@router.post("/scrape", tags=["Website Scraper"])
async def scrape_website(payload: ScrapeRequest):
    if not payload.website:
        raise HTTPException(status_code=400, detail="Website URL is required")
    scraper = WebsiteScraper()
    result = await scraper.scrape(payload.website)
    return result

