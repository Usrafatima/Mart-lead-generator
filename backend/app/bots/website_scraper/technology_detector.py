import logging
import re
from typing import List, Dict, Tuple
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_DETECTION_PATTERNS: Dict[str, List[re.Pattern]] = {
    "wordpress": [re.compile(r"wp-content", re.I), re.compile(r"wp-includes", re.I), re.compile(r"wordpress", re.I)],
    "woocommerce": [re.compile(r"woocommerce", re.I), re.compile(r"wc-add-to-cart", re.I)],
    "shopify": [re.compile(r"cdn\.shopify\.com", re.I), re.compile(r"shopify\.myshopify\.com", re.I), re.compile(r"Shopify\.theme", re.I)],
    "wix": [re.compile(r"wixstatic\.com", re.I), re.compile(r"wix\.com", re.I), re.compile(r"_wix_", re.I)],
    "squarespace": [re.compile(r"squarespace\.com", re.I), re.compile(r"sqsp", re.I), re.compile(r"static1\.squarespace\.com", re.I)],
    "webflow": [re.compile(r"webflow\.com", re.I), re.compile(r"data-wf-page", re.I), re.compile(r"webflow\.js", re.I)],
    "magento": [re.compile(r"mage\/cache", re.I), re.compile(r"magento", re.I), re.compile(r"Mage\.Cookies", re.I)],
    "cloudflare": [re.compile(r"cloudflare", re.I), re.compile(r"cf-beacon", re.I), re.compile(r"cf[-_]\w+", re.I)],
    "react": [re.compile(r"react\.js", re.I), re.compile(r"data-reactroot", re.I)],
    "next.js": [re.compile(r"__next", re.I), re.compile(r"next\.data", re.I)],
    "vue": [re.compile(r"vue\.js", re.I), re.compile(r"data-vue", re.I)],
}

_DELIVERY_PROVIDERS: Dict[str, re.Pattern] = {
    "Deliveroo": re.compile(r"deliveroo", re.I),
    "Uber Eats": re.compile(r"ubereats|uber\.com\/eats", re.I),
    "Foodpanda": re.compile(r"foodpanda", re.I),
    "Just Eat": re.compile(r"just-eat|justeat", re.I),
    "DoorDash": re.compile(r"doordash", re.I),
    "Careem": re.compile(r"careem", re.I),
    "Bykea": re.compile(r"bykea", re.I),
    "Zomato": re.compile(r"zomato", re.I),
    "Talabat": re.compile(r"talabat", re.I),
}


class TechnologyDetector:
    """Detect CMS, frameworks, e-commerce, delivery providers, and ordering methods."""

    def __init__(self, html: str):
        self.html = html
        self.soup = BeautifulSoup(html, "lxml")

    def detect(self) -> List[str]:
        detected: set[str] = set()

        for tech, patterns in _DETECTION_PATTERNS.items():
            for pat in patterns:
                if pat.search(self.html):
                    detected.add(tech)
                    break

        metas = {
            meta.get('name', '').lower(): meta.get('content', '').lower()
            for meta in self.soup.find_all('meta') if meta.get('name')
        }
        generator = metas.get('generator', '')
        for cms in ("wordpress", "shopify", "magento", "wix", "squarespace", "webflow"):
            if cms in generator:
                detected.add(cms)

        name_map = {
            "wordpress": "WordPress",
            "woocommerce": "WooCommerce",
            "shopify": "Shopify",
            "wix": "Wix",
            "squarespace": "Squarespace",
            "webflow": "Webflow",
            "magento": "Magento",
            "cloudflare": "Cloudflare",
            "react": "React",
            "next.js": "Next.js",
            "vue": "Vue",
        }
        normalized = [name_map.get(tech, tech.capitalize()) for tech in detected]
        return sorted(normalized)

    def detect_delivery_providers(self) -> List[str]:
        providers = set()
        for name, pattern in _DELIVERY_PROVIDERS.items():
            if pattern.search(self.html):
                providers.add(name)

        if re.search(r"home delivery|doorstep delivery|free delivery|express delivery|our delivery", self.html, re.I):
            providers.add("In-house Delivery")

        if re.search(r"click and collect|store pickup|curbside pickup|collection|takeaway", self.html, re.I):
            providers.add("Collection / Pickup")

        return sorted(list(providers))

    def detect_order_and_delivery(self) -> Tuple[str, str, str]:
        """
        Returns (order_method, order_method_detail, delivery_system).
        order_method choices: "online", "phone", "in_person", "unknown"
        """
        techs = self.detect()
        providers = self.detect_delivery_providers()

        has_cart_or_checkout = bool(
            re.search(r"add to cart|add-to-cart|checkout|buy now|shopping cart|view cart|place order", self.html, re.I)
        )
        is_ecommerce = any(t in techs for t in ["Shopify", "WooCommerce", "Magento"]) or has_cart_or_checkout

        has_whatsapp_order = bool(
            re.search(r"wa\.me|api\.whatsapp\.com|whatsapp", self.html, re.I)
            and re.search(r"order|buy|catalog|price|chat to order", self.html, re.I)
        )

        has_phone_order = bool(
            re.search(r"tel:|call to order|phone order|order by phone|call for delivery", self.html, re.I)
        )

        delivery_sys = ", ".join(providers) if providers else ("In-house Delivery" if is_ecommerce else "None")

        if is_ecommerce:
            cms_name = next((t for t in techs if t in ["Shopify", "WooCommerce", "Magento"]), "E-Commerce")
            return "online", f"Online (Add to Cart / {cms_name})", delivery_sys

        if has_whatsapp_order:
            return "online", "WhatsApp Ordering", delivery_sys

        if providers:
            return "online", f"Delivery Apps ({', '.join(providers)})", delivery_sys

        if has_phone_order:
            return "phone", "Phone Order", delivery_sys

        return "in_person", "Walk-in / In-Person", delivery_sys
