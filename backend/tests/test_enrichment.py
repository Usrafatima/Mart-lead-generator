import uuid
import pytest
from unittest.mock import patch, MagicMock

from app.models.business import Business
from app.models.lead import Lead, AutomationStatus, OrderMethod
from app.services.discovery_ingest import ingest_scraped_lead, ingest_scraped_leads
from app.bots.website_scraper.scraper import WebsiteScraper
from app.bots.website_scraper.technology_detector import TechnologyDetector
from app.bots.website_scraper.contact_extractor import extract_owner_name


def test_technology_detector_order_method():
    html = """
    <html>
      <head>
        <script src="https://cdn.shopify.com/s/files/1/0000/0000/t/1/assets/theme.js"></script>
      </head>
      <body>
        <h1>Shopify Store</h1>
        <a href="/cart">Add to Cart</a>
        <a href="https://foodpanda.pk">Order on Foodpanda</a>
      </body>
    </html>
    """
    detector = TechnologyDetector(html)
    techs = detector.detect()
    assert "Shopify" in techs
    providers = detector.detect_delivery_providers()
    assert "Foodpanda" in providers

    order_method, detail, delivery_sys = detector.detect_order_and_delivery()
    assert order_method == "online"
    assert "Shopify" in detail
    assert "Foodpanda" in delivery_sys


def test_extract_owner_name():
    html = """
    <html>
      <head>
        <meta name="founder" content="Ali Ahmed" />
      </head>
      <body>
        <h1>Our Supermarket</h1>
        <p>Founder: Ali Ahmed</p>
      </body>
    </html>
    """
    owner = extract_owner_name(html)
    assert owner == "Ali Ahmed"


def test_ingest_scraped_lead_queues_enrichment(db):
    scraped_item = {
        "name": "Al-Fatah Supermarket",
        "city": "Lahore",
        "country": "Pakistan",
        "category": "Supermarket",
        "website": "https://alfatah.pk",
        "phone": "+9242111162786",
    }

    with patch("app.workers.celery_worker.enrich_website_task.delay") as mock_delay:
        summary = ingest_scraped_leads(db, [scraped_item], commit=True)
        assert summary["created"] == 1

        business = db.query(Business).filter(Business.name == "Al-Fatah Supermarket").first()
        assert business is not None
        assert business.website == "https://alfatah.pk"

        lead = db.query(Lead).filter(Lead.business_id == business.id).first()
        assert lead is not None
        assert lead.automation_status_detail == "Queued"
        mock_delay.assert_called_once_with(str(business.id))


def test_website_scraper_mocked(db):
    mock_scrape_result = {
        "status": "success",
        "website": "https://example-mart.com",
        "emails": ["info@example-mart.com"],
        "phones": ["+923001234567"],
        "owner_manager_name": "Tariq Malik",
        "contact_page": "https://example-mart.com/contact",
        "social_links": {
            "facebook": "https://facebook.com/examplemart",
            "instagram": "https://instagram.com/examplemart",
            "whatsapp": "+923001234567",
        },
        "technologies": ["Shopify"],
        "delivery_providers": ["Foodpanda"],
        "order_method": "online",
        "order_method_detail": "Online (Shopify E-Commerce)",
        "delivery_system": "Foodpanda",
    }

    business = Business(
        name="Example Mart",
        city="Lahore",
        country="Pakistan",
        website="https://example-mart.com",
    )
    db.add(business)
    db.commit()

    b_id = business.id

    with patch("app.core.database.SessionLocal", return_value=db), \
         patch.object(WebsiteScraper, "scrape_sync", return_value=mock_scrape_result):
        from app.workers.celery_worker import enrich_website_task
        res = enrich_website_task(str(b_id))
        assert res["status"] == "success"

    updated_business = db.query(Business).filter(Business.id == b_id).first()
    assert updated_business.email == "info@example-mart.com"
    assert updated_business.owner_manager_name == "Tariq Malik"
    assert updated_business.facebook_url == "https://facebook.com/examplemart"
    assert updated_business.instagram_url == "https://instagram.com/examplemart"

    lead = db.query(Lead).filter(Lead.business_id == b_id).first()
    assert lead is not None
    assert lead.automation_status == AutomationStatus.completed
    assert lead.automation_status_detail == "Completed"
    assert lead.delivery_system == "Foodpanda"
    assert lead.order_method == OrderMethod.online
    assert "Tariq Malik" in lead.notes
