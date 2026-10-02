from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import quote
import re

SOURCES = {
    "PriceOye": "https://priceoye.pk/smartphones",
    "Daraz Pakistan": "https://www.daraz.pk/phones-tablets/",
}

class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

def _fetch(url, timeout=8):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 BuyWiseAI/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")

def _records_from_text(text, source):
    records = []
    prices = re.findall(r"(?:Rs\.?|PKR)\s*([0-9,]+)", text, flags=re.I)
    lines = [x.strip() for x in re.split(r"[\n|]", text) if x.strip()]
    for line in lines:
        if len(line) > 3 and len(line) < 180 and re.search(r"(phone|mobile|iphone|galaxy|redmi|vivo|oppo|tecno|infinix|xiaomi|realme|motorola|honor)", line, re.I):
            records.append({
                "text": line,
                "source": source,
                "source_type": "live_web",
                "metadata": {"title": line[:120], "country": "Pakistan", "currency": "PKR"}
            })
    for i, price in enumerate(prices[:20]):
        if i < len(records):
            records[i]["price"] = f"PKR {price}"
    return records[:20]

def search_web(query):
    """Fetch a small, transparent set of live Pakistan shopping evidence."""
    results = []
    for source, url in SOURCES.items():
        try:
            html = _fetch(url)
            parser = _TextParser()
            parser.feed(html)
            text = "\n".join(parser.parts)
            records = _records_from_text(text, source)
            results.extend(records)
        except Exception:
            continue
    return results
