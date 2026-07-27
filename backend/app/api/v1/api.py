from fastapi import APIRouter

# Import the website scraper router
from app.bots.website_scraper.router import router as website_scraper_router

api_router = APIRouter()

# Include the website scraper endpoints under /website-scraper
api_router.include_router(website_scraper_router, prefix="/website-scraper", tags=["Website Scraper"])
