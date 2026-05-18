from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import re
import logging
import os

logger = logging.getLogger(__name__)


class GoogleMapsScraper:
    def __init__(self):
        self.driver = None

    # ─────────────────────────────────────────────
    # DRIVER SETUP
    # ─────────────────────────────────────────────

    def setup_driver(self):
        """Setup Chrome driver with anti-detection and suppressed logs"""
        logger.info("Setting up Chrome driver...")

        os.environ['WDM_LOG'] = '0'
        os.environ['WDM_PRINT_FIRST_LINE'] = 'False'

        options = Options()
        options.binary_location = "/usr/bin/chromium-browser"

        # Anti-detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)

        # Headless
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')

        # Suppress logs
        options.add_argument('--log-level=3')
        options.add_argument('--silent')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-background-networking')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-features=MediaRouter')
        options.add_argument('--metrics-recording-only')
        options.add_argument('--mute-audio')
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        prefs = {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0,
            'profile.password_manager_enabled': False,
            'credentials_enable_service': False,
        }
        options.add_experimental_option('prefs', prefs)

        try:
            service = Service(log_path=os.devnull)
            self.driver = webdriver.Chrome(service=service, options=options)

            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
            })
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            logger.info("✅ Chrome driver setup successful")

        except Exception as e:
            logger.error(f"❌ Chrome driver setup failed: {e}")
            raise

    # ─────────────────────────────────────────────
    # MAIN SCRAPE ENTRY POINT
    # ─────────────────────────────────────────────

    def scrape(self, keyword, location, max_results=100):
        """Scrape Google Maps for businesses"""
        if not self.driver:
            self.setup_driver()

        search_query = f"{keyword} in {location}"
        url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"

        logger.info(f"📍 Navigating to: {url}")

        try:
            self.driver.get(url)

            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"]'))
            )

            time.sleep(3)

            logger.info(f"📜 Scrolling to load up to {max_results} results...")
            results_container = self.driver.find_element(By.CSS_SELECTOR, '[role="feed"]')
            self.scroll_results(results_container, max_results)

            logger.info("📊 Extracting business data...")
            leads = self.extract_businesses()

            logger.info("🔍 Enriching leads with contact details...")
            enriched_leads = []
            for i, lead in enumerate(leads[:max_results], 1):
                logger.info(f"   [{i}/{min(len(leads), max_results)}] Enriching: {lead['businessName']}")
                enriched = self.enrich_lead(lead)
                enriched_leads.append(enriched)

            logger.info(f"✅ Successfully extracted and enriched {len(enriched_leads)} businesses")
            return enriched_leads

        except Exception as e:
            logger.error(f"❌ Scraping failed: {e}")
            raise

    # ─────────────────────────────────────────────
    # SCROLLING
    # ─────────────────────────────────────────────

    def scroll_results(self, container, max_results):
        """Scroll the results container to load more businesses"""
        last_count = 0
        no_change_streak = 0
        max_scroll_attempts = 50

        for _ in range(max_scroll_attempts):
            self.driver.execute_script(
                'arguments[0].scrollTo(0, arguments[0].scrollHeight)',
                container
            )
            time.sleep(2)

            current_count = len(self.driver.find_elements(By.CSS_SELECTOR, '[role="article"]'))
            logger.info(f"   Loaded {current_count} results...")

            if current_count >= max_results:
                logger.info(f"✅ Reached target of {max_results} results")
                break

            if current_count == last_count:
                no_change_streak += 1
                if no_change_streak >= 5:
                    logger.info(f"⚠️  No more results. Stopping at {current_count}")
                    break
            else:
                no_change_streak = 0
                last_count = current_count

    # ─────────────────────────────────────────────
    # CARD EXTRACTION (list view)
    # ─────────────────────────────────────────────

    def extract_businesses(self):
        """Extract all businesses from the list"""
        businesses = []
        cards = self.driver.find_elements(By.CSS_SELECTOR, '[role="article"]')

        logger.info(f"Found {len(cards)} business cards")

        for index, card in enumerate(cards, 1):
            try:
                business = self.extract_card_data(card, index)
                if business:
                    businesses.append(business)
            except Exception as e:
                logger.warning(f"Failed to extract business #{index}: {e}")
                continue

        return businesses

    def extract_card_data(self, card, index):
        """Extract basic data from a business card in the list view.

        NOTE: Phone numbers are intentionally NOT extracted here because Google Maps
        does not reliably expose them on list cards. They are extracted in enrich_lead()
        by visiting the full business profile page.
        """
        business = {}

        # Business name (required)
        try:
            name_el = None
            for selector in ['h3', '.fontHeadlineSmall', '[class*="fontHeadline"]']:
                try:
                    el = card.find_element(By.CSS_SELECTOR, selector)
                    if el and el.text.strip():
                        name_el = el
                        break
                except Exception:
                    continue

            if not name_el or not name_el.text.strip():
                return None

            business['businessName'] = name_el.text.strip()
        except Exception:
            return None

        # Website (best-effort from card)
        business['website'] = None
        try:
            for link in card.find_elements(By.CSS_SELECTOR, 'a[href]'):
                href = link.get_attribute('href')
                if href and self.is_valid_website(href):
                    business['website'] = href
                    break
        except Exception:
            pass

        # Address (best-effort from card)
        business['location'] = None
        try:
            for selector in ['[data-item-id*="address"]', '[aria-label*="Address"]']:
                try:
                    el = card.find_element(By.CSS_SELECTOR, selector)
                    text = el.get_attribute('aria-label') or el.text
                    if text:
                        business['location'] = text.replace('Address: ', '').strip()
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Rating
        business['rating'] = None
        try:
            rating_el = card.find_element(By.CSS_SELECTOR, '[role="img"][aria-label*="star"]')
            business['rating'] = self.extract_rating(rating_el.get_attribute('aria-label'))
        except Exception:
            pass

        # Maps URL (needed for profile enrichment)
        business['mapsUrl'] = None
        try:
            link = card.find_element(By.CSS_SELECTOR, 'a[href*="maps/place"]')
            business['mapsUrl'] = link.get_attribute('href')
        except Exception:
            pass

        # Phone and social fields — populated during enrichment
        business['phone'] = None
        business['email'] = None
        business['instagram'] = None
        business['facebook'] = None
        business['twitter'] = None
        business['linkedin'] = None
        business['whatsapp'] = None
        business['tiktok'] = None
        business['youtube'] = None
        business['snapchat'] = None

        return business

    # ─────────────────────────────────────────────
    # ENRICHMENT
    # ─────────────────────────────────────────────

    def enrich_lead(self, lead):
        """Visit the Google Maps profile and website to extract all contact info"""
        if lead.get('mapsUrl'):
            lead = self.extract_from_maps_profile(lead)

        if lead.get('website'):
            lead = self.extract_from_website(lead)

        return lead

    def extract_from_maps_profile(self, lead):
        """Navigate to the Google Maps business profile and extract phone + socials."""
        try:
            self.driver.get(lead['mapsUrl'])

            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'h1'))
            )
            time.sleep(2)

            # ── Phone extraction (priority order) ──────────────────────────────
            if not lead['phone']:
                lead['phone'] = self._extract_phone_from_profile()
                if lead['phone']:
                    logger.info(f"      📞 Found phone: {lead['phone']}")

            # ── Website (if not already found) ─────────────────────────────────
            if not lead['website']:
                try:
                    for selector in [
                        'a[data-item-id="authority"]',
                        'a[href*="http"]:not([href*="google"])',
                    ]:
                        for link in self.driver.find_elements(By.CSS_SELECTOR, selector):
                            href = link.get_attribute('href')
                            if href and self.is_valid_website(href):
                                lead['website'] = href
                                logger.info(f"      🌐 Found website: {href}")
                                break
                        if lead['website']:
                            break
                except Exception:
                    pass

            # ── Social media from page source ───────────────────────────────────
            social = self.extract_social_from_html(self.driver.page_source)
            for key, val in social.items():
                if val and not lead.get(key):
                    lead[key] = val
                    logger.info(f"      📱 Found {key}: {val}")

            # Go back to the results list
            self.driver.back()
            time.sleep(2)

        except Exception as e:
            logger.warning(f"      ⚠️  Could not enrich from Maps profile: {e}")

        return lead

    def _extract_phone_from_profile(self):
        """
        Try multiple strategies to pull a phone number from the currently
        loaded Google Maps business profile page.

        Priority:
          1. tel: href link  — most reliable, always formatted correctly
          2. aria-label on button/span elements
          3. data-item-id containing "phone"
          4. Regex on page source (conservative patterns only)
        """

        # 1. tel: link — Google Maps wraps the phone number in an <a href="tel:...">
        try:
            tel_el = self.driver.find_element(By.CSS_SELECTOR, 'a[href^="tel:"]')
            raw = tel_el.get_attribute('href').replace('tel:', '').strip()
            cleaned = self.clean_phone(raw)
            if cleaned:
                return cleaned
        except Exception:
            pass

        # 2. aria-label on interactive elements
        phone_selectors = [
            'button[data-item-id*="phone"]',
            'button[aria-label*="Phone"]',
            'button[aria-label*="phone"]',
            'span[aria-label*="Phone"]',
            '[data-tooltip*="phone"]',
        ]
        for selector in phone_selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = (
                    el.get_attribute('aria-label')
                    or el.get_attribute('data-tooltip')
                    or el.text
                )
                cleaned = self.clean_phone(text)
                if cleaned:
                    return cleaned
            except Exception:
                continue

        # 3. data-item-id attribute that contains the phone number itself
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, '[data-item-id*="phone:tel:"]')
            raw = el.get_attribute('data-item-id').split('phone:tel:')[-1].strip()
            cleaned = self.clean_phone(raw)
            if cleaned:
                return cleaned
        except Exception:
            pass

        # 4. Regex fallback on page source — conservative patterns only
        #    We deliberately skip the loose \d{8,} pattern to avoid false positives.
        page_source = self.driver.page_source
        phone_patterns = [
            r'\+\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}',  # intl format
            r'\(?\d{3}\)?[\s\-]\d{3}[\s\-]\d{4}',                             # US/CA format
            r'\d{3}[\s\-]\d{4}[\s\-]\d{4}',                                   # PK/IN format
            r'\d{4}[\s\-]\d{7}',                                               # common PK local
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, page_source)
            if match:
                cleaned = self.clean_phone(match.group().strip())
                if cleaned:
                    return cleaned

        return None

    def extract_from_website(self, lead):
        """Visit the business website to extract email and social media"""
        try:
            import requests
            from bs4 import BeautifulSoup

            url = lead['website']
            if not url.startswith('http'):
                url = 'https://' + url

            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
            }

            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            html = response.text

            # Email
            if not lead.get('email'):
                email = self.extract_email_from_html(html)
                if email:
                    lead['email'] = email
                    logger.info(f"      📧 Found email: {email}")

            # Social media
            social = self.extract_social_from_html(html)
            for key, val in social.items():
                if val and not lead.get(key):
                    lead[key] = val
                    logger.info(f"      📱 Found {key}: {val}")

            # Try contact / about pages if we still need more data
            contact_paths = ['/contact', '/contact-us', '/about', '/about-us', '/reach-us']
            for path in contact_paths:
                already_complete = (
                    lead.get('email')
                    and (lead.get('instagram') or lead.get('facebook'))
                )
                if already_complete:
                    break

                try:
                    contact_url = url.rstrip('/') + path
                    r = requests.get(contact_url, headers=headers, timeout=5)
                    if r.status_code == 200:
                        contact_html = r.text

                        if not lead.get('email'):
                            email = self.extract_email_from_html(contact_html)
                            if email:
                                lead['email'] = email
                                logger.info(f"      📧 Found email on {path}: {email}")

                        contact_social = self.extract_social_from_html(contact_html)
                        for key, val in contact_social.items():
                            if val and not lead.get(key):
                                lead[key] = val
                                logger.info(f"      📱 Found {key} on {path}: {val}")
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"      ⚠️  Could not extract from website: {e}")

        return lead

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────

    def extract_social_from_html(self, html):
        """Extract all social media handles / URLs from raw HTML"""
        social = {
            'instagram': None,
            'facebook': None,
            'twitter': None,
            'linkedin': None,
            'tiktok': None,
            'youtube': None,
            'whatsapp': None,
            'snapchat': None,
        }

        # Instagram
        for pattern in [
            r'instagram\.com/([A-Za-z0-9_.]+)',
            r'@([A-Za-z0-9_.]+)\s*on\s*instagram',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                handle = m.group(1)
                excluded = {'p', 'explore', 'accounts', 'reel', 'stories', 'tv', 'sharer'}
                if handle not in excluded:
                    social['instagram'] = f"https://instagram.com/{handle}"
                    break

        # Facebook
        for pattern in [
            r'facebook\.com/([A-Za-z0-9_./-]+)',
            r'fb\.com/([A-Za-z0-9_./-]+)',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                handle = m.group(1).strip('/')
                excluded_words = {'sharer', 'share', 'login', 'dialog', 'plugins', 'tr', 'photo'}
                if not any(w in handle.lower() for w in excluded_words):
                    social['facebook'] = f"https://facebook.com/{handle}"
                    break

        # Twitter / X
        for pattern in [
            r'twitter\.com/([A-Za-z0-9_]+)',
            r'x\.com/([A-Za-z0-9_]+)',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                handle = m.group(1)
                if handle not in {'intent', 'share', 'home', 'search', 'hashtag'}:
                    social['twitter'] = f"https://twitter.com/{handle}"
                    break

        # LinkedIn
        for pattern in [
            r'linkedin\.com/company/([A-Za-z0-9_-]+)',
            r'linkedin\.com/in/([A-Za-z0-9_-]+)',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                social['linkedin'] = f"https://linkedin.com/company/{m.group(1)}"
                break

        # TikTok
        m = re.search(r'tiktok\.com/@([A-Za-z0-9_.]+)', html, re.IGNORECASE)
        if m:
            social['tiktok'] = f"https://tiktok.com/@{m.group(1)}"

        # YouTube
        for pattern in [
            r'youtube\.com/channel/([A-Za-z0-9_-]+)',
            r'youtube\.com/c/([A-Za-z0-9_-]+)',
            r'youtube\.com/@([A-Za-z0-9_-]+)',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                social['youtube'] = m.group(0)
                break

        # WhatsApp
        for pattern in [
            r'wa\.me/(\d+)',
            r'api\.whatsapp\.com/send\?phone=(\d+)',
            r'whatsapp\.com/send\?phone=(\d+)',
        ]:
            m = re.search(pattern, html, re.IGNORECASE)
            if m:
                social['whatsapp'] = f"https://wa.me/{m.group(1)}"
                break

        # Snapchat
        m = re.search(r'snapchat\.com/add/([A-Za-z0-9_.]+)', html, re.IGNORECASE)
        if m:
            social['snapchat'] = f"https://snapchat.com/add/{m.group(1)}"

        return social

    def extract_email_from_html(self, html):
        """Extract a valid business email from HTML"""
        junk_domains = {
            'example.com', 'yourdomain.com', 'domain.com', 'email.com',
            'sentry.io', 'googletagmanager.com', 'wixpress.com',
            'placeholder.com', 'test.com', 'sample.com', 'schema.org',
            'w3.org', 'cloudflare.com', 'jquery.com', 'google.com',
        }
        junk_prefixes = ('noreply@', 'no-reply@', 'donotreply@', 'wordpress@')

        for pattern in [
            r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        ]:
            for email in re.findall(pattern, html, re.IGNORECASE):
                email = email.lower().strip()
                domain = email.split('@')[-1]

                if domain in junk_domains:
                    continue
                if email.startswith(junk_prefixes):
                    continue
                if '@' in email and '.' in domain:
                    return email

        return None

    def is_valid_website(self, url):
        if not url:
            return False
        excluded = [
            'google.com', 'goo.gl', 'maps.google',
            'accounts.google', 'policies.google',
        ]
        if any(d in url.lower() for d in excluded):
            return False
        return url.startswith('http://') or url.startswith('https://')

    def clean_phone(self, text):
        """
        Normalize a raw phone string.
        - Strips label prefixes like "Phone:", "Call:", "Tel:"
        - Keeps only digits, +, spaces, dashes, parentheses
        - Returns None if nothing meaningful remains
        """
        if not text:
            return None

        # Remove common label prefixes
        text = re.sub(r'(?i)^(phone|call|tel|mobile|mob)[:\s]*', '', text).strip()

        # Keep only phone-valid characters
        cleaned = re.sub(r'[^\d\+\s\-\(\)]', '', text).strip()

        # Must have at least 7 digits to be a real phone number
        digit_count = sum(c.isdigit() for c in cleaned)
        if digit_count < 7:
            return None

        return cleaned if cleaned else None

    def extract_rating(self, text):
        """Extract numeric rating from aria-label string"""
        try:
            m = re.search(r'([\d.]+)\s+star', text, re.IGNORECASE)
            return float(m.group(1)) if m else None
        except Exception:
            return None

    # ─────────────────────────────────────────────
    # LIFECYCLE
    # ─────────────────────────────────────────────

    def close(self):
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
            except Exception:
                pass

    def __del__(self):
        self.close()