from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin, unquote
from urllib.request import Request, urlopen
import re
import json
import logging

logger = logging.getLogger(__name__)
from tools.product_validator import validate_record

# Supported shopping sources. A source is only returned when BuyWise can
# actually retrieve a product/listing record from it; no URL or product is invented.
SOURCE_CATALOG = {
    "AliExpress": {"base": "https://www.aliexpress.com", "search": "https://www.aliexpress.com/w/wholesale-{q}.html", "groups": {"electronics", "general"}},
    "Temu": {"base": "https://www.temu.com", "search": "https://www.temu.com/search_result.html?search_key={q}", "groups": {"electronics", "general", "home"}},
    "Daraz Pakistan": {"base": "https://www.daraz.pk", "search": "https://www.daraz.pk/catalog/?q={q}", "groups": {"electronics", "fashion", "grocery", "home", "general"}},
    "Markaz App": {"base": "https://www.markaz.app", "search": "https://www.markaz.app/shop?search={q}", "groups": {"electronics", "fashion", "grocery", "home", "general"}},
    "OLX Pakistan": {"base": "https://www.olx.com.pk", "search": "https://www.olx.com.pk/items/q-{q}", "groups": {"electronics", "home", "general"}},
    "PriceOye": {"base": "https://priceoye.pk", "search": "https://priceoye.pk/mobiles", "groups": {"electronics"}},
    "Telemart": {"base": "https://www.telemart.pk", "search": "https://www.telemart.pk/collections/smart-phones", "groups": {"electronics", "home", "general"}},
    "Shophive": {"base": "https://www.shophive.com", "search": "https://www.shophive.com/catalogsearch/result/?q={q}", "groups": {"electronics", "home", "general"}},
    "Mega.pk": {"base": "https://www.mega.pk", "search": "https://www.mega.pk/mobiles/", "groups": {"electronics"}},
    "iShopping": {"base": "https://www.ishopping.pk", "search": "https://www.ishopping.pk/mobiles", "groups": {"electronics"}},
    "HomeShopping": {"base": "https://www.homeshopping.pk", "search": "https://www.homeshopping.pk/mobiles", "groups": {"electronics", "home", "general"}},
    "Galaxy": {"base": "https://www.galaxy.pk", "search": "https://www.galaxy.pk/search?q={q}", "groups": {"electronics"}},
    "Naheed": {"base": "https://www.naheed.pk", "search": "https://www.naheed.pk/catalogsearch/result/?q={q}", "groups": {"grocery", "home", "general"}},
    "Foodpanda / Pandamart": {"base": "https://www.foodpanda.pk", "search": "https://www.foodpanda.pk/contents/pandamart", "groups": {"grocery"}},
    "Sapphire": {"base": "https://pk.sapphireonline.pk", "search": "https://pk.sapphireonline.pk/search?q={q}", "groups": {"fashion"}},
    "Khaadi": {"base": "https://pk.khaadi.com", "search": "https://pk.khaadi.com/search?q={q}", "groups": {"fashion"}},
    "Junaid Jamshed (J.)": {"base": "https://www.junaidjamshed.com", "search": "https://www.junaidjamshed.com/catalogsearch/result/?q={q}", "groups": {"fashion", "general"}},
}

# Search Pakistani shopping sources first. These are the core sources for
# local price comparison; secondary sources are queried only when the first
# pass does not return enough useful evidence.
PRIMARY_PK_SOURCES = (
    "Daraz Pakistan",
    "PriceOye",
    "Telemart",
    "Shophive",
    "Mega.pk",
    "iShopping",
)

SECONDARY_PK_SOURCES = (
    "HomeShopping",
    "Galaxy",
    "Naheed",
    "OLX Pakistan",
    "Markaz App",
    "Sapphire",
    "Khaadi",
    "Junaid Jamshed (J.)",
)

INTERNATIONAL_SOURCES = (
    "AliExpress",
    "Temu",
)

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

def _enrich_detail_metadata(record, detail_text, source):
    """Attach retailer-specific evidence extracted from the live product page."""
    metadata = record.setdefault("metadata", {})
    metadata["specs"] = _extract_specs(detail_text)
    text = _clean(detail_text)
    patterns = {
        "Daraz Pakistan": {
            "seller": r"(?:sold by|seller)\s*[:\-]?\s*([^|]{2,80}?)(?=\s+(?:seller rating|rating|reviews|warranty|delivery)\b|$)",
            "seller_rating": r"(?:seller rating)\s*[:\-]?\s*([0-9.]+\s*(?:/\s*5|%))",
            "product_rating": r"(?:rating|product rating)\s*[:\-]?\s*([0-9.]+\s*(?:/\s*5|%))",
            "reviews": r"(?:reviews?|ratings?)\s*[:\-]?\s*([0-9][0-9,]*)",
            "warranty": r"(?:warranty)\s*[:\-]?\s*([^|]{3,80}?)(?=\s+(?:delivery|seller|rating)\b|$)",
            "delivery": r"(?:delivery|shipping)\s*[:\-]?\s*([^|]{3,80}?)(?=\s+(?:warranty|seller|rating)\b|$)",
            "variant": r"(?:color|colour|variant|storage|ram)\s*[:\-]?\s*([^|]{2,60})",
        },
        "Shophive": {
            "warranty": r"(?:warranty|brand warranty)\s*[:\-]?\s*([^|]{3,80}?)(?=\s+(?:availability|rating|reviews)\b|$)",
            "availability": r"(?:availability|stock|status)\s*[:\-]?\s*([^|]{2,50})",
            "rating": r"(?:rating|stars?)\s*[:\-]?\s*([0-9.]+\s*(?:/\s*5|%))",
            "reviews": r"(?:reviews?)\s*[:\-]?\s*([0-9][0-9,]*)",
        },
        "Mega.pk": {
            "warranty": r"(?:warranty|brand warranty)\s*[:\-]?\s*([^|]{3,80}?)(?=\s+(?:availability|rating|reviews)\b|$)",
            "availability": r"(?:availability|stock|status)\s*[:\-]?\s*([^|]{2,50})",
            "rating": r"(?:rating|stars?)\s*[:\-]?\s*([0-9.]+\s*(?:/\s*5|%))",
            "reviews": r"(?:reviews?)\s*[:\-]?\s*([0-9][0-9,]*)",
        },
        "iShopping": {
            "warranty": r"(?:warranty|brand warranty)\s*[:\-]?\s*([^|]{3,80}?)(?=\s+(?:availability|rating|reviews)\b|$)",
            "availability": r"(?:availability|stock|status)\s*[:\-]?\s*([^|]{2,50})",
            "rating": r"(?:rating|stars?)\s*[:\-]?\s*([0-9.]+\s*(?:/\s*5|%))",
            "reviews": r"(?:reviews?)\s*[:\-]?\s*([0-9][0-9,]*)",
        },
    }
    for key, pattern in patterns.get(source, {}).items():
        match = re.search(pattern, text, re.I)
        if match:
            value = _clean(match.group(1))
            if value:
                metadata[key] = value[:120]
    return record

def _is_product_url(source, url):
    """Return True only for URLs that look like individual product pages."""
    path = url.split("?", 1)[0].lower().rstrip("/")
    if not path:
        return False

    if source == "Daraz Pakistan":
        return bool(re.search(r"/products/[^/]+-i\d+\.html$", path, re.I))
    if source == "Mega.pk":
        return bool(re.search(r"/mobiles_products/\d+/[^/]+\.html$", path, re.I)) or bool(re.search(r"/mobiles/[^/]+$", path, re.I))
    if source == "Shophive":
        blocked = ("/catalogsearch", "/search", "/category", "/categories", "/customer", "/checkout", "/cart", "/blog")
        if any(item in path for item in blocked):
            return False
        return "/mobile-phones/" in path or "/laptops/" in path or "/tablets/" in path or path.endswith(".html")
    if source == "iShopping":
        blocked = ("/category", "/catalogsearch", "/search", "/customer", "/checkout", "/cart", "/blog", "/sale", "/brands", "/pre-owned", "/accessories")
        if any(item in path for item in blocked):
            return False
        return bool(re.search(r"/mobiles/[^/]+$", path)) or bool(re.search(r"/[^/]+-price-in-pakistan$", path))
    if source == "Telemart":
        return "/products/" in path and path.count("/") >= 4
    if re.search(r"/(product|item|p|dp|products)/[^/]+", path, re.I):
        return True
    blocked = ("/search", "/catalogsearch", "/category", "/categories/", "/collection", "/collections/", "/shop", "/cart", "/account", "/checkout", "/blog", "/tag/", "/page/")
    if any(item in path for item in blocked):
        return False
    return False


def _record_from_context(context, source, url):
    # Search/category pages are evidence-discovery pages, not product records.
    if not _is_product_url(source, url):
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

    # Reject obviously broken price snippets. Some retailer pages contain
    # installment fragments, quantities, ratings, or unrelated numbers such
    # as "Rs 3" before the actual product price.
    if currency == "PKR" and price < 1000:
        return None
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

    return validate_record({
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
            "price_source": "product_page_text",
        },
    })

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
    metadata = record.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    title = str(metadata.get("title", "")).lower().strip()
    text = str(record.get("text", "")).lower()

    category_key = str(category or "").strip().lower().rstrip("s")
    terms = CATEGORY_TERMS.get(category_key)
    if not terms:
        terms = CATEGORY_TERMS.get(_query_group(query))

    if not terms:
        return True

    # For a specific category such as smartphone, the product title is the
    # authoritative relevance signal. Do not fall back to page/footer text:
    # retailer navigation can contain unrelated words such as "phone".
    return any(term in title for term in terms)

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

def _jsonld_product_records(html, source, page_url):
    """Extract Product/Offer records embedded in retailer HTML."""
    results = []
    seen = set()

    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.I | re.S,
    )

    def walk(value):
        if isinstance(value, dict):
            value_type = value.get("@type", "")
            if (
                (isinstance(value_type, str) and value_type.lower() == "product")
                or (
                    isinstance(value_type, list)
                    and any(str(item).lower() == "product" for item in value_type)
                )
            ):
                yield value
            graph = value.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    yield from walk(item)
            for key in ("itemListElement", "items", "item", "mainEntity", "mainEntityOfPage"):
                items = value.get(key)
                if isinstance(items, list):
                    for item in items:
                        yield from walk(item)
                elif isinstance(items, dict):
                    yield from walk(items)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)

    for raw in scripts:
        try:
            data = json.loads(raw.strip())
        except Exception:
            continue

        for product in walk(data):
            name = _clean(str(product.get("name", "")))
            offers = product.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if not isinstance(offers, dict):
                offers = {}

            product_url = str(
                product.get("url")
                or offers.get("url")
                or page_url
            ).strip()
            if not product_url.startswith("http"):
                product_url = urljoin(page_url, product_url)

            price = offers.get("price") or offers.get("lowPrice")
            currency = str(offers.get("priceCurrency", "PKR")).upper()
            if not name or not price or not _is_product_url(source, product_url):
                continue

            amount = _money(price)
            if not amount or (currency == "PKR" and amount < 1000):
                continue

            key = (product_url, name, amount)
            if key in seen:
                continue
            seen.add(key)

            results.append(validate_record({
                "text": name,
                "source": source,
                "source_type": "live_web",
                "price": f"{currency} {amount:,}",
                "metadata": {
                    "title": name[:120],
                    "country": "Pakistan" if currency == "PKR" else "international",
                    "currency": currency,
                    "url": product_url,
                    "specs": {},
                    "price_source": "jsonld_product_offer",
                },
            }))

    return results


def _price_contexts(html, source, page_url, limit=12):
    """Extract product prices while rejecting installment/monthly-payment noise."""
    parser = _TextParser()
    parser.feed(html)
    text = _clean(" ".join(parser.parts))
    matches = []

    for match in re.finditer(
        r"(?:Rs\.?|PKR|\$)\s*[0-9][0-9,]*(?:\.\d+)?",
        text,
        re.I,
    ):
        value = _money(match.group(0))
        if not value:
            continue

        context = text[max(0, match.start()-320):min(len(text), match.end()+420)]
        if not PRODUCT_WORDS.search(context):
            continue

        window = context.lower()
        score = 0

        for token in (
            "latest price", "current price", "our price", "sale price",
            "price in pakistan", "price:", "price ", "buy now",
        ):
            if token in window:
                score += 4

        for token in (
            "per month", "/month", "monthly", "installment", "installments",
            "emi", "down payment", "advance payment", "deposit",
        ):
            if token in window:
                score -= 12

        label_match = re.search(
            r"(?:latest|current|our|sale)?\s*price(?:\s+in\s+pakistan)?\s*[:\-]?\s*(?:rs\.?|pkr)?\s*[0-9]",
            window,
            re.I,
        )
        if label_match:
            score += 8

        if value < 10000:
            score -= 2

        matches.append((score, value, match))

    matches.sort(key=lambda item: (-item[0], item[1]))

    results = []
    seen_prices = set()
    for _, value, match in matches:
        if value in seen_prices:
            continue
        context = text[max(0, match.start()-320):min(len(text), match.end()+420)]
        record = _record_from_context(context, source, page_url)
        if record:
            results.append(record)
            seen_prices.add(value)
        if len(results) >= limit:
            break

    return results


def _listing_records_from_links(html, source, page_url, budget=None, limit=6):
    """Extract product-card evidence from listing HTML.

    Retailer cards vary widely: prices may be separated from the anchor by
    nested markup, tracking attributes, or several thousand characters of HTML.
    We therefore locate the exact product href first, then inspect a generous
    local card window and choose a sensible PKR price from that window.
    """
    parser = _LinkParser()
    parser.feed(html)
    results = []
    seen = set()

    candidates = []
    for href, anchor in parser.links:
        if not href or not anchor:
            continue
        absolute = urljoin(page_url, href).split("?", 1)[0].rstrip("/")
        anchor = _clean(unquote(anchor))
        if absolute in seen or not _is_product_url(source, absolute):
            continue
        if not PRODUCT_WORDS.search(anchor):
            continue
        seen.add(absolute)
        candidates.append((href, absolute, anchor))

    for raw_href, absolute, anchor in candidates:
        escaped_href = re.escape(raw_href)
        match = re.search(
            r"""href\s*=\s*["']""" + escaped_href + r"""["']""",
            html,
            re.I,
        )
        if not match:
            match = re.search(re.escape(absolute), html, re.I)
        if not match:
            continue

        start = max(0, match.start() - 5000)
        end = min(len(html), match.end() + 5000)
        raw_context = html[start:end]
        visible_context = _clean(
            unquote(re.sub(r"<[^>]+>", " ", raw_context))
        )

        # Prefer an in-budget price when the user supplied a budget.
        price_matches = list(
            re.finditer(
                r"(?:PKR|Rs\.?)\s*[0-9][0-9,]*(?:\.\d+)?",
                visible_context,
                re.I,
            )
        )
        chosen_price = None
        for price_match in price_matches:
            value = _money(price_match.group(0))
            if value and value >= 1000 and (not budget or value <= budget):
                chosen_price = price_match.group(0)
                break
        if chosen_price is None and price_matches:
            chosen_price = price_matches[0].group(0)
        if not chosen_price:
            continue

        # Put the exact product title first. This prevents navigation/footer
        # text in the card window from becoming the displayed product name.
        context = f"{anchor} {chosen_price} {visible_context}"
        record = _record_from_context(context, source, absolute)
        if not record:
            continue

        price = _money(record.get("price"))
        if budget and (not price or price > budget):
            continue

        clean_title = re.sub(
            r"\s+(?:ask other llm models|refine your code|refine the code).*$",
            "",
            anchor,
            flags=re.I,
        ).strip()
        if len(clean_title) < 8:
            continue

        record["metadata"]["title"] = clean_title[:120]
        record["metadata"]["url"] = absolute
        record["metadata"]["price_source"] = "listing_page_text"
        record["metadata"]["listing_verified"] = False
        results.append(record)

        if len(results) >= limit:
            break

    return results


def _search_source(source, config, query, budget, group):
    try:
        q = quote_plus(query)
        url = config["search"].format(q=q)
        html = _fetch(url, timeout=5)

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
            if not _is_product_url(source, absolute):
                continue
            seen.add(absolute)
            candidates.append((absolute, anchor))

        results = _jsonld_product_records(html, source, url)
        # Try more candidates because some retailer pages contain accessories
        # before the actual smartphone products.
        for product_url, anchor in candidates[:8]:
            try:
                detail_html = _fetch(product_url, timeout=4)

                # Parse the entire product page for specifications. Price snippets
                # are intentionally short, but specs such as battery/camera often
                # appear elsewhere on the same detail page.
                detail_parser = _TextParser()
                detail_parser.feed(detail_html)
                detail_text = _clean(" ".join(detail_parser.parts))

                detail = _price_contexts(detail_html, source, product_url, limit=1)
                if detail:
                    detail[0]["metadata"]["title"] = anchor[:120]
                    detail[0]["metadata"]["price_source"] = "product_page_text"
                    detail[0]["text"] = detail_text[:1800]
                    _enrich_detail_metadata(detail[0], detail_text, source)
                    results.extend(detail)
            except Exception:
                continue
            if len(results) >= 6:
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
        return filtered[:8]
    except Exception:
        return []


def _search_engine_candidates(source, config, query):
    """Discover exact retailer product URLs from public search indexes.

    Retailer search pages are frequently JavaScript-only. Search indexes still
    expose the underlying product URLs, so URL discovery is deliberately kept
    separate from retailer-page scraping.
    """
    host = config["base"].split("//", 1)[-1].replace("www.", "")
    search_queries = [
        f"site:{host} {query} Pakistan price",
        f"site:{host} smartphone PKR",
    ]
    candidates = []
    seen = set()

    def add_url(raw_url, anchor=""):
        absolute = unquote(raw_url).replace("&amp;", "&").strip(" \t\r\n'\"<>(),")
        if not absolute.startswith("http"):
            return False
        if host not in absolute.replace("www.", "").lower():
            return False
        if absolute in seen or not _is_product_url(source, absolute):
            return False
        seen.add(absolute)
        candidates.append((absolute, _clean(anchor) or absolute.rsplit("/", 1)[-1]))
        return True

    for engine in (
        "https://www.google.com/search?q=",
        "https://www.bing.com/search?q=",
    ):
        for search_query in search_queries:
            try:
                page = _fetch(engine + quote_plus(search_query) + "&num=10", timeout=5)

                # First try parsed anchors.
                parser = _LinkParser()
                parser.feed(page)
                for href, anchor in parser.links:
                    href = unquote(href)
                    if href.startswith("/url?q="):
                        href = href.split("/url?q=", 1)[1].split("&", 1)[0]
                    elif "url=" in href and href.startswith("/url?"):
                        href = href.split("url=", 1)[1].split("&", 1)[0]
                    add_url(href, anchor)
                    if len(candidates) >= 12:
                        return candidates

                # Then scan the raw result HTML. This catches Google/Bing
                # redirect formats that HTMLParser cannot interpret.
                pattern = rf"https?://(?:www\.)?{re.escape(host)}[^\\s\"'<>]+"
                for raw in re.findall(pattern, page, re.I):
                    add_url(raw)
                    if len(candidates) >= 12:
                        return candidates
            except Exception:
                continue

    return candidates

def _dedicated_catalog_candidates(source, config, query, budget, limit=6):
    """Discover exact product URLs, then verify each exact detail page."""
    if source not in {"Daraz Pakistan", "Mega.pk", "Shophive", "iShopping"}:
        return []

    listing_url = config["search"]
    if source == "Daraz Pakistan":
        listing_url = config["search"].format(q=quote_plus(query))

    discovered = []
    seen = set()

    def add_url(raw_url, anchor=""):
        absolute = urljoin(listing_url, unquote(raw_url))
        canonical = absolute.split("?", 1)[0].rstrip("/")
        if canonical in seen or not _is_product_url(source, canonical):
            return
        if anchor and not PRODUCT_WORDS.search(anchor + " " + canonical):
            return
        seen.add(canonical)
        discovered.append((canonical, _clean(anchor)))

    try:
        html = _fetch(listing_url, timeout=5)
    except Exception:
        html = ""

    if html:
        parser = _LinkParser()
        parser.feed(html)
        for href, anchor in parser.links:
            add_url(href, anchor)
            if len(discovered) >= limit * 3:
                break

        host = config["base"].split("//", 1)[-1].replace("www.", "")
        if source == "Daraz Pakistan":
            pattern = rf'https?://(?:www\.)?{re.escape(host)}/products/[^\s"<>]+-i\d+\.html'
        elif source == "Mega.pk":
            pattern = rf'https?://(?:www\.)?{re.escape(host)}/(?:mobiles_products/\d+/[^\s"<>]+|mobiles/[^\s"<>]+)'
        elif source == "Shophive":
            pattern = rf'https?://(?:www\.)?{re.escape(host)}/[^\s"<>]+'
        else:
            pattern = rf'https?://(?:www\.)?{re.escape(host)}/(?:mobiles/[^\s"<>]+|[^\s"<>]+-price-in-pakistan)'
        for raw_url in re.findall(pattern, html, re.I):
            add_url(raw_url, raw_url)
            if len(discovered) >= limit * 3:
                break

    # Prioritize catalog products already known to fit the budget.
    catalog_records = _listing_records_from_links(
        html, source, listing_url, budget=budget, limit=limit * 3
    ) if html else []
    catalog_urls = {
        str(item.get("metadata", {}).get("url", ""))
        for item in catalog_records
    }

    # Search indexes are a second discovery path when retailer HTML is
    # JavaScript-heavy or hides product links. Trigger this based on usable
    # catalog records, not raw URL count: a page can expose many URLs while
    # none of their detail pages are fetchable or within the user's budget.
    if len(catalog_records) < limit:
        for product_url, anchor in _search_engine_candidates(source, config, query):
            add_url(product_url, anchor)
            if len(discovered) >= limit * 4:
                break

    def verify_detail(item):
        product_url, anchor = item
        try:
            detail_html = _fetch(product_url, timeout=5)
            parser = _TextParser()
            parser.feed(detail_html)
            detail_text = _clean(" ".join(parser.parts))

            records = _price_contexts(
                detail_html, source, product_url, limit=2
            )
            verified = []
            for record in records:
                price = _money(record.get("price"))
                if budget and price and price > budget:
                    continue
                record["metadata"]["title"] = (
                    _clean(anchor)[:120]
                    or record.get("metadata", {}).get("title")
                    or product_url.rsplit("/", 1)[-1][:120]
                )
                record["metadata"]["price_source"] = "product_page_text"
                record["text"] = detail_text[:1800]
                _enrich_detail_metadata(record, detail_text, source)
                verified.append(record)
            return verified
        except Exception:
            return []

    prioritized = [item for item in discovered if item[0] in catalog_urls]
    prioritized += [item for item in discovered if item not in prioritized]

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(verify_detail, item) for item in prioritized[:limit * 4]]
        for future in as_completed(futures):
            results.extend(future.result())
            if len(results) >= limit:
                break

    # If an exact product page blocks automated fetching, retain the product
    # when the retailer catalog itself exposes its exact URL and price.
    # Validation labels this evidence as partial rather than fully verified.
    if len(results) < limit and html:
        listing_records = catalog_records
        existing_urls = {
            str(item.get("metadata", {}).get("url", ""))
            for item in results
        }
        for record in listing_records:
            product_url = str(record.get("metadata", {}).get("url", ""))
            if product_url in existing_urls:
                continue
            record["metadata"]["price_source"] = "listing_page_text"
            record["metadata"]["listing_verified"] = True
            results.append(record)
            existing_urls.add(product_url)
            if len(results) >= limit:
                break

    return results[:limit]

def _search_source_with_fallback(source, config, query, budget, group):
    # These retailers need exact product-page discovery first. Their public
    # category/search HTML is often incomplete or JavaScript-heavy.
    if source in {"Daraz Pakistan", "Mega.pk", "Shophive", "iShopping"}:
        results = _dedicated_catalog_candidates(source, config, query, budget, limit=6)
        if len(results) < 3:
            results.extend(_search_source(source, config, query, budget, group))
    else:
        results = _search_source(source, config, query, budget, group)

    if not results:
        # A listing page may expose Product JSON-LD even when its visible HTML
        # links are JavaScript-rendered or its detail pages block automated fetches.
        try:
            listing_url = config["search"].format(q=quote_plus(query))
            listing_html = _fetch(listing_url, timeout=5)
            for record in _jsonld_product_records(listing_html, source, listing_url):
                product_url = record["metadata"]["url"]
                if product_url not in {
                    str(item.get("metadata", {}).get("url", ""))
                    for item in results
                }:
                    price = _money(record.get("price"))
                    currency = record["metadata"].get("currency")
                    if not (budget and currency == "PKR" and price and price > budget):
                        results.append(record)
                if len(results) >= 12:
                    break
        except Exception:
            pass

    if len(results) >= 12:
        return results[:12]

    existing_urls = {
        str(item.get("metadata", {}).get("url", ""))
        for item in results
    }

    fallback_limit = 4 if source in {"Daraz Pakistan", "Shophive", "Mega.pk", "iShopping"} else 5
    for product_url, anchor in _search_engine_candidates(source, config, query)[:fallback_limit]:
        if product_url in existing_urls:
            continue

        try:
            detail_html = _fetch(product_url, timeout=4)
            detail_parser = _TextParser()
            detail_parser.feed(detail_html)
            detail_text = _clean(" ".join(detail_parser.parts))
            detail = _price_contexts(detail_html, source, product_url, limit=1)
            if detail:
                detail[0]["metadata"]["title"] = anchor[:120]
                detail[0]["text"] = detail_text[:1800]
                _enrich_detail_metadata(detail[0], detail_text, source)
                price = _money(detail[0].get("price"))
                currency = detail[0].get("metadata", {}).get("currency")
                if not (budget and currency == "PKR" and price and price > budget):
                    results.extend(detail)
                    existing_urls.add(product_url)
        except Exception:
            continue

        if len(results) >= 12:
            break

    return results[:12]

def search_web(query, category=""):
    """Search shopping sources in fast priority passes and return live evidence.

    Pass 1 focuses on Pakistan's main shopping platforms. Secondary and
    international sources are only queried when the primary pass does not
    produce enough useful records. This keeps common Pakistan searches fast
    while still giving BuyWiseAI broad coverage when needed.
    """
    budget = _budget_from_query(query)
    group = _query_group(query)
    category_key = str(category or "").strip().lower().rstrip("s")
    category_name = category_key.title()
    allowed_groups = SOURCE_GROUPS.get(category_name)
    if not allowed_groups:
        allowed_groups = {group}

    def eligible(names):
        return [
            (name, SOURCE_CATALOG[name])
            for name in names
            if name in SOURCE_CATALOG
            and SOURCE_CATALOG[name]["groups"] & allowed_groups
        ]

    def run_pass(selected, workers=6):
        found = []
        if not selected:
            return found
        with ThreadPoolExecutor(max_workers=min(workers, len(selected))) as pool:
            futures = {
                pool.submit(_search_source_with_fallback, name, cfg, query, budget, group): name
                for name, cfg in selected
            }
            for future in as_completed(futures):
                try:
                    found.extend(future.result())
                except Exception:
                    continue
        return found

    # Pass 1: the six highest-priority Pakistani shopping sources.
    results = run_pass(eligible(PRIMARY_PK_SOURCES), workers=6)

    # If the primary pass produced too few products, broaden to other
    # Pakistani stores before touching international marketplaces.
    if len(results) < 8:
        secondary = [
            item for item in eligible(SECONDARY_PK_SOURCES)
            if item[0] not in {str(r.get("source", "")) for r in results}
        ]
        results.extend(run_pass(secondary, workers=6))

    # International sources are a final fallback. They are useful, but
    # querying them on every Pakistan shopping request adds latency.
    if len(results) < 8:
        international = eligible(INTERNATIONAL_SOURCES)
        results.extend(run_pass(international, workers=2))

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

    # Keep results diverse. Primary Pakistani stores get the first opportunity
    # to appear, while round-robin prevents one retailer from taking over.
    priority_order = {
        name: index for index, name in enumerate(
            list(PRIMARY_PK_SOURCES) + list(SECONDARY_PK_SOURCES) + list(INTERNATIONAL_SOURCES)
        )
    }
    by_source = {}
    for item in unique:
        by_source.setdefault(item.get("source", "Unknown"), []).append(item)
    for source_items in by_source.values():
        source_items.sort(key=lambda item: priority_order.get(item.get("source", ""), 999))

    balanced = []
    max_per_source = 3
    source_order = sorted(
        by_source,
        key=lambda source: priority_order.get(source, 999),
    )
    for round_index in range(max_per_source):
        for source in source_order:
            source_items = by_source[source]
            if round_index < len(source_items):
                balanced.append(source_items[round_index])
                if len(balanced) >= 18:
                    return [validate_record(item) for item in balanced]

    return [validate_record(item) for item in balanced]

