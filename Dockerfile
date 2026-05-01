FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

# Install Python deps first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY naukri_scraper.py .

# Cloud-friendly: read port from env, default 8000
ENV PORT=8000
EXPOSE 8000

# Use uvicorn directly so signals/healthchecks work cleanly
CMD ["sh", "-c", "uvicorn naukri_scraper:app --host 0.0.0.0 --port ${PORT}"]