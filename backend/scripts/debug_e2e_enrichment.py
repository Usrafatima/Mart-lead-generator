import asyncio
import logging
import time
import requests
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.business import Business
from app.models.lead import Lead
from app.core.security import hash_password, create_access_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e_debug")

API_URL = "http://localhost:8000"

def get_auth_token():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "owner@example.com").first()
        if not user:
            user = User(
                email="owner@example.com",
                hashed_password=hash_password("password123"),
                full_name="Owner User",
                role=UserRole.owner,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return create_access_token({"sub": str(user.id)})
    finally:
        db.close()

def main():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    logger.info("=== REQUIREMENT 1: Tracing complete execution path after Google Maps discovery ===")
    payload = {
        "category": "supermarket",
        "city": "Karachi",
        "country": "Pakistan",
        "max_results": 3,
        "headless": True
    }
    
    logger.info("Sending Discovery request: %s", payload)
    start_time = time.time()
    resp = requests.post(f"{API_URL}/api/v1/discovery/google-maps", json=payload, headers=headers)
    
    if resp.status_code != 200:
        logger.error("Discovery failed: %s %s", resp.status_code, resp.text)
        return
        
    data = resp.json()
    summary = data.get("summary", {})
    businesses = data.get("businesses", [])
    logger.info("Discovery Response Summary: %s | Total Businesses: %d", summary, len(businesses))
    
    db = SessionLocal()
    try:
        for b in businesses:
            b_id = b["id"]
            name = b["name"]
            website = b.get("website")
            logger.info("Discovered Business: ID=%s | Name='%s' | Website='%s'", b_id, name, website)
            
            lead = db.query(Lead).filter(Lead.business_id == b_id).first()
            if lead:
                logger.info("-> Lead record created: ID=%s | AutomationStatus=%s | Detail=%s", 
                            lead.id, lead.automation_status, lead.automation_status_detail)
            else:
                logger.warning("-> No Lead record found for business %s!", b_id)
    finally:
        db.close()

    logger.info("Waiting 25 seconds for Celery workers to pick up and complete website enrichment...")
    time.sleep(25)

    logger.info("=== REQUIREMENT 12: Verify dashboard API returns updated values ===")
    leads_resp = requests.get(f"{API_URL}/api/v1/leads", headers=headers)
    if leads_resp.status_code == 200:
        lead_list = leads_resp.json()
        logger.info("Dashboard API GET /api/v1/leads returned %d leads", len(lead_list))
        for l in lead_list[:5]:
            b_info = l.get("business", {})
            logger.info("API Lead #%s | Biz='%s' | Email='%s' | Owner='%s' | AutomationStatus='%s' (%s) | OrderMethod='%s' (%s) | Delivery='%s'",
                        l.get("lead_ref"),
                        b_info.get("name"),
                        b_info.get("email"),
                        b_info.get("owner_manager_name"),
                        l.get("automation_status"),
                        l.get("automation_status_detail"),
                        l.get("order_method"),
                        l.get("order_method_detail"),
                        l.get("delivery_system"))
    else:
        logger.error("Failed to fetch leads from API: %s %s", leads_resp.status_code, leads_resp.text)

if __name__ == "__main__":
    main()
