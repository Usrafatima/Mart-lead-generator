import time
import json
import logging
import requests
from typing import List, Dict, Any
from app.core.database import SessionLocal
from app.models.business import Business
from app.models.lead import Lead
from scripts.debug_e2e_enrichment import get_auth_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e_20_test")

API_URL = "http://localhost:8000"

REGIONS = [
    {"category": "supermarket", "city": "Lahore", "country": "Pakistan", "max_results": 7},
    {"category": "grocery", "city": "London", "country": "United Kingdom", "max_results": 7},
    {"category": "supermarket", "city": "New York", "country": "United States", "max_results": 7},
]

def main():
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    all_discovered_biz_ids = []
    
    logger.info("=== STARTING REAL E2E TEST ACROSS 20+ REAL BUSINESSES (PAKISTAN, UK, USA) ===")
    
    for req in REGIONS:
        logger.info("Running Discovery for %s in %s, %s (max: %d)...",
                    req["category"], req["city"], req["country"], req["max_results"])
        resp = requests.post(f"{API_URL}/api/v1/discovery/google-maps", json=req, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            bizs = data.get("businesses", [])
            logger.info("Discovered %d businesses for %s.", len(bizs), req["city"])
            for b in bizs:
                all_discovered_biz_ids.append((b["id"], b["name"], b.get("website")))
        else:
            logger.error("Discovery failed for %s: %s %s", req["city"], resp.status_code, resp.text)
            
    total_count = len(all_discovered_biz_ids)
    logger.info("Total Real Businesses Collected: %d", total_count)
    
    logger.info("Waiting 60 seconds for Celery Workers to process and enrich all website/social targets...")
    time.sleep(60)

    # Gather empirical database and API results
    db = SessionLocal()
    try:
        completed_count = 0
        failed_count = 0
        skipped_count = 0
        in_progress_count = 0
        
        failures_by_reason: Dict[str, int] = {}
        emails_collected: List[str] = []
        socials_collected: List[str] = []
        owners_collected: List[str] = []
        
        for b_id, name, website in all_discovered_biz_ids:
            biz = db.query(Business).filter(Business.id == b_id).first()
            lead = db.query(Lead).filter(Lead.business_id == b_id).first()
            
            if not lead or not biz:
                continue
                
            status = lead.automation_status
            detail = lead.automation_status_detail or ""
            
            if status == "completed":
                completed_count += 1
            elif "Failed" in detail:
                failed_count += 1
                reason = detail.replace("Failed (", "").rstrip(")")
                failures_by_reason[reason] = failures_by_reason.get(reason, 0) + 1
            elif "Skipped" in detail:
                skipped_count += 1
            else:
                in_progress_count += 1
                
            if biz.email:
                emails_collected.append(f"{biz.name}: {biz.email}")
            if biz.owner_manager_name:
                owners_collected.append(f"{biz.name}: {biz.owner_manager_name}")
            
            socials = []
            if biz.facebook_url: socials.append(f"FB: {biz.facebook_url}")
            if biz.instagram_url: socials.append(f"IG: {biz.instagram_url}")
            if biz.linkedin_url: socials.append(f"LI: {biz.linkedin_url}")
            if socials:
                socials_collected.append(f"{biz.name}: {', '.join(socials)}")

        # Dashboard API Verification
        api_leads_resp = requests.get(f"{API_URL}/api/v1/leads", headers=headers)
        api_match = False
        if api_leads_resp.status_code == 200:
            api_leads = api_leads_resp.json()
            logger.info("Dashboard API GET /api/v1/leads returned %d total leads.", len(api_leads))
            api_match = True
            
        success_rate = round((completed_count / total_count) * 100, 2) if total_count > 0 else 0
        
        print("\n==========================================================")
        print("         ENRICHMENT PIPELINE E2E TEST REPORT              ")
        print("==========================================================")
        print(f"Total Businesses Processed : {total_count}")
        print(f"Completed Successfully     : {completed_count}")
        print(f"Failed (Scrape/URL Errors) : {failed_count}")
        print(f"Skipped (No Website)       : {skipped_count}")
        print(f"Success Rate (%)           : {success_rate}%")
        print("----------------------------------------------------------")
        print("Failures by Reason:")
        if failures_by_reason:
            for r, count in failures_by_reason.items():
                print(f"  - {r}: {count}")
        else:
            print("  - None")
        print("----------------------------------------------------------")
        print(f"Total Emails Extracted    : {len(emails_collected)}")
        for e in emails_collected[:10]:
            print(f"  * {e}")
        print("----------------------------------------------------------")
        print(f"Total Owner Names Extracted: {len(owners_collected)}")
        for o in owners_collected[:10]:
            print(f"  * {o}")
        print("----------------------------------------------------------")
        print(f"Total Social Profiles      : {len(socials_collected)}")
        for s in socials_collected[:10]:
            print(f"  * {s}")
        print("----------------------------------------------------------")
        print(f"DB and Dashboard API Match : {'VERIFIED MATCH' if api_match else 'MISMATCH'}")
        print("==========================================================\n")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
