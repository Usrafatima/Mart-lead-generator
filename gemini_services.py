import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


def test_gemini():
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents="Reply with exactly: Gemini Connected Successfully"
    )

    return response.text


def classify_business(business, website_data=None):

    prompt = f"""
Business Name: {business.name}
Category: {business.category}
Website: {business.website}
Phone: {business.phone}
City: {business.city}
Country: {business.country}

Website Emails: {website_data.get("emails") if website_data else []}
Website Phones: {website_data.get("phones") if website_data else []}
Website Address: {website_data.get("address") if website_data else ""}
Technologies: {website_data.get("technologies") if website_data else []}

Facebook:
{website_data.get("social_links", {}).get("facebook") if website_data else ""}

Instagram:
{website_data.get("social_links", {}).get("instagram") if website_data else ""}

LinkedIn:
{website_data.get("social_links", {}).get("linkedin") if website_data else ""}

WhatsApp:
{website_data.get("social_links", {}).get("whatsapp") if website_data else ""}

Contact Form:
{website_data.get("contact_form") if website_data else False}

Contact Page:
{website_data.get("contact_page") if website_data else ""}


Return ONLY valid JSON:

{{
  "order_method": "",
  "delivery_system": "",
  "automation_status": "",
  "lead_priority": "",
  "notes": ""
}}
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text.strip()

        # Remove markdown JSON formatting if Gemini adds it
        if text.startswith("```json"):
            text = text.replace("```json", "")
            text = text.replace("```", "")
            text = text.strip()

        return json.loads(text)


    except Exception as e:

        print("Gemini Error:", e)

        # fallback response
        return {
            "order_method": "Unknown",
            "delivery_system": "Unknown",
            "automation_status": "Unknown",
            "lead_priority": "Low",
            "notes": "Gemini unavailable"
        }