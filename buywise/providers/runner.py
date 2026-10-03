from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from buywise.schemas import ProductListing, RawSearchResult
from .base import SearchProvider
from .brave import BraveProvider
from .ddg import DuckDuckGoProvider
from .serpapi import SerpApiProvider
from .serper import SerperProvider
from .tavily import TavilyProvider
from .common import normalize_url, raw_to_listing


PROVIDERS: list[SearchProvider] = [
    SerperProvider(), SerpApiProvider(), TavilyProvider(), BraveProvider(), DuckDuckGoProvider()
]


def run_search(query: str, country: str, max_results: int = 20) -> tuple[list[RawSearchResult], list[ProductListing], list[str]]:
    """Fan out to every configured provider, isolate failures, then normalize/dedupe priced results."""
    raw: list[RawSearchResult] = []
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=len(PROVIDERS), thread_name_prefix="buywise-search") as pool:
        futures = {pool.submit(p.search, query, country, max_results): p for p in PROVIDERS}
        for future in as_completed(futures):
            provider = futures[future]
            try:
                raw.extend(future.result())
            except Exception as exc:
                errors.append(f"{provider.name}: {type(exc).__name__}: {exc}")

    listings: list[ProductListing] = []
    seen: set[str] = set()
    for item in raw:
        listing = raw_to_listing(item)
        if not listing:
            continue
        key = normalize_url(str(listing.url)) or f"{listing.source}|{listing.title.lower()}|{listing.price}"
        if key in seen:
            continue
        seen.add(key)
        listings.append(listing)
    return raw, listings, errors
