from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from buywise.schemas import ProductListing, RawSearchResult

# Deliberately conservative: capture currency symbols/codes plus a number.
PRICE_RE = re.compile(
    r"(?P<currency>PKR|Rs\.?|USD|US\$|GBP|£|EUR|€|AED|SAR|INR|₹|\$)"
    r"\s*(?P<amount>[0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)
NUMBER_PRICE_RE = re.compile(r"(?<![A-Za-z])(?P<amount>[0-9][0-9,]*(?:\.[0-9]{1,2})?)")

CURRENCY_MAP = {
    "PKR": "PKR", "RS": "PKR", "RS.": "PKR", "USD": "USD", "US$": "USD", "$": "USD",
    "GBP": "GBP", "£": "GBP", "EUR": "EUR", "€": "EUR", "AED": "AED", "SAR": "SAR",
    "INR": "INR", "₹": "INR",
}

TRACKING_KEYS = {"gclid", "fbclid", "ref", "ref_", "tag", "affid", "affiliate", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


def normalize_url(url: str) -> str:
    """Remove fragments and common tracking parameters without changing the destination."""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_KEYS and not k.lower().startswith("utm_")]
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))
    except ValueError:
        return url.strip()


def infer_source(url: str, fallback: str = "Unknown") -> str:
    host = urlsplit(url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return fallback
    return host


def parse_price(price_text: str | None, snippet: str = "") -> tuple[float, str] | None:
    """Parse a price only when currency evidence is present; avoids random page numbers."""
    text = " ".join(x for x in [price_text or "", snippet or ""] if x).strip()
    match = PRICE_RE.search(text)
    if not match:
        return None
    amount = float(match.group("amount").replace(",", ""))
    currency = CURRENCY_MAP.get(match.group("currency").upper(), match.group("currency").upper())
    if amount <= 0:
        return None
    return amount, currency


def raw_to_listing(raw: RawSearchResult) -> ProductListing | None:
    """Convert a provider result into a strict listing only when a price and URL exist."""
    url = normalize_url(raw.url)
    parsed = parse_price(raw.price_text, raw.snippet)
    if not url or not parsed:
        return None
    price, currency = parsed
    try:
        return ProductListing(
            title=raw.title.strip(), price=price, currency=currency,
            source=raw.source or infer_source(url, raw.provider), url=url,
            rating=None, availability=None, snippet=raw.snippet[:1000] if raw.snippet else None,
            verified=False,
        )
    except Exception:
        return None
