from html.parser import HTMLParser
from urllib.request import Request, urlopen
import re

SOURCES = {
    "PriceOye": "https://priceoye.pk/smartphones",
    "Daraz Pakistan": "https://www.daraz.pk/phones-tablets/",
}

PRODUCT_PATTERN = re.compile(
    r"(iphone|galaxy|redmi|vivo|oppo|tecno|infinix|xiaomi|realme|motorola|honor|"
    r"oneplus|google pixel|itel|nokia|dcode|sparx|xmobile|mobile|phone)",
    re.I,
)

def _fetch(url, timeout=8):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 BuyWiseAI/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")

def _clean(text):
    return " ".join(text.split())

def _extract_specs(text):
    specs = {}
    patterns = {
        "battery": r"(?:battery|capacity)\D{0,30}(\d{4,5})\s*mAh",
        "camera": r"(?:camera|main camera|rear camera)\D{0,40}(\d{2,3})\s*MP",
        "ram": r"(?:RAM)\D{0,20}(\d{1,2})\s*GB",
        "storage": r"(?:storage|ROM|internal)\D{0,20}(\d{2,4})\s*GB",
        "display": r"(?:display|screen)\D{0,50}([0-9.]+\s*(?:inch|in))",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.I)
        if match:
            specs[key] = match.group(1)
            if key == "battery":
                specs[key] += " mAh"
            elif key == "camera":
                specs[key] += " MP"
            elif key in ("ram", "storage"):
                specs[key] += " GB"
    return specs

def _records_from_text(text, source, url):
    normalized = _clean(text)
    price_matches = list(re.finditer(r"(?:Rs\.?|PKR)\s*([0-9,]+)", normalized, re.I))
    records = []

    for match in price_matches[:40]:
        start = max(0, match.start() - 350)
        end = min(len(normalized), match.end() + 350)
        context = normalized[start:end]
        if not PRODUCT_PATTERN.search(context):
            continue

        names = PRODUCT_PATTERN.findall(context)
        title_match = re.search(
            r"([A-Z][A-Za-z0-9+._-]{1,25}(?:\s+[A-Za-z0-9+._-]{1,25}){0,5})",
            context,
        )
        title = title_match.group(1).strip() if title_match else context[:120]
        specs = _extract_specs(context)

        records.append({
            "text": context[:700],
            "source": source,
            "source_type": "live_web",
            "price": f"PKR {match.group(1)}",
            "metadata": {
                "title": title[:120],
                "country": "Pakistan",
                "currency": "PKR",
                "url": url,
                "specs": specs,
            },
        })

    return records

def search_web(query):
    """Retrieve Pakistan shopping evidence with nearby product/spec context."""
    results = []
    for source, url in SOURCES.items():
        try:
            html = _fetch(url)
            parser = _TextParser()
            parser.feed(html)
            text = "\n".join(parser.parts)
            results.extend(_records_from_text(text, source, url))
        except Exception:
            continue

    # Remove exact duplicate records while preserving source evidence.
    unique = []
    seen = set()
    for item in results:
        key = (
            item.get("source"),
            item.get("price"),
            item.get("metadata", {}).get("title"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    return unique[:40]

class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = _clean(data)
        if text:
            self.parts.append(text)
