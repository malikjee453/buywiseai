from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen
import re
import json

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
    "Mega.pk": {"base": "https://www.mega.pk", "search": "https://www.mega.pk/mobiles/?q={q}", "groups": {"electronics"}},
    "iShopping": {"base": "https://www.ishopping.pk", "search": "https://www.ishopping.pk/mobiles", "groups": {"electronics"}},
    "HomeShopping": {"base": "https://www.homeshopping.pk", "search": "https://www.homeshopping.pk/mobiles", "groups": {"electronics", "home", "general"}},
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

def _is_product_url(source, url):
    """Return True only for URLs that look like individual product pages."""
    path = url.split("?", 1)[0].lower().rstrip("/")
    if not path:
        return False

    if re.search(r"/(product|item|p|dp|products|mobiles)/[^/]+", path, re.I):
        return True

    # Shophive product pages use /<slug>.html or /product/<slug>.
    if "shophive.com" in path:
        blocked = (
            "/catalogsearch", "/search", "/mobile-phones", "/category",
            "/categories", "/customer", "/checkout", "/cart", "/blog",
        )
        if any(item in path for item in blocked):
            return False
        return path.endswith(".html") or path.count("/") >= 2

    # Mega.pk mobile pages commonly use /mobiles/<slug>.
    if "mega.pk" in path and "/mobiles/" in path:
        return True

    # Daraz product pages use /products/<slug>-i<id>.html.
    if "daraz.pk" in path and re.search(r"/products/.+-i\d+\.html", path, re.I):
        return True

    if "telemart.pk" in path and "/products/" in path:
        return True

    if "ishopping.pk" in path:
        blocked = (
            "/mobiles", "/electronics", "/category", "/catalogsearch",
            "/search", "/customer", "/checkout", "/cart", "/blog",
            "/sale", "/brands", "/pre-owned", "/accessories",
        )
        if any(path.endswith(item) or item + "/" in path for item in blocked):
            return False
        return path.count("/") >= 1

    blocked = (
        "/search", "/catalogsearch", "/category", "/categories/",
        "/collection", "/collections/", "/shop", "/cart", "/account",
        "/checkout", "/blog", "/tag/", "/page/",
    )
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
            if str(value.get("@type", "")).lower() == "product":
                yield value
            graph = value.get("@graph")
            if isinstance(graph, list):
                for item in graph:
                    yield from walk(item)
            for key in ("itemListElement", "items"):
                items = value.get(key)
                if isinstance(items, list):
                    for item in items:
                        yield from walk(item)
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

            price = offers.get("price")
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

            results.append({
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
                },
            })

    return results


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
            if not _is_product_url(source, absolute):
                continue
            seen.add(absolute)
            candidates.append((absolute, anchor))

        results = _jsonld_product_records(html, source, url)
        # Try more candidates because some retailer pages contain accessories
        # before the actual smartphone products.
        for product_url, anchor in candidates[:30]:
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
    """Discover indexed product pages when a retailer search page is JS/blocking."""
    host = config["base"].split("//", 1)[-1].replace("www.", "")
    search_queries = [
        f"site:{host} {query}",
        f"site:{host} smartphone PKR battery camera",
    ]
    candidates = []
    seen = set()

    for engine in ("https://www.google.com/search?q=", "https://www.bing.com/search?q="):
        for search_query in search_queries:
            try:
                html = _fetch(engine + quote_plus(search_query), timeout=8)
                parser = _LinkParser()
                parser.feed(html)

                for href, anchor in parser.links:
                    if not href or not anchor:
                        continue

                    absolute = href
                    if absolute.startswith("/url?q="):
                        absolute = absolute.split("/url?q=", 1)[1].split("&", 1)[0]

                    if not absolute.startswith("http"):
                        continue
                    if host not in absolute.replace("www.", ""):
                        continue
                    if absolute in seen:
                        continue
                    if not _is_product_url(source, absolute):
                        continue

                    seen.add(absolute)
                    candidates.append((absolute, anchor))

                    if len(candidates) >= 30:
                        return candidates
            except Exception:
                continue

    return candidates

def _search_source_with_fallback(source, config, query, budget, group):
    # First use the retailer's own search page. Some retailers expose only a
    # small subset or use client-side rendering, so supplement (rather than
    # replace) those results with indexed product pages.
    results = _search_source(source, config, query, budget, group)

    if len(results) < 12:
        # A listing page may expose Product JSON-LD even when its visible HTML
        # links are JavaScript-rendered or its detail pages block automated fetches.
        try:
            listing_url = config["search"].format(q=quote_plus(query))
            listing_html = _fetch(listing_url, timeout=8)
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

    # Keep results diverse. Round-robin across sources first so a single
    # retailer cannot consume the entire evidence set.
    by_source = {}
    for item in unique:
        by_source.setdefault(item.get("source", "Unknown"), []).append(item)

    balanced = []
    max_per_source = 4
    for round_index in range(max_per_source):
        for source, source_items in by_source.items():
            if round_index < len(source_items):
                balanced.append(source_items[round_index])
                if len(balanced) >= 30:
                    return balanced

    return balanced
