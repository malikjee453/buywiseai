from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from buywise.schemas import ProductListing, RawSearchResult

PRICE_RE = re.compile(
    r"(?:(?P<currency>PKR|Rs\.?|USD|US\$|GBP|£|EUR|€|AED|SAR|INR|₹|\$)"
    r"\s*(?P<amount>[0-9][0-9,]*(?:\.[0-9]{1,2})?)"
    r"|(?P<amount2>[0-9][0-9,]*(?:\.[0-9]{1,2})?)"
    r"\s*(?P<currency2>PKR|Rs\.?|USD|US\$|GBP|£|EUR|€|AED|SAR|INR|₹|\$))",
    re.IGNORECASE,
)

CURRENCY_MAP = {
    "PKR": "PKR", "RS": "PKR", "RS.": "PKR",
    "USD": "USD", "US$": "USD", "$": "USD",
    "GBP": "GBP", "£": "GBP", "EUR": "EUR", "€": "EUR",
    "AED": "AED", "SAR": "SAR", "INR": "INR", "₹": "INR",
}

TRACKING_KEYS = {
    "gclid", "fbclid", "ref", "ref_", "tag", "affid", "affiliate",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
}


def normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
        query = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if k.lower() not in TRACKING_KEYS and not k.lower().startswith("utm_")
        ]
        return urlunsplit(
            (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"),
             urlencode(query), "")
        )
    except ValueError:
        return url.strip()


def infer_source(url: str, fallback: str = "Unknown") -> str:
    host = urlsplit(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host or fallback


def parse_price(
    price_text: str | None,
    snippet: str = "",
    title: str = "",
) -> tuple[float, str] | None:
    # Prefer explicit provider price fields. Fall back to snippet only when
    # necessary; never extract a random number from a product title.
    text = " ".join(x for x in [price_text or "", snippet or ""] if x)
    match = PRICE_RE.search(text)
    if not match:
        return None
    amount_text = match.group("amount") or match.group("amount2")
    currency_text = match.group("currency") or match.group("currency2")
    amount = float(amount_text.replace(",", ""))
    currency = CURRENCY_MAP.get(
        currency_text.upper(),
        currency_text.upper(),
    )
    return (amount, currency) if amount > 0 else None


def _normal(text: str) -> str:
    text = text.lower().replace("-", " ")
    text = re.sub(r"(\d+)\s*gb\b", r"\1gb", text)
    text = re.sub(r"(\d+)\s*tb\b", r"\1tb", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _evidence(raw: RawSearchResult) -> str:
    # Include URL and raw provider data because marketplace URLs often carry
    # the exact SKU/spec even when the search snippet does not.
    raw_blob = " ".join(str(v) for v in raw.raw_data.values())
    return _normal(" ".join([raw.title, raw.snippet, raw.url, raw_blob]))


def is_relevant_product(query: str, raw: RawSearchResult) -> tuple[bool, str]:
    """
    Conservative two-stage matcher:
    - core product/model tokens must match
    - requested specs must be evidenced somewhere in title/snippet/URL/provider data
    - explicit conflicting capacity is rejected
    """
    tokens = _normal(query).split()
    ignored = {
        "price", "prices", "buy", "online", "cheap", "best", "deal",
        "deals", "in", "pakistan", "pk", "for",
    }
    tokens = [t for t in tokens if t not in ignored]
    evidence = _evidence(raw)

    # Capacity/spec tokens.
    specs = [t for t in tokens if re.fullmatch(r"\d+(?:gb|tb|mp|mah)", t)]
    core = [t for t in tokens if t not in specs]

    # Common shopping-language equivalents. Search engines often return
    # "women" for girls' fashion, and "female" for women/girls.
    equivalents = {
        "girls": {"girls", "girl", "women", "woman", "female", "ladies"},
        "girl": {"girls", "girl", "women", "woman", "female", "ladies"},
        "women": {"women", "woman", "female", "ladies", "girls", "girl"},
        "woman": {"women", "woman", "female", "ladies", "girls", "girl"},
        "female": {"women", "woman", "female", "ladies", "girls", "girl"},
        "ladies": {"women", "woman", "female", "ladies", "girls", "girl"},
    }

    missing_core = []
    for token in core:
        acceptable = equivalents.get(token, {token})
        if not any(term in evidence for term in acceptable):
            missing_core.append(token)

    if missing_core:
        return False, f"missing product terms: {', '.join(missing_core)}"

    for spec in specs:
        # A requested spec may be absent from a short search snippet, so allow
        # the listing when the URL/provider data identifies the exact variant.
        # Explicitly conflicting capacities are always rejected.
        if spec.endswith(("gb", "tb")):
            capacities = re.findall(r"\b\d+(?:gb|tb)\b", evidence)
            if capacities and spec not in capacities:
                return False, f"conflicting capacity: {', '.join(sorted(set(capacities)))}"
        elif spec not in evidence:
            return False, f"missing requested specification: {spec}"

    return True, "product and requested specifications matched"


def raw_to_listing(raw: RawSearchResult) -> ProductListing | None:
    url = normalize_url(raw.url)
    # For ordinary web/marketplace discovery, a snippet can contain many
    # unrelated prices. Accept it only when the snippet explicitly labels the
    # amount as a product price.
    price_source = raw.price_text
    if not price_source and raw.snippet:
        snippet_lower = raw.snippet.lower()
        if not re.search(r"(price|rs\.?|pkr|\$|usd|gbp|eur|aed|sar|inr|₹)", snippet_lower):
            return None
        price_source = raw.snippet

    parsed = parse_price(price_source, "", raw.title)
    if not url or not parsed:
        return None

    price, currency = parsed
    try:
        return ProductListing(
            title=raw.title.strip(),
            price=price,
            currency=currency,
            source=raw.source or infer_source(url, raw.provider),
            url=url,
            rating=None,
            availability=None,
            snippet=raw.snippet[:1000] if raw.snippet else None,
            verified=False,
        )
    except Exception:
        return None
