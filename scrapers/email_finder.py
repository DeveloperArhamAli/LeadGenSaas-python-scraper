import requests
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

class EmailFinder:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def find_email(self, url):
        """Find email address on a website"""
        if not url:
            return None
        
        # Normalize URL
        if not url.startswith('http'):
            url = 'https://' + url
        
        logger.info(f"Looking for email on: {url}")
        
        try:
            email = self._extract_from_page(url)
            if email:
                logger.info(f"   ✅ Found email on main page: {email}")
                return email
            
            # Try common contact pages
            contact_paths = ['/contact', '/contact-us', '/about', '/about-us']
            
            for path in contact_paths:
                contact_url = url.rstrip('/') + path
                try:
                    email = self._extract_from_page(contact_url)
                    if email:
                        logger.info(f"   ✅ Found email on {path}: {email}")
                        return email
                except:
                    continue
            
            logger.info("   ❌ No email found")
            return None
            
        except Exception as e:
            logger.error(f"   ❌ Error finding email: {e}")
            return None
    
    def _extract_from_page(self, url):
        """Extract email from a specific page"""
        response = requests.get(url, headers=self.headers, timeout=10)
        html = response.text
        
        # Regex patterns for emails
        email_patterns = [
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
        
        emails = []
        for pattern in email_patterns:
            found = re.findall(pattern, html, re.IGNORECASE)
            emails.extend(found)
        
        if not emails:
            return None
        
        # Filter out common junk/placeholder emails
        junk_domains = [
            'example.com',
            'yourdomain.com',
            'yoursite.com',
            'domain.com',
            'email.com',
            'sentry.io',
            'googletagmanager.com',
            'wixpress.com',
            'placeholder.com',
            'test.com',
            'sample.com'
        ]
        
        filtered = []
        for email in emails:
            email = email.lower().strip()
            
            # Skip if it's a junk domain
            if any(junk in email for junk in junk_domains):
                continue
            
            # Skip common generic emails (unless it's the only one)
            if email.startswith(('noreply@', 'no-reply@', 'donotreply@')):
                continue
            
            filtered.append(email)
        
        # Return the first valid email found
        return filtered[0] if filtered else None