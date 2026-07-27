import asyncio

from app.bots.google_maps import GoogleMapsBot
from app.services.lead_service import LeadService


class GoogleMapsPipeline:


    def __init__(self):
        self.google_bot = GoogleMapsBot()
        self.lead_service = LeadService()


    async def run(
        self,
        category,
        city,
        country=None,
        max_results=10
    ):


        # Step 1: Google Maps se businesses lao

        businesses = await self.google_bot.search_businesses(
            category=category,
            city=city,
            country=country,
            max_results=max_results
        )


        results=[]


        # Step 2: Har business ko process karo

        for business in businesses:

            lead = await self.lead_service.process_lead(
                business
            )

            results.append(lead)


        return results



async def main():

    pipeline = GoogleMapsPipeline()


    leads = await pipeline.run(
        category="restaurants",
        city="Lahore",
        country="Pakistan",
        max_results=5
    )


    for lead in leads:
        print(
            lead.business_name,
            lead.lead_priority
        )



if __name__=="__main__":
    asyncio.run(main())