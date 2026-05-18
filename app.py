from flask import Flask, request, jsonify
from flask_cors import CORS
from scrapers.google_maps import GoogleMapsScraper
from scrapers.website_checker import WebsiteChecker
from scrapers.email_finder import EmailFinder
import os
from dotenv import load_dotenv
import logging

load_dotenv()

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

google_scraper = GoogleMapsScraper()
website_checker = WebsiteChecker()
email_finder = EmailFinder()

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'python-scraper',
        'version': '1.0.0'
    })

@app.route('/scrape', methods=['POST'])
def scrape_leads():
    """
    Scrape Google Maps for business leads
    
    POST /scrape
    Body: {
        "keyword": "restaurants",
        "location": "Kuwait",
        "max_results": 100
    }
    """
    try:
        data = request.json
        keyword = data.get('keyword')
        location = data.get('location')
        max_results = data.get('max_results', 100)
        
        if not keyword or not location:
            return jsonify({
                'success': False,
                'error': 'keyword and location are required'
            }), 400
        
        logger.info(f"🔍 Scraping: {keyword} in {location} (max: {max_results})")
        
        # Scrape leads
        leads = google_scraper.scrape(keyword, location, max_results)
        
        logger.info(f"✅ Found {len(leads)} leads")
        
        return jsonify({
            'success': True,
            'count': len(leads),
            'leads': leads
        })
        
    except Exception as e:
        logger.error(f"Scraping error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/analyze-website', methods=['POST'])
def analyze_website():
    """
    Analyze a website's quality and status
    
    POST /analyze-website
    Body: {
        "url": "https://example.com"
    }
    """
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({
                'success': False,
                'error': 'url is required'
            }), 400
        
        logger.info(f"🔍 Analyzing website: {url}")
        
        analysis = website_checker.analyze(url)
        
        return jsonify({
            'success': True,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/batch-analyze', methods=['POST'])
def batch_analyze():
    """
    Analyze multiple websites in batch
    
    POST /batch-analyze
    Body: {
        "urls": ["https://example1.com", "https://example2.com"]
    }
    """
    try:
        data = request.json
        urls = data.get('urls', [])
        
        if not urls:
            return jsonify({
                'success': False,
                'error': 'urls array is required'
            }), 400
        
        logger.info(f"🔍 Batch analyzing {len(urls)} websites")
        
        results = []
        for url in urls:
            try:
                analysis = website_checker.analyze(url)
                results.append({
                    'url': url,
                    'analysis': analysis
                })
            except Exception as e:
                results.append({
                    'url': url,
                    'error': str(e)
                })
        
        return jsonify({
            'success': True,
            'count': len(results),
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Batch analysis error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/find-email', methods=['POST'])
def find_email():
    """
    Find email address on a website
    
    POST /find-email
    Body: {
        "url": "https://example.com"
    }
    """
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({
                'success': False,
                'error': 'url is required'
            }), 400
        
        logger.info(f"📧 Finding email on: {url}")
        
        email = email_finder.find_email(url)
        
        return jsonify({
            'success': True,
            'email': email
        })
        
    except Exception as e:
        logger.error(f"Email finding error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)