from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from statistics import median
from urllib.parse import urlsplit

from buywise.schemas import ProductListing, RawSearchResult
from buywise.categories import detect_categories
from .base import SearchProvider
from .brave import BraveProvider
from .common import infer_source, is_relevant_product, normalize_url, raw_to_listing
from .marketplace import MarketplaceProvider
from .serpapi import SerpApiProvider
from .serper import SerperProvider
from .tavily import TavilyProvider


# Search backends are discovery channels. The final result set is deliberately
# controlled by SHOPPING SOURCE diversity, not by provider result count.
PROVIDERS: list[SearchProvider] = [
    SerperProvider(),
    SerpApiProvider(),
    TavilyProvider(),
    BraveProvider(),
    MarketplaceProvider(),
]

TARGET_RESULTS = 10
MIN_DISTINCT_SOURCES = 8
MAX_SEARCH_ROUNDS = 2
MAX_RESULTS_PER_PROVIDER = 10


def _query_variants(query: str) -> list[str]:
    clean = " ".join(query.split())
    categories = detect_categories(clean)
    category_hint = f" {' '.join(categories)}" if categories else ""

    variants = [
        clean,
        f"{clean} Pakistan buy online{category_hint}",
        f"{clean} Pakistan price{category_hint}",
    ]
    return list(dict.fromkeys(variants))


def _host(url: str) -> str:
    try:
        return urlsplit(url).netloc.lower().removeprefix("www.").split(":")[0]
    except Exception:
        return ""


def _is_obviously_wrong_price(
    listing: ProductListing,
    prices: list[float],
    query: str,
) -> bool:
    """
    Reject obvious search-engine price contamination.

    This is intentionally conservative and category-aware:
    - no universal minimum is imposed because BuyWiseAI searches groceries,
      fashion, accessories, etc.
    - for a strongly priced cluster, an extreme low outlier is rejected.
    - common accessory/deposit wording is rejected for full-product queries.
    """
    if listing.currency != "PKR" or len(prices) < 4:
        return False

    text = f"{listing.title} {listing.snippet or ''}".lower()
    q = query.lower()

    # Strong signals that a tiny price is for an accessory, deposit, part,
    # installment, or other non-comparable item.
    accessory_words = (
        "case", "cover", "screen protector", "protector", "charger",
        "cable", "adapter", "glass", "strap", "replacement", "parts",
        "part", "accessory", "accessories", "deposit", "installment",
        "per month", "monthly", "down payment",
    )
    if any(word in text for word in accessory_words):
        return True

    med = median(prices)
    if med <= 0:
        return False

    # A result below 20% of the median is a strong outlier. For products such
    # as an iPhone this catches PKR 26 / PKR 38,999 while leaving ordinary
    # low-cost categories alone.
    if listing.price < med * 0.20:
        # Do not apply this to genuinely low-cost queries.
        if any(token in q for token in (
            "sticker", "pen", "pencil", "cable", "clip", "keychain",
            "socks", "mask", "notebook", "snack", "biscuit",
        )):
            return False
        return True

    return False


def _build_listings(
    all_raw: list[RawSearchResult],
    original_query: str,
) -> list[ProductListing]:
    """
    Return at most TARGET_RESULTS verified products.

    Hard business rule:
        one final product per shopping website/domain.

    Search providers may return many records from the same store; those are
    candidates only. They never become multiple final rows for one store.
    """
    candidates: list[tuple[ProductListing, str, str]] = []
    seen_urls: set[str] = set()

    for item in all_raw:
        relevant, _ = is_relevant_product(original_query, item)
        if not relevant:
            continue

        listing = raw_to_listing(item)
        if not listing:
            continue

        canonical_url = normalize_url(str(listing.url))
        host = _host(canonical_url)
        source = infer_source(canonical_url, listing.source).lower()

        if not canonical_url or not host or not source or source == "unknown":
            continue
        if canonical_url in seen_urls:
            continue

        path = canonical_url.split("?", 1)[0].rstrip("/").lower()
        bad_path_markers = (
            "/search", "/category", "/categories", "/collections",
            "/shop", "/compare", "/comparison", "/search-results",
        )
        if any(marker in path for marker in bad_path_markers):
            continue

        path_tokens = set(re.findall(r"[a-z0-9]+", path))
        if {"compare", "comparison", "search", "category", "categories"} & path_tokens:
            continue

        seen_urls.add(canonical_url)
        candidates.append((listing, source, host))

    # Establish a market anchor only after relevance filtering. Using the
    # median is more stable than an upper-quartile rule when a search provider
    # contributes several suspicious low prices.
    pkr_prices = sorted(
        item.price
        for item, _, _ in candidates
        if item.currency == "PKR" and item.price > 0
    )

    listings: list[ProductListing] = []
    seen_sources: set[str] = set()

    # Prefer candidates close to the market cluster before consuming a source.
    # This also stops a suspicious cheap result from winning its entire store.
    def candidate_key(entry: tuple[ProductListing, str, str]) -> tuple[int, float]:
        listing, _, _ = entry
        suspicious = _is_obviously_wrong_price(listing, pkr_prices, original_query)
        return (1 if suspicious else 0, listing.price)

    for listing, source, host in sorted(candidates, key=candidate_key):
        # Domain is the actual diversity key. A provider/source label is not.
        if host in seen_sources:
            continue

        if _is_obviously_wrong_price(listing, pkr_prices, original_query):
            continue

        listing.verified = True
        listing.source = host
        listing.verification_note = (
            "Verified product URL + parseable price + relevant product evidence; "
            "one-result-per-shopping-website diversity rule passed."
        )

        seen_sources.add(host)
        listings.append(listing)

        if len(listings) >= TARGET_RESULTS:
            break

    return listings


def _search_round(
    query: str,
    country: str,
    max_results: int,
) -> tuple[list[RawSearchResult], list[str]]:
    raw: list[RawSearchResult] = []
    errors: list[str] = []

    with ThreadPoolExecutor(
        max_workers=len(PROVIDERS),
        thread_name_prefix="buywise-search",
    ) as pool:
        futures = {
            pool.submit(
                provider.search,
                query,
                country,
                min(max_results, MAX_RESULTS_PER_PROVIDER),
            ): provider
            for provider in PROVIDERS
        }

        for future in as_completed(futures):
            provider = futures[future]
            try:
                raw.extend(future.result())
            except Exception as exc:
                errors.append(
                    f"{provider.name}: {type(exc).__name__}: {exc}"
                )

    return raw, errors


def run_search(
    query: str,
    country: str,
    max_results: int = MAX_RESULTS_PER_PROVIDER,
) -> tuple[list[RawSearchResult], list[ProductListing], list[str]]:
    """
    Search multiple discovery providers and return up to 10 different stores.

    max_results is a UI/provider request limit only. It does NOT mean that
    every provider contributes max_results rows to the final table.
    """
    all_raw: list[RawSearchResult] = []
    errors: list[str] = []

    for search_query in _query_variants(query)[:MAX_SEARCH_ROUNDS]:
        raw, round_errors = _search_round(
            search_query,
            country,
            min(max_results, MAX_RESULTS_PER_PROVIDER),
        )
        all_raw.extend(raw)
        errors.extend(round_errors)

        listings = _build_listings(all_raw, query)
        distinct_sources = len({_host(str(item.url)) for item in listings})

        if len(listings) >= TARGET_RESULTS and distinct_sources >= MIN_DISTINCT_SOURCES:
            return all_raw, listings[:TARGET_RESULTS], errors

    return all_raw, _build_listings(all_raw, query)[:TARGET_RESULTS], errors
