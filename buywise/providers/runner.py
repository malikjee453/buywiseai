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


def run_search(
    query: str,
    country: str,
    max_results: int = 20,
) -> tuple[list[RawSearchResult], list[ProductListing], list[str]]:
    """Search providers in parallel, then strictly filter and deduplicate listings."""
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

    listings: list[ProductListing] = []
    seen_urls: set[str] = set()
    source_counts: dict[str, int] = {}

    for item in raw:
        relevant, _reason = is_relevant_product(query, item)
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
        listing.verification_note = "Matched requested product terms and has a parseable price + URL."

        seen_urls.add(canonical_url)
        source_counts[source] = source_counts.get(source, 0) + 1
        listings.append(listing)

    return raw, listings, errors
