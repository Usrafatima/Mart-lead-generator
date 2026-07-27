from app.services.ai_classifier import AIClassifier
from app.bots.website_scrapers.scraper import WebsiteScraper
from app.core.database import SessionLocal
from app.models.lead import Lead


class LeadService:

    def __init__(self):
        self.classifier = AIClassifier()
        self.scraper = WebsiteScraper()

    async def process_lead(self, business):

        website_data = None

        if business.website:
            website_data = await self.scraper.scrape(
                business.website
            )

        result = self.classifier.classify(
            business,
            website_data
        )

        db = SessionLocal()

        lead = Lead(
            business_name=business.name,
            category=business.category,
            website=business.website,
            phone=business.phone,
            city=business.city,
            country=business.country,
            order_method=result.order_method,
            delivery_system=result.delivery_system,
            automation_status=result.automation_status,
            lead_priority=result.lead_priority,
            notes=result.notes
        )

        db.add(lead)
        db.commit()
        db.refresh(lead)
        db.close()

        return lead