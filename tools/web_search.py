from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen
import re

# Supported shopping sources. A source is only returned when BuyWise can
# actually retrieve a product/listing record from it; no URL or product is invented.
SOURCE_CATALOG = {
    "AliExpress": {"base": "https://www.aliexpress.com", "search": "https://www.aliexpress.com/w/wholesale-{q}.html", "groups": {"electronics", "general"}},
    "Temu": {"base": "https://www.temu.com", "search": "https://www.temu.com/search_result.html?search_key={q}", "groups": {"electronics", "general", "home"}},
    "Daraz Pakistan": {"base": "https://www.daraz.pk", "search": "https://www.daraz.pk/catalog/?q={q}", "groups": {"electronics", "fashion", "grocery", "home", "general"}},
    "Markaz App": {"base": "https://www.markaz.app", "search": "https://www.markaz.app/shop?search={q}", "groups": {"electronics", "fashion", "grocery", "home", "general"}},
    "OLX Pakistan": {"base": "https://www.olx.com.pk", "search": "https://www.olx.com.pk/items/q-{q}", "groups": {"electronics", "home", "general"}},
    "PriceOye": {"base": "https://priceoye.pk", "search": "https://priceoye.pk/mobiles", "groups": {"electronics"}},
    "Telemart": {"base": "https://www.telemart.pk", "search": "https://www.telemart.pk/catalogsearch/result/?q={q}", "groups": {"electronics", "home", "general"}},
    "Shophive": {"base": "https://www.shophive.com", "search": "https://www.shophive.com/catalogsearch/result/?q={q}", "groups": {"electronics", "home", "general"}},
    "Mega.pk": {"base": "https://www.mega.pk", "search": "https://www.mega.pk/mobiles/?q={q}", "groups": {"electronics"}},
    "iShopping": {"base": "https://www.ishopping.pk", "search": "https://www.ishopping.pk/catalogsearch/result/?q={q}", "groups": {"electronics"}},
    "HomeShopping": {"base": "https://www.homeshopping.pk", "search": "https://www.homeshopping.pk/search?q={q}", "groups": {"electronics", "home", "general"}},
    "Galaxy": {"base": "https://www.galaxy.pk", "search": "https://www.galaxy.pk/search?q={q}", "groups": {"electronics"}},
    "Naheed": {"base": "https://www.naheed.pk", "search": "https://www.naheed.pk/catalogsearch/result/?q={q}", "groups": {"grocery", "home", "general"}},
    "Foodpanda / Pandamart": {"base": "https://www.foodpanda.pk", "search": "https://www.foodpanda.pk/contents/pandamart", "groups": {"grocery"}},
    "Sapphire": {"base": "https://pk.sapphireonline.pk", "search": "https://pk.sapphireonline.pk/search?q={q}", "groups": {"fashion"}},
    "Khaadi": {"base": "https://pk.khaadi.com", "search": "https://pk.khaadi.com/search?q={q}", "groups": {"fashion"}},
    "Junaid Jamshed (J.)": {"base": "https://www.junaidjamshed.com", "search": "https://www.junaidjamshed.com/catalogsearch/result/?q={q}", "groups": {"fashion", "general"}},
}

PRODUCT_WORDS = re.compile(
    r"(iphone|galaxy|redmi|vivo|oppo|tecno|infinix|xiaomi|realme|motorola|honor|"
    r"oneplus|pixel|itel|nokia|dcode|sparx|xmobile|phone|mobile|laptop|tablet|"
    r"headphone|earbuds|watch|tv|shirt|dress|kurta|lawn|shoe|sandal|grocery|"
    r"rice|milk|oil|atta|cosmetic|perfume|skincare)",
    re.I,
)

def _fetch(url, timeout=8):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 BuyWiseAI/1.0"})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")

def _clean(text):
    return " ".join(text.split())

def _money(value):
    digits = re.sub(r"\D", "", str(value))
    return int(digits) if digits else None

def _budget_from_query(query):
    matches = re.findall(
        r"(?:under|below|less than|upto|up to|budget)\D{0,20}(?:PKR|Rs\.?|)\s*([0-9][0-9,]*)",
        query, re.I
    )
    values = [_money(x) for x in matches]
    values = [x for x in values if x]
    return max(values) if values else None

def _query_group(query):
    q = query.lower()
    if any(x in q for x in ("dress", "shirt", "kurta", "lawn", "abaya", "shoe", "sandal", "fashion", "clothes")):
        return "fashion"
    if any(x in q for x in ("grocery", "food", "milk", "atta", "rice", "oil", "snack")):
        return "grocery"
    if any(x in q for x in ("home", "appliance", "fridge", "refrigerator", "washing machine", "microwave")):
        return "home"
    if any(x in q for x in ("phone", "mobile", "laptop", "tablet", "earbuds", "headphone", "camera", "tv", "electronics")):
        return "electronics"
    return "general"

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

def _record_from_context(context, source, url):
    # Search/category pages are evidence-discovery pages, not product records.
    if not re.search(r"/(product|item|p/|dp/|mobiles/|products/)[^?]*", url, re.I):
        return None

    price_match = re.search(r"(PKR|Rs\.?|\$)\s*([0-9][0-9,]*(?:\.\d+)?)", context, re.I)
    if not price_match:
        return None

    symbol = price_match.group(1).upper()
    amount = price_match.group(2)
    price = _money(amount)
    if not price:
        return None

    currency = "USD" if symbol == "$" else "PKR"
    price_text = f"{currency} {price:,}"
    title = _clean(context[:140])

    # Reject obvious HTML/JS/navigation fragments.
    bad_title = (
        "privacy", "cookie policy", "goldlog", "setmetainfo", "javascript",
        "please ensure", "defaultpicurl", "function(", "arguments"
    )
    if any(x in title.lower() for x in bad_title):
        return None
    if len(title) < 8 or not PRODUCT_WORDS.search(title):
        return None

    return {
        "text": context[:900],
        "source": source,
        "source_type": "live_web",
        "price": price_text,
        "metadata": {
            "title": title[:120],
            "country": "Pakistan" if currency == "PKR" else "international",
            "currency": currency,
            "url": url,
            "specs": _extract_specs(context),
        },
    }

CATEGORY_TERMS = {
    "smartphone": ("phone", "smartphone", "mobile", "iphone", "galaxy", "redmi", "vivo", "oppo", "tecno", "infinix", "xiaomi", "realme", "motorola", "honor", "oneplus", "pixel", "itel", "nokia", "dcode", "sparx", "xmobile"),
    "laptop": ("laptop", "notebook", "macbook", "thinkpad", "ideapad", "vivobook", "pavilion"),
    "electronics": ("phone", "mobile", "laptop", "tablet", "headphone", "earbuds", "watch", "camera", "tv", "monitor", "keyboard", "mouse", "speaker", "console"),
    "appliance": ("fridge", "refrigerator", "washing machine", "microwave", "oven", "air conditioner", "air fryer", "blender", "appliance"),
    "fashion": ("shirt", "dress", "kurta", "lawn", "abaya", "shoe", "sandal", "clothing", "fashion"),
    "grocery": ("grocery", "rice", "milk", "oil", "atta", "flour", "snack", "food"),
}

SOURCE_GROUPS = {
    "Smartphone": {"electronics"},
    "Laptop": {"electronics"},
    "Electronics": {"electronics"},
    "Appliance": {"home", "electronics"},
    "Other": {"general", "electronics", "home", "fashion", "grocery"},
}

def _is_relevant_record(record, category="", query=""):
    text = " ".join([
        str(record.get("metadata", {}).get("title", "")),
        str(record.get("text", "")),
    ]).lower()
    category_key = str(category or "").strip().lower()
    category_key = category_key.rstrip("s")
    terms = CATEGORY_TERMS.get(category_key)
    if not terms:
        group = _query_group(query)
        terms = CATEGORY_TERMS.get(group)
    return not terms or any(term in text for term in terms)

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

def _price_contexts(html, source, page_url, limit=12):
    parser = _TextParser()
    parser.feed(html)
    text = _clean(" ".join(parser.parts))
    results = []
    for match in re.finditer(r"(?:Rs\.?|PKR|\$)\s*[0-9][0-9,]*(?:\.\d+)?", text, re.I):
        context = text[max(0, match.start()-220):min(len(text), match.end()+260)]
        if not PRODUCT_WORDS.search(context):
            continue
        record = _record_from_context(context, source, page_url)
        if record:
            results.append(record)
        if len(results) >= limit:
            break
    return results

def _search_source(source, config, query, budget, group):
    try:
        q = quote_plus(query)
        url = config["search"].format(q=q)
        html = _fetch(url)

        link_parser = _LinkParser()
        link_parser.feed(html)

        candidates = []
        seen = set()
        for href, anchor in link_parser.links:
            absolute = urljoin(config["base"], href)
            if absolute in seen or not anchor.strip():
                continue
            combined = anchor + " " + absolute
            if not PRODUCT_WORDS.search(combined):
                continue
            if not re.search(r"(product|item|mobile|phone|laptop|shirt|dress|shoe|p/|/dp/|/product|/mobiles/)", absolute, re.I):
                continue
            seen.add(absolute)
            candidates.append((absolute, anchor))

        results = []
        for product_url, anchor in candidates[:10]:
            try:
                detail_html = _fetch(product_url, timeout=6)

                # Parse the entire product page for specifications. Price snippets
                # are intentionally short, but specs such as battery/camera often
                # appear elsewhere on the same detail page.
                detail_parser = _TextParser()
                detail_parser.feed(detail_html)
                detail_text = _clean(" ".join(detail_parser.parts))

                detail = _price_contexts(detail_html, source, product_url, limit=1)
                if detail:
                    detail[0]["metadata"]["title"] = anchor[:120]
                    detail[0]["metadata"]["specs"] = _extract_specs(detail_text)
                    detail[0]["text"] = detail_text[:1600]
                    results.extend(detail)
            except Exception:
                continue
            if len(results) >= 12:
                break

        # Never turn a retailer's search/category page into a product record.
        # Only detail-page URLs discovered above are eligible.
        filtered = []
        for record in results:
            if budget:
                price = _money(record.get("price"))
                if price and price > budget:
                    continue
            filtered.append(record)
        return filtered[:12]
    except Exception:
        return []


def _search_engine_candidates(source, config, query):
    """Discover indexed product pages when a retailer's search page is JS/blocking."""
    search_url = (
        "https://www.google.com/search?q="
        + quote_plus(f"site:{config['base'].replace('https://','').replace('www.','')} {query}")
    )
    try:
        html = _fetch(search_url, timeout=8)
        parser = _LinkParser()
        parser.feed(html)
        candidates = []
        seen = set()
        for href, anchor in parser.links:
            if not href or not anchor:
                continue
            absolute = href
            if absolute.startswith("/url?q="):
                absolute = absolute.split("/url?q=", 1)[1].split("&", 1)[0]
            if not absolute.startswith("http"):
                continue
            if config["base"].split("//", 1)[-1].replace("www.", "") not in absolute.replace("www.", ""):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            candidates.append((absolute, anchor))
        return candidates[:10]
    except Exception:
        return []

def _search_source_with_fallback(source, config, query, budget, group):
    # First use the retailer's own search page. Some retailers expose only a
    # small subset or use client-side rendering, so supplement (rather than
    # replace) those results with indexed product pages.
    results = _search_source(source, config, query, budget, group)

    if len(results) >= 3:
        return results[:12]

    existing_urls = {
        str(item.get("metadata", {}).get("url", ""))
        for item in results
    }

    for product_url, anchor in _search_engine_candidates(source, config, query):
        if product_url in existing_urls:
            continue

        try:
            detail_html = _fetch(product_url, timeout=7)

            detail_parser = _TextParser()
            detail_parser.feed(detail_html)
            detail_text = _clean(" ".join(detail_parser.parts))

            detail = _price_contexts(detail_html, source, product_url, limit=1)
            if detail:
                detail[0]["metadata"]["title"] = anchor[:120]
                detail[0]["metadata"]["specs"] = _extract_specs(detail_text)
                detail[0]["text"] = detail_text[:1600]
                price = _money(detail[0].get("price"))

                # A PKR budget can only be compared against a PKR price.
                currency = detail[0].get("metadata", {}).get("currency")
                if not (
                    budget
                    and currency == "PKR"
                    and price
                    and price > budget
                ):
                    results.extend(detail)
                    existing_urls.add(product_url)
        except Exception:
            continue

        if len(results) >= 12:
            break

    return results[:12]

def search_web(query, category=""):
    """Search supported shopping sources and return only retrieved live evidence."""
    budget = _budget_from_query(query)
    group = _query_group(query)
    category_key = str(category or "").strip().lower().rstrip("s")
    category_name = category_key.title()
    allowed_groups = SOURCE_GROUPS.get(category_name)
    if not allowed_groups:
        allowed_groups = {group}
    selected = [
        (name, cfg) for name, cfg in SOURCE_CATALOG.items()
        if cfg["groups"] & allowed_groups
    ]

    results = []
    # Six concurrent fetches keeps multi-source search practical on Streamlit Cloud.
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(_search_source_with_fallback, name, cfg, query, budget, group): name
            for name, cfg in selected
        }
        for future in as_completed(futures):
            results.extend(future.result())

    unique = []
    seen = set()
    for item in results:
        if not _is_relevant_record(item, category, query):
            continue
        key = (
            item.get("source"),
            item.get("metadata", {}).get("url"),
            item.get("price"),
            item.get("metadata", {}).get("title"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    # Keep results diverse: up to 3 products per source and up to 30 total.
    # This prevents one marketplace from filling the entire result set.
    balanced = []
    counts = {}
    for item in unique:
        source = item.get("source", "Unknown")
        if counts.get(source, 0) >= 4:
            continue
        counts[source] = counts.get(source, 0) + 1
        balanced.append(item)
        if len(balanced) >= 30:
            break
    return balanced
