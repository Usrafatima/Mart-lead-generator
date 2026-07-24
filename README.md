# 🛒 Mart Lead Generator

An AI-powered lead generation system that automates the discovery, enrichment, classification, and management of retail business leads. The platform scrapes businesses from Google Maps, extracts contact information from websites and social media, classifies businesses using AI, and provides a centralized dashboard for lead management.

---

## ✨ Features

- **Google Maps Discovery**
  - Search businesses by city and category
  - Collect business names, addresses, phone numbers, ratings, and websites

-  **Website Data Enrichment**
  - Extract emails, phone numbers, contact pages, and business details
  - Detect website availability

-  **Social Media Discovery**
  - Find Facebook, Instagram, WhatsApp, and LinkedIn profiles
  - Collect publicly available contact information

-  **AI Lead Classification**
  - Detect Order Method
  - Identify Delivery System
  - Determine Automation Status
  - Generate Lead Priority
  - Add AI-generated notes

-  **Lead Management**
  - Duplicate detection
  - PostgreSQL database
  - Search and filtering

-  **Admin Dashboard**
  - View all collected leads
  - Search & filters
  - Analytics
  - Export options

-  **Export**
  - Google Sheets
  - CSV

-  **Automation**
  - Background scraping jobs
  - Weekly scheduled tasks using Celery

---

# 🛠 Tech Stack

## Frontend
- Next.js 16
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Table
- Axios

## Backend
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT Authentication
- Pydantic

## Scraping
- Playwright
- BeautifulSoup4
- Requests

## AI
- Grok

## Background Processing
- Celery
- Redis

## Data Processing
- Pandas

## Deployment
- Docker
- Docker Compose

---

# 📁 Project Structure

```text
mart-lead-generator/
│
├── backend/
│   ├── app/
│   ├── api/
│   ├── services/
│   ├── scraper/
│   ├── ai/
│   └── database/
│
├── frontend/
│
├── playwright-bots/
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

# 🚀 Getting Started

## 1. Clone Repository

```bash
git clone https://github.com/your-username/mart-lead-generator.git

cd mart-lead-generator
```

---

## 2. Backend Setup

```bash
cd backend

python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

## 3. Environment Variables

Create a `.env` file inside the backend directory.

```env
DATABASE_URL=
OPENAI_API_KEY=
JWT_SECRET_KEY=
REDIS_URL=
```

---

## 4. Run with Docker

```bash
docker-compose up --build
```

---

## 5. Run Manually

```bash
uvicorn app.main:app --reload
```

---

---

# 📌 Lead Information Collected

- Business Name
- Business Type
- Country
- City
- Address
- Phone Number
- Email
- Website
- Website URL
- Owner / Manager
- Social Media Links
- Order Method
- Delivery System
- Automation Status
- Google Rating
- Reviews Count
- Lead Priority
- Notes
- Call Status
- Follow-up Date

---

# ⚠️ Notes

- Respect the Terms of Service of websites and data providers.
- Use proxy rotation for large-scale scraping.
- Validate collected data before outreach.
- Monitor scraping jobs regularly for failures.
- Secure API keys using environment variables.

---

# 📄 License

This project is intended for educational and business automation purposes.