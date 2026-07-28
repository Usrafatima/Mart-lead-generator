FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Playwright Chromium runtime libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    postgresql-client \
    wget \
    ca-certificates \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxcb1 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    libgtk-3-0 \
    libxss1 \
    fonts-liberation \
    fonts-unifont \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser binary
RUN python -m playwright install chromium

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python scripts/wait_for_db.py && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
