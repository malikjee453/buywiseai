from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen
import re

SOURCES = {
    "PriceOye": "https://priceoye.pk/mobile",
}

PRODUCT_PATH = re.compile(r"^/mobiles/[^/]+/[^/]+/?$", re.I)
PRODUCT_WORDS = re.compile(
    r"(iphone|galaxy|redmi|vivo|oppo|tecno|infinix|xiaomi|realme|motorola|honor|"
    r"oneplus|pixel|itel|nokia|dcode|sparx|xmobile|phone|mobile)",
    re.I,
)

def _fetch(url, timeout=10):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 BuyWiseAI/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")

def _clean(text):
    return " ".join(text.split())

def _money(value):
    digits = re.sub(r"\D", "", str(value))
    return int(digits) if digits else None

def _budget_from_query(query):
    matches = re.findall(r"(?:under|below|less than|upto|up to|budget)\D{0,20}(?:PKR|Rs\.?|)\s*([0-9][0-9,]*)", query, re.I)
    values = [_money(x) for x in matches]
    values = [x for x in values if x]
    return max(values) if values else None

def _extract_specs(text):
    specs = {}
    patterns = {
        "battery": r"(?:battery|type)\D{0,35}(\d{4,5})\s*mAh",
        "camera": r"(?:back camera|main camera|rear camera|camera)\D{0,45}(\d{1,3})\s*MP",
        "ram": r"\bRAM\D{0,25}([0-9]{1,2}(?:GB|\s*GB))",
        "storage": r"(?:internal memory|storage|ROM)\D{0,30}([0-9]{2,4}(?:GB|\s*GB))",
        "display": r"(?:screen size|display|screen)\D{0,50}([0-9.]+\s*(?:inch|inches|in))",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            value = _clean(match.group(1))
            if key in ("ram", "storage") and "gb" not in value.lower():
                value += " GB"
            if key == "battery" and "mah" not in value.lower():
                value += " mAh"
            if key == "camera" and "mp" not in value.lower():
                value += " MP"
            specs[key] = value
    return specs

def _product_detail(url, source):
    try:
        html = _fetch(url)
        parser = _TextParser()
        parser.feed(html)
        text = _clean(" ".join(parser.parts))

        title_match = re.search(r"(?:logo|Image: badges logo)?\s*([A-Z][A-Za-z0-9+._()\- ]{2,80}?)(?:\s+Price in Pakistan|\s+Price|\s+\d+\.\d+\s*\|)", text, re.I)
        title = title_match.group(1).strip() if title_match else ""
        price_match = re.search(r"(?:Rs\s*|PKR\s*)([0-9][0-9,]*)", text, re.I)
        specs = _extract_specs(text)

        if not title or not price_match:
            return None

        price = _money(price_match.group(1))
        if not price:
            return None

        return {
            "text": text[:1200],
            "source": source,
            "source_type": "live_web",
            "price": f"PKR {price:,}",
            "metadata": {
                "title": title[:120],
                "country": "Pakistan",
                "currency": "PKR",
                "url": url,
                "specs": specs,
            },
        }
    except Exception:
        return None

class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs = dict(attrs)
            self._href = attrs.get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(_clean(data))

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, _clean(" ".join(self._text))))
            self._href = None
            self._text = []

class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = _clean(data)
        if text:
            self.parts.append(text)

def search_web(query):
    """Retrieve product-level Pakistan shopping evidence with direct links."""
    results = []
    budget = _budget_from_query(query)

    try:
        html = _fetch(SOURCES["PriceOye"])
        source = "PriceOye"

        link_parser = _LinkParser()
        link_parser.feed(html)

        candidates = []
        seen_urls = set()
        for href, anchor_text in link_parser.links:
            absolute = urljoin(SOURCES["PriceOye"], href)
            path = re.sub(r"https?://[^/]+", "", absolute)
            if not PRODUCT_PATH.match(path):
                continue
            if absolute in seen_urls:
                continue
            if not PRODUCT_WORDS.search(anchor_text + " " + absolute):
                continue
            seen_urls.add(absolute)
            candidates.append(absolute)

        # Fetch a small number of real product pages to keep latency and TPM controlled.
        for product_url in candidates[:18]:
            record = _product_detail(product_url, source)
            if not record:
                continue
            if budget and _money(record["price"]) and _money(record["price"]) > budget:
                continue
            results.append(record)
            if len(results) >= 12:
                break

        # Fallback to category-page records if product links could not be parsed.
        if not results:
            parser = _TextParser()
            parser.feed(html)
            text = _clean(" ".join(parser.parts))
            for match in re.finditer(r"(?:Rs\.?|PKR)\s*([0-9,]+)", text, re.I):
                start = max(0, match.start() - 220)
                end = min(len(text), match.end() + 220)
                context = text[start:end]
                if not PRODUCT_WORDS.search(context):
                    continue
                price = _money(match.group(1))
                if budget and price and price > budget:
                    continue
                results.append({
                    "text": context[:700],
                    "source": source,
                    "source_type": "live_web",
                    "price": f"PKR {price:,}" if price else f"PKR {match.group(1)}",
                    "metadata": {
                        "title": context[:100],
                        "country": "Pakistan",
                        "currency": "PKR",
                        "url": SOURCES["PriceOye"],
                        "specs": _extract_specs(context),
                    },
                })
                if len(results) >= 12:
                    break
    except Exception:
        pass

    unique = []
    seen = set()
    for item in results:
        key = (
            item.get("source"),
            item.get("metadata", {}).get("url"),
            item.get("price"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
