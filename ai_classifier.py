from app.services.gemini_services import classify_business
from app.schemas.classification import ClassificationResponse


class AIClassifier:

    def __init__(self):
        print("AI Classifier Started")

    def classify(self, business, website_data=None):

        print("Business Name:", business.name)
        print("Category:", business.category)
        print("Website:", business.website)

        result = classify_business(
            business,
            website_data
        )

        return ClassificationResponse(**result)