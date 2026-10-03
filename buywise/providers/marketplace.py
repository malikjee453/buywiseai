from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ddgs import DDGS

from buywise.schemas import RawSearchResult
from .base import SearchProvider
from .platforms import all_platforms


class MarketplaceProvider(SearchProvider):
    """Broad platform-targeted discovery for many Pakistan shopping categories."""

    name = "platform-targeted"
    requires_key = False
    env_var = None

    def _search_one(
        self,
        platform: str,
        domain: str,
        query: str,
        max_results: int,
    ) -> list[RawSearchResult]:
        # Do not require price words in the search query. Many stores expose
        # the price only in structured metadata/snippets, while their indexed
        # page title contains the product terms.
        search_query = f'site:{domain} {query} Pakistan'

        with DDGS(timeout=15) as ddgs:
            items = ddgs.text(
                search_query,
                max_results=max(2, min(max_results, 4)),
            )

        return [
            RawSearchResult(
                title=str(item.get("title", "")),
                url=str(item.get("href", "")),
                snippet=str(item.get("body", "")),
                source=platform,
                provider=self.name,
                raw_data=item,
            )
            for item in items
        ]

    def search(
        self,
        query: str,
        country: str,
        max_results: int,
    ) -> list[RawSearchResult]:
        platforms = all_platforms()
        results: list[RawSearchResult] = []

        with ThreadPoolExecutor(
            max_workers=min(8, len(platforms)),
            thread_name_prefix="buywise-platform",
        ) as pool:
            futures = {
                pool.submit(
                    self._search_one,
                    platform,
                    domain,
                    query,
                    max_results,
                ): platform
                for platform, domain in platforms.items()
            }

            for future in as_completed(futures):
                try:
                    results.extend(future.result())
                except Exception:
                    # One unavailable store must not stop the remaining stores.
                    continue

        return results
