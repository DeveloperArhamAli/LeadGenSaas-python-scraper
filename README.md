# Python Scraper Service

Lead scraping microservice for the Lead Gen SaaS platform.

## Features
- Google Maps scraping with anti-detection
- Website quality analysis
- Email extraction from websites
- Batch processing support

## Setup

1. Install Python 3.9+
2. Install dependencies:
```bash
   pip install -r requirements.txt
```

3. Install Chrome/Chromium (required for Selenium)

4. Run the service:
```bash
   python app.py
```

Service runs on http://localhost:5001

## API Endpoints

### POST /scrape
Scrape Google Maps for businesses
```json
{
  "keyword": "restaurants",
  "location": "Kuwait",
  "max_results": 100
}
```

### POST /analyze-website
Analyze a website's quality
```json
{
  "url": "https://example.com"
}
```

### POST /find-email
Find email on a website
```json
{
  "url": "https://example.com"
}
```