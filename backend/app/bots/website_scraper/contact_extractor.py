import re
from typing import Set, List, Optional, Tuple
from bs4 import BeautifulSoup
from ...utils.regex import EMAIL_REGEX, PHONE_REGEX


def _soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _clean_soup_for_text(soup: BeautifulSoup) -> BeautifulSoup:
    """Make a copy of soup without script, style, svg, noscript, code tags."""
    soup_copy = BeautifulSoup(str(soup), "lxml")
    for tag in soup_copy(["script", "style", "svg", "path", "noscript", "code", "iframe"]):
        tag.decompose()
    return soup_copy


def _is_valid_phone(phone: str) -> bool:
    s = phone.strip()
    digits = re.sub(r'\D', '', s)
    num_digits = len(digits)

    # Standard international phone length is 7 to 15 digits
    if num_digits < 7 or num_digits > 15:
        return False

    # Reject dates (e.g. 2026-01-12, 12-01-2026, 2026/01/12)
    if re.match(r'^\d{4}[-\/\.]\d{2}[-\/\.]\d{2}$', s) or re.match(r'^\d{2}[-\/\.]\d{2}[-\/\.]\d{4}$', s):
        return False

    # Reject RGB / CSS color values like "255 255 255" or "0 0 0"
    parts = s.split()
    if len(parts) >= 3 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return False

    # Reject SVG viewBox coordinates like "0 0 24 24" or "0 0 500 500"
    if re.match(r'^(0\s+){1,3}\d+(\s+\d+)?$', s):
        return False

    # Reject low-entropy numbers like "0000000000" or "11111111"
    if len(set(digits)) <= 2:
        return False

    # Reject timestamp / Shopify internal product IDs (e.g. 100000+ IDs with 10+ digits starting with 1000)
    if num_digits >= 10 and digits.startswith("10000"):
        return False

    return True


def _clean_phone_string(phone: str) -> str:
    cleaned = re.sub(r'\s+', ' ', phone.strip())
    cleaned = re.sub(r'\s*-\s*', '-', cleaned)
    return cleaned


def extract_emails(html: str) -> Set[str]:
    soup = _soup_from_html(html)
    emails: Set[str] = set()
    # mailto links — explicit contact emails
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        if href.lower().startswith('mailto:'):
            email = href[7:].split('?')[0].strip()
            if email and not email.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css')):
                emails.add(email)

    # regex scan of clean visible text (excluding script, style, svg tags)
    clean_soup = _clean_soup_for_text(soup)
    clean_text = clean_soup.get_text(separator=' ')

    for match in EMAIL_REGEX.finditer(clean_text):
        email = match.group(0).strip()
        if not email.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.js', '.css', '.woff', '.ttf')):
            emails.add(email)
    return emails


def extract_phones(html: str) -> Set[str]:
    soup = _soup_from_html(html)
    phones: Set[str] = set()

    # 1. tel: links — explicit contact phone numbers
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        if href.lower().startswith('tel:'):
            phone = href[4:].split('?')[0].strip()
            phone = _clean_phone_string(phone)
            if phone and _is_valid_phone(phone):
                phones.add(phone)

    # 2. Microdata / schema.org telephone tags
    for tag in soup.find_all(attrs={"itemprop": "telephone"}):
        txt = tag.get_text(strip=True) or tag.get('content', '')
        txt = _clean_phone_string(txt)
        if txt and _is_valid_phone(txt):
            phones.add(txt)

    # 3. Regex scan of clean visible text (excluding script, style, svg tags)
    clean_soup = _clean_soup_for_text(soup)
    clean_text = clean_soup.get_text(separator=' ')

    for match in PHONE_REGEX.finditer(clean_text):
        raw_phone = match.group(0).strip()
        cleaned = _clean_phone_string(raw_phone)
        if _is_valid_phone(cleaned):
            phones.add(cleaned)

    return phones



def extract_address(html: str) -> Optional[str]:
    soup = _soup_from_html(html)
    addr_tag = soup.select_one('[itemprop=address]')
    if addr_tag:
        return addr_tag.get_text(separator=' ', strip=True)
    possible = []
    for div in soup.find_all(['div', 'p'], string=re.compile(r'\d{1,5}\s+\w+\s+\w+')):
        possible.append(div.get_text(separator=' ', strip=True))
    return possible[0] if possible else None


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
        soup, base_url, ['about', 'story', 'who we are', 'company', 'about-us']
    )


def find_privacy_policy(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    return find_page_by_keywords(
        soup, base_url, ['privacy', 'policy', 'privacy-policy']
    )


def find_terms_page(soup: BeautifulSoup, base_url: str) -> Optional[str]:
    return find_page_by_keywords(
        soup, base_url, ['terms', 'tos', 'conditions', 'terms-of-service', 'terms-of-use']
    )


def normalize_field_name(name: str) -> str:
    name_lower = name.lower()
    if 'name' in name_lower:
        return 'Name'
    if 'email' in name_lower or 'mail' in name_lower:
        return 'Email'
    if 'phone' in name_lower or 'tel' in name_lower or 'mobile' in name_lower:
        return 'Phone'
    if 'message' in name_lower or 'msg' in name_lower or 'comment' in name_lower or 'body' in name_lower or 'text' in name_lower:
        return 'Message'
    return name.replace('_', ' ').replace('-', ' ').title()


def extract_contact_form(soup: BeautifulSoup) -> Tuple[bool, List[str]]:
    form = soup.find('form')
    if not form:
        return False, []
    
    fields = []
    seen = set()
    for input_tag in form.find_all(['input', 'textarea', 'select']):
        # Ignore buttons and hidden fields
        input_type = input_tag.get('type', '').lower()
        if input_type in ('submit', 'button', 'image', 'hidden'):
            continue
            
        name = input_tag.get('name') or input_tag.get('id') or input_tag.get('placeholder')
        if name:
            norm = normalize_field_name(name.strip())
            if norm not in seen:
                seen.add(norm)
                fields.append(norm)
                
    return True, fields

