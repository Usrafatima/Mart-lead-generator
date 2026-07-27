from app.models.business import Business
from app.models.lead import LeadPriority


def score_priority(business: Business) -> LeadPriority:
    """
    Fallback scoring rule used only if the AI Classification Service hasn't
    returned a priority yet (e.g. while it's still processing in the queue).
    The AI service's own priority value always takes precedence once it
    arrives via POST /api/v1/leads/{id}/classify.
    """
    score = 0

    if business.website:
        score += 1
    if business.email:
        score += 1
    if business.phone:
        score += 1
    if business.facebook_url or business.instagram_url or business.whatsapp_number:
        score += 1

    if score >= 3:
        return LeadPriority.high
    if score >= 1:
        return LeadPriority.medium
    return LeadPriority.low
