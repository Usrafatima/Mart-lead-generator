import re

# Regular expression for email addresses
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# Regular expression for phone numbers (supports +country code, area codes, hyphens, and spaces)
PHONE_REGEX = re.compile(r"\+?\d{1,4}[-.\s]?\(?\d{1,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}")

