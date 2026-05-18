import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class WebsiteChecker:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def analyze(self, url):
        """Analyze a website and return quality score"""
        if not url:
            return {
                'hasWebsite': False,
                'status': 'none',
                'score': 0,
                'issues': ['No website found']
            }
        
        # Normalize URL
        if not url.startswith('http'):
            url = 'https://' + url
        
        logger.info(f"Analyzing: {url}")
        
        try:
            start_time = datetime.now()
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=15,
                allow_redirects=True,
                verify=True
            )
            
            load_time = (datetime.now() - start_time).total_seconds()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            html_text = response.text.lower()
            
            analysis = {
                'hasWebsite': True,
                'status': 'functional',
                'score': 100,
                'issues': [],
                'loadTime': round(load_time, 2),
                'statusCode': response.status_code,
                'finalUrl': response.url
            }
            
            # === Check 1: HTTP Status ===
            if response.status_code >= 400:
                analysis['issues'].append(f'HTTP {response.status_code} error')
                analysis['score'] -= 50
                analysis['status'] = 'broken'
                logger.warning(f"   ❌ HTTP {response.status_code}")
            
            # === Check 2: Load Time ===
            if load_time > 5:
                analysis['issues'].append(f'Slow loading time ({load_time:.1f}s)')
                analysis['score'] -= 15
                logger.warning(f"   ⚠️  Slow load time: {load_time:.1f}s")
            else:
                logger.info(f"   ✅ Load time: {load_time:.2f}s")
            
            # === Check 3: Mobile Responsiveness ===
            viewport = soup.find('meta', attrs={'name': 'viewport'})
            if not viewport:
                analysis['issues'].append('Not mobile-friendly')
                analysis['score'] -= 20
                logger.warning("   ❌ Not mobile-friendly")
            else:
                logger.info("   ✅ Mobile-friendly")
            
            # === Check 4: HTTPS ===
            if not response.url.startswith('https://'):
                analysis['issues'].append('No SSL certificate (not HTTPS)')
                analysis['score'] -= 15
                logger.warning("   ❌ No HTTPS")
            else:
                logger.info("   ✅ HTTPS enabled")
            
            # === Check 5: Modern Framework Detection ===
            modern_frameworks = ['react', 'vue', 'angular', 'bootstrap', 'tailwind', 'next.js', 'nuxt']
            has_modern = any(framework in html_text for framework in modern_frameworks)
            
            if not has_modern:
                analysis['issues'].append('Potentially outdated design (no modern framework detected)')
                analysis['score'] -= 10
                logger.warning("   ⚠️  No modern framework detected")
            else:
                logger.info("   ✅ Modern framework detected")
            
            # === Check 6: Copyright Year ===
            copyright_year = self.extract_copyright_year(response.text)
            if copyright_year:
                current_year = datetime.now().year
                years_old = current_year - copyright_year
                
                if years_old > 3:
                    analysis['issues'].append(f'Copyright year is outdated ({copyright_year})')
                    analysis['score'] -= 15
                    logger.warning(f"   ⚠️  Outdated copyright: {copyright_year}")
                elif years_old > 1:
                    analysis['issues'].append(f'Copyright year slightly outdated ({copyright_year})')
                    analysis['score'] -= 5
                else:
                    logger.info(f"   ✅ Copyright up to date: {copyright_year}")
            
            # === Check 7: SEO - Title Tag ===
            title = soup.find('title')
            if not title or len(title.text.strip()) < 10:
                analysis['issues'].append('Missing or poor title tag')
                analysis['score'] -= 10
                logger.warning("   ❌ Poor/missing title tag")
            else:
                logger.info(f"   ✅ Title: {title.text.strip()[:50]}...")
            
            # === Check 8: SEO - Meta Description ===
            description = soup.find('meta', attrs={'name': 'description'})
            if not description:
                analysis['issues'].append('Missing meta description')
                analysis['score'] -= 5
                logger.warning("   ❌ Missing meta description")
            else:
                logger.info("   ✅ Meta description present")
            
            # === Check 9: Contact Information ===
            contact_keywords = ['contact', 'email', 'phone', 'call us', 'reach us', 'get in touch']
            has_contact = any(keyword in html_text for keyword in contact_keywords)
            
            if not has_contact:
                analysis['issues'].append('No visible contact information')
                analysis['score'] -= 10
                logger.warning("   ⚠️  No contact info found")
            else:
                logger.info("   ✅ Contact information found")
            
            # === Check 10: Broken Images ===
            images = soup.find_all('img')
            broken_images = sum(1 for img in images if not img.get('src'))
            if broken_images > 0:
                analysis['issues'].append(f'{broken_images} images missing src attribute')
                analysis['score'] -= 5
                logger.warning(f"   ⚠️  {broken_images} broken images")
            
            # === Check 11: Page Size ===
            page_size_mb = len(response.content) / (1024 * 1024)
            if page_size_mb > 5:
                analysis['issues'].append(f'Large page size ({page_size_mb:.1f}MB)')
                analysis['score'] -= 10
                logger.warning(f"   ⚠️  Large page: {page_size_mb:.1f}MB")
            
            # === Determine Final Status ===
            if analysis['score'] < 40:
                analysis['status'] = 'broken'
            elif analysis['score'] < 70:
                analysis['status'] = 'outdated'
            else:
                analysis['status'] = 'functional'
            
            logger.info(f"   📊 Final Score: {analysis['score']}/100 - Status: {analysis['status']}")
            
            return analysis
            
        except requests.exceptions.SSLError as e:
            logger.error(f"   ❌ SSL Error: {e}")
            return {
                'hasWebsite': True,
                'status': 'broken',
                'score': 0,
                'issues': ['SSL Certificate Error - Website not secure']
            }
        
        except requests.exceptions.Timeout:
            logger.error("   ❌ Timeout")
            return {
                'hasWebsite': True,
                'status': 'broken',
                'score': 10,
                'issues': ['Website timeout - Takes too long to load']
            }
        
        except requests.exceptions.ConnectionError as e:
            logger.error(f"   ❌ Connection Error: {e}")
            return {
                'hasWebsite': True,
                'status': 'broken',
                'score': 0,
                'issues': ['Cannot connect to website - May be down']
            }
        
        except Exception as e:
            logger.error(f"   ❌ Error: {str(e)}")
            return {
                'hasWebsite': True,
                'status': 'broken',
                'score': 0,
                'issues': [f'Failed to analyze: {str(e)}']
            }
    
    def extract_copyright_year(self, html):
        """Extract copyright year from HTML"""
        # Look for patterns like ©2024, © 2024, Copyright 2024, etc.
        patterns = [
            r'©\s*(\d{4})',
            r'copyright\s*©?\s*(\d{4})',
            r'\(c\)\s*(\d{4})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                year = int(match.group(1))
                # Sanity check: year should be between 2000 and current year + 1
                current_year = datetime.now().year
                if 2000 <= year <= current_year + 1:
                    return year
        
        return None