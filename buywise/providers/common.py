from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from buywise.schemas import ProductListing, RawSearchResult

PRICE_RE = re.compile(
    r"(?P<currency>PKR|Rs\.?|USD|US\$|GBP|£|EUR|€|AED|SAR|INR|₹|\$)"
    r"\s*(?P<amount>[0-9][0-9,]*(?:\.[0-9]{1,2})?)",
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
    text = " ".join(x for x in [price_text or "", snippet or "", title or ""] if x)
    match = PRICE_RE.search(text)
    if not match:
        return None
    amount = float(match.group("amount").replace(",", ""))
    currency = CURRENCY_MAP.get(
        match.group("currency").upper(),
        match.group("currency").upper(),
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

    missing_core = [t for t in core if t not in evidence]
    if missing_core:
        return False, f"missing product terms: {', '.join(missing_core)}"

    for spec in specs:
        if spec not in evidence:
            return False, f"missing requested specification: {spec}"

        # Do not accept an explicitly different capacity when the requested
        # capacity is present.
        if spec.endswith(("gb", "tb")):
            capacities = re.findall(r"\b\d+(?:gb|tb)\b", evidence)
            if capacities and spec not in capacities:
                return False, f"conflicting capacity: {', '.join(sorted(set(capacities)))}"

    return True, "product and requested specifications matched"


def raw_to_listing(raw: RawSearchResult) -> ProductListing | None:
    url = normalize_url(raw.url)
    parsed = parse_price(raw.price_text, raw.snippet, raw.title)
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
