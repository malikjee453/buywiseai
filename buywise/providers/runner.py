from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from buywise.schemas import ProductListing, RawSearchResult
from buywise.categories import detect_categories
from .base import SearchProvider
from .brave import BraveProvider
from .common import infer_source, is_relevant_product, normalize_url, raw_to_listing
from .ddg import DuckDuckGoProvider
from .marketplace import MarketplaceProvider
from .serpapi import SerpApiProvider
from .serper import SerperProvider
from .tavily import TavilyProvider

PROVIDERS: list[SearchProvider] = [
    SerperProvider(),
    SerpApiProvider(),
    TavilyProvider(),
    BraveProvider(),
    DuckDuckGoProvider(),
    MarketplaceProvider(),
]

MAX_RESULTS_PER_SOURCE = 1
TARGET_RESULTS = 10
MIN_DISTINCT_SOURCES = 8
MAX_SEARCH_ROUNDS = 2


def _query_variants(query: str) -> list[str]:
    clean = " ".join(query.split())
    categories = detect_categories(clean)
    category_hint = f" {' '.join(categories)}" if categories else ""
    variants = [
        clean,
        f'{clean} Pakistan buy online{category_hint}',
        f'{clean} Pakistan price{category_hint}',
    ]
    return list(dict.fromkeys(variants))


def _build_listings(
    all_raw: list[RawSearchResult],
    original_query: str,
) -> list[ProductListing]:
    """Build a maximum of 10 verified offers, with at most one offer per store."""
    candidates: list[tuple[ProductListing, str]] = []
    seen_urls: set[str] = set()

    for item in all_raw:
        relevant, _ = is_relevant_product(original_query, item)
        if not relevant:
            continue

        listing = raw_to_listing(item)
        if not listing:
            continue

        canonical_url = normalize_url(str(listing.url))
        source = infer_source(canonical_url, listing.source).lower()
        if not canonical_url or canonical_url in seen_urls:
            continue

        path = canonical_url.split("?", 1)[0].rstrip("/").lower()
        bad_path_markers = (
            "/search", "/category", "/categories", "/collections",
            "/shop", "/compare", "/comparison", "/search-results",
        )
        if any(marker in path for marker in bad_path_markers):
            continue

        seen_urls.add(canonical_url)
        candidates.append((listing, source))

    # One result per shopping website. This is a hard diversity rule.
    # First remove obviously suspicious prices after computing a robust median.
    prices = sorted(item.price for item, _ in candidates if item.currency == "PKR")
    median = prices[len(prices) // 2] if prices else None

    listings: list[ProductListing] = []
    seen_sources: set[str] = set()

    for listing, source in candidates:
        if source in seen_sources:
            continue

        # A price dramatically below the market cluster is not trusted.
        # It may be an accessory, deposit, used item, typo, or unrelated offer.
        if median is not None and listing.currency == "PKR" and len(prices) >= 3:
            if listing.price < median * 0.20:
                continue

        listing.verified = True
        listing.verification_note = (
            "Matched product/spec evidence, has a parseable price and URL, "
            "and passed source/price sanity checks."
        )
        seen_sources.add(source)
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
        max_workers=min(len(PROVIDERS), 6),
        thread_name_prefix="buywise-search",
    ) as pool:
        futures = {
            pool.submit(p.search, query, country, max_results): p
            for p in PROVIDERS
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
    max_results: int = 20,
) -> tuple[list[RawSearchResult], list[ProductListing], list[str]]:
    """Search providers as discovery channels; return at most 10 total verified products, prioritizing distinct sources."""
    all_raw: list[RawSearchResult] = []
    errors: list[str] = []

    for search_query in _query_variants(query)[:MAX_SEARCH_ROUNDS]:
        raw, round_errors = _search_round(search_query, country, min(max_results, 10))
        all_raw.extend(raw)
        errors.extend(round_errors)

        listings = _build_listings(all_raw, query)
        distinct_sources = len({item.source.strip().lower() for item in listings})

        if len(listings) >= TARGET_RESULTS and distinct_sources >= MIN_DISTINCT_SOURCES:
            return all_raw, listings, errors

    return all_raw, _build_listings(all_raw, query), errors
