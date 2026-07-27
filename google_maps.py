from fastapi import APIRouter

from app.services.google_maps_pipeline import GoogleMapsPipeline


router = APIRouter()

pipeline = GoogleMapsPipeline()


@router.post("/search")
async def search_google_maps(
    category:str,
    city:str,
    country:str="Pakistan",
    max_results:int=1
):

    leads = await pipeline.run(
        category,
        city,
        country,
        max_results
    )


    return {
    "message": "Leads generated successfully",
    "total": len(leads),
    "leads": [
        {
            "id": lead.id,
            "business_name": lead.business_name,
            "category": lead.category,
            "website": lead.website,
            "phone": lead.phone,
            "city": lead.city,
            "country": lead.country,

            "order_method": lead.order_method,
            "delivery_system": lead.delivery_system,
            "automation_status": lead.automation_status,

            "priority": lead.lead_priority,
            "notes": lead.notes
        }
        for lead in leads
    ]
}