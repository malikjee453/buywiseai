from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from buywise.schemas import ProductListing, RawSearchResult
from .base import SearchProvider
from .brave import BraveProvider
from .common import is_relevant_product, normalize_url, raw_to_listing
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

MAX_RESULTS_PER_SOURCE = 2
TARGET_RESULTS = 10
MIN_DISTINCT_SOURCES = 8
MAX_SEARCH_ROUNDS = 3


def _query_variants(query: str) -> list[str]:
    clean = " ".join(query.split())
    variants = [
        clean,
        f'"{clean}" Pakistan price',
        f'{clean} Pakistan buy online price',
    ]
    return list(dict.fromkeys(variants))


def _build_listings(
    all_raw: list[RawSearchResult],
    original_query: str,
) -> list[ProductListing]:
    listings: list[ProductListing] = []
    seen_urls: set[str] = set()
    source_counts: dict[str, int] = {}

    for item in all_raw:
        relevant, _ = is_relevant_product(original_query, item)
        if not relevant:
            continue

        listing = raw_to_listing(item)
        if not listing:
            continue

        canonical_url = normalize_url(str(listing.url))
        source = listing.source.strip().lower()

        if not canonical_url or canonical_url in seen_urls:
            continue
        if source_counts.get(source, 0) >= MAX_RESULTS_PER_SOURCE:
            continue

        listing.verified = True
        listing.verification_note = (
            "Matched requested product/spec evidence and has a parseable price + URL."
        )
        seen_urls.add(canonical_url)
        source_counts[source] = source_counts.get(source, 0) + 1
        listings.append(listing)

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
    """Run up to three rounds until coverage reaches 10 results / 8 sources."""
    all_raw: list[RawSearchResult] = []
    errors: list[str] = []

    for search_query in _query_variants(query)[:MAX_SEARCH_ROUNDS]:
        raw, round_errors = _search_round(search_query, country, max_results)
        all_raw.extend(raw)
        errors.extend(round_errors)

        listings = _build_listings(all_raw, query)
        distinct_sources = len({item.source.strip().lower() for item in listings})

        if len(listings) >= TARGET_RESULTS and distinct_sources >= MIN_DISTINCT_SOURCES:
            return all_raw, listings, errors

    return all_raw, _build_listings(all_raw, query), errors
