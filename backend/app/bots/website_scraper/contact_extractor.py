import re
import html
import json
import urllib.parse
from typing import Set, List, Optional, Tuple, Dict, Any
from bs4 import BeautifulSoup
from ...utils.regex import EMAIL_REGEX, PHONE_REGEX

INVALID_EMAIL_DOMAINS = {
    "example.com", "domain.com", "email.com", "test.com", "yourdomain.com",
    "sentry.io", "w3.org", "schema.org", "github.com", "bootstrap.com",
    "cloudflare.com", "google.com", "facebook.com", "instagram.com"
}

INVALID_EMAIL_PREFIXES = (
    "sentry", "bootstrap", "webpack", "react", "font", "format", "image",
    "icon", "asset", "npm", "node_modules"
)

INVALID_EXTENSIONS = (
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css',
    '.woff', '.woff2', '.ttf', '.eot', '.mp4', '.pdf', '.zip'
)


def _soup_from_html(html_str: str) -> BeautifulSoup:
    return BeautifulSoup(html_str, "lxml")


def _clean_soup_for_text(soup: BeautifulSoup) -> BeautifulSoup:
    soup_copy = BeautifulSoup(str(soup), "lxml")
    for tag in soup_copy(["script", "style", "svg", "path", "noscript", "code", "iframe"]):
        tag.decompose()
    return soup_copy


def _decode_and_clean_email(raw_email: str) -> Optional[str]:
    if not raw_email:
        return None
    
    # 1. Decode HTML entities (e.g. &#64;, &commat;) and URL encoding (%40)
    decoded = urllib.parse.unquote(html.unescape(raw_email.strip()))
    
    # Handle mailto prefix or query params
    if decoded.lower().startswith("mailto:"):
        decoded = decoded[7:]
    decoded = decoded.split("?")[0].strip().rstrip("./;,:")

    # 2. Validation filters
    if not decoded or "@" not in decoded:
        return None

    if any(decoded.lower().endswith(ext) for ext in INVALID_EXTENSIONS):
        return None

    parts = decoded.split("@")
    if len(parts) != 2:
        return None

    prefix, domain = parts[0].lower(), parts[1].lower()

    if domain in INVALID_EMAIL_DOMAINS or any(domain.endswith("." + d) for d in INVALID_EMAIL_DOMAINS):
        return None

    if any(prefix.startswith(bad) for bad in INVALID_EMAIL_PREFIXES):
        return None

    if len(prefix) < 2 or len(domain) < 3 or "." not in domain:
        return None

    return decoded


def extract_emails(html_str: str) -> Set[str]:
    soup = _soup_from_html(html_str)
    emails: Set[str] = set()

    # 1. Extract from mailto hrefs
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "mailto:" in href.lower():
            email = _decode_and_clean_email(href)
            if email:
                emails.add(email)

    # 2. Extract from decoded text
    clean_soup = _clean_soup_for_text(soup)
    clean_text = urllib.parse.unquote(html.unescape(clean_soup.get_text(separator=" ")))

    for match in EMAIL_REGEX.finditer(clean_text):
        email = _decode_and_clean_email(match.group(0))
        if email:
            emails.add(email)

    # Deduplicate case-insensitively keeping clean canonical string
    seen_lower = set()
    deduped = set()
    for e in emails:
        low = e.lower()
        if low not in seen_lower:
            seen_lower.add(low)
            deduped.add(e)

    return deduped


def _is_valid_phone(phone: str) -> bool:
    s = phone.strip()
    digits = re.sub(r'\D', '', s)
    num_digits = len(digits)

    if num_digits < 7 or num_digits > 15:
        return False

    if re.match(r'^\d{4}[-\/\.]\d{2}[-\/\.]\d{2}$', s) or re.match(r'^\d{2}[-\/\.]\d{2}[-\/\.]\d{4}$', s):
        return False

    parts = s.split()
    if len(parts) >= 3 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return False

    if len(set(digits)) <= 2:
        return False

    return True


def _clean_phone_string(phone: str) -> str:
    cleaned = re.sub(r'\s+', ' ', phone.strip())
    cleaned = re.sub(r'\s*-\s*', '-', cleaned)
    return cleaned


def extract_phones(html_str: str) -> Set[str]:
    soup = _soup_from_html(html_str)
    phones: Set[str] = set()

    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        if href.lower().startswith('tel:'):
            phone = href[4:].split('?')[0].strip()
            phone = _clean_phone_string(phone)
            if phone and _is_valid_phone(phone):
                phones.add(phone)

    for tag in soup.find_all(attrs={"itemprop": "telephone"}):
        txt = tag.get_text(strip=True) or tag.get('content', '')
        txt = _clean_phone_string(txt)
        if txt and _is_valid_phone(txt):
            phones.add(txt)

    clean_soup = _clean_soup_for_text(soup)
    clean_text = clean_soup.get_text(separator=' ')

    for match in PHONE_REGEX.finditer(clean_text):
        raw_phone = match.group(0).strip()
        cleaned = _clean_phone_string(raw_phone)
        if _is_valid_phone(cleaned):
            phones.add(cleaned)

    return phones


def extract_address(html_str: str) -> Optional[str]:
    soup = _soup_from_html(html_str)
    addr_tag = soup.select_one('[itemprop=address]')
    if addr_tag:
        return addr_tag.get_text(separator=' ', strip=True)
    possible = []
    for div in soup.find_all(['div', 'p'], string=re.compile(r'\d{1,5}\s+\w+\s+\w+')):
        possible.append(div.get_text(separator=' ', strip=True))
    return possible[0] if possible else None


def _clean_name(name: str) -> Optional[str]:
    if not name:
        return None
    cleaned = re.sub(r'\s+', ' ', name.strip())
    # Owner names should be 2 to 4 words
    words = cleaned.split()
    if 2 <= len(words) <= 4 and not any(char in cleaned for char in "<>{};()[]"):
        blacklist = {"our team", "about us", "contact us", "privacy policy", "read more", "learn more", "terms conditions"}
        if cleaned.lower() not in blacklist:
            return cleaned
    return None


def extract_owner_name(html_str: str, soup: Optional[BeautifulSoup] = None) -> Optional[str]:
    """Extract owner, manager, founder, or CEO name from JSON-LD, Meta tags, or text."""
    if not soup:
        soup = _soup_from_html(html_str)

    # 1. Inspect JSON-LD schemas
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            raw_text = script.string or script.get_text()
            if not raw_text:
                continue
            data = json.loads(raw_text)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                for key in ('founder', 'founders', 'owner', 'author', 'employee', 'director', 'ceo'):
                    val = item.get(key)
                    if isinstance(val, dict) and val.get('name'):
                        candidate = _clean_name(str(val['name']))
                        if candidate:
                            return candidate
                    elif isinstance(val, list):
                        for sub in val:
                            if isinstance(sub, dict) and sub.get('name'):
                                candidate = _clean_name(str(sub['name']))
                                if candidate:
                                    return candidate
                    elif isinstance(val, str):
                        candidate = _clean_name(val)
                        if candidate:
                            return candidate
        except Exception:
            pass

    # 2. Meta tags
    for meta in soup.find_all('meta'):
        prop = (meta.get('property') or meta.get('name') or '').lower()
        if prop in ('founder', 'owner', 'author', 'article:author', 'og:author'):
            val = meta.get('content', '').strip()
            candidate = _clean_name(val)
            if candidate:
                return candidate

    # 3. Text regex matching
    clean_soup = _clean_soup_for_text(soup)
    text = clean_soup.get_text(separator=' ')
    patterns = [
        r'(?:founder|co-founder|owner|proprietor|ceo|director|manager|managing director|store manager)\s*[:|-]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        r'founded\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        r'meet\s+(?:our\s+)?(?:founder|owner|manager|ceo)\s*[:|-]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
    ]
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            candidate = _clean_name(match.group(1))
            if candidate:
                return candidate

    return None


def find_page_by_keywords(soup: BeautifulSoup, base_url: str, keywords: List[str]) -> Optional[str]:
    for a in soup.find_all('a', href=True):
        txt = (a.get_text() or '').lower().strip()
        href = a['href'].lower().strip()
        if any(k in txt or k in href for k in keywords):
            actual_href = a['href'].strip()
            if actual_href.startswith('http'):
                return actual_href
            elif actual_href.startswith('/'):
                return f"{base_url.rstrip('/')}{actual_href}"
            else:
                return f"{base_url.rstrip('/')}/{actual_href}"
    return None


def find_contact_page(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    return find_page_by_keywords(
        soup, base_url, ['contact', 'support', 'help', 'reach us', 'get in touch', 'contact-us']
    )


def find_about_page(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    return find_page_by_keywords(
        soup, base_url, ['about', 'story', 'who we are', 'company', 'about-us', 'our-team', 'team']
    )


def extract_contact_form(soup: BeautifulSoup) -> Tuple[bool, List[str]]:
    form = soup.find('form')
    if not form:
        return False, []

    fields = []
    seen = set()
    for input_tag in form.find_all(['input', 'textarea', 'select']):
        input_type = input_tag.get('type', '').lower()
        if input_type in ('submit', 'button', 'image', 'hidden'):
            continue

        name = input_tag.get('name') or input_tag.get('id') or input_tag.get('placeholder')
        if name:
            norm = name.replace('_', ' ').replace('-', ' ').title()
            if norm not in seen:
                seen.add(norm)
                fields.append(norm)

    return True, fields
