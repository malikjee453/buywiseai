from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ddgs import DDGS

from buywise.schemas import RawSearchResult
from .base import SearchProvider
from .platforms import relevant_platforms


class MarketplaceProvider(SearchProvider):
    """
    Targeted shopping-platform discovery.

    This is the main free route for store diversity. It searches many actual
    shopping websites rather than treating DuckDuckGo itself as a shopping
    source.
    """

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
        search_query = f"site:{domain} {query} Pakistan"

        for region, backend in (("pk-en", "auto"), ("wt-wt", "bing")):
            try:
                with DDGS(timeout=6) as ddgs:
                    items = ddgs.text(
                        search_query,
                        region=region,
                        backend=backend,
                        max_results=min(max_results, 5),
                    )
                if not items:
                    continue

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
            except Exception:
                continue

        return []

    def search(
        self,
        query: str,
        country: str,
        max_results: int,
    ) -> list[RawSearchResult]:
        # Search more candidate stores than the final 10-result target.
        # This gives the diversity controller enough alternatives when some
        # stores have no indexed product page.
        platforms = relevant_platforms(query, max_platforms=20)
        results: list[RawSearchResult] = []

        if not platforms:
            return results

        with ThreadPoolExecutor(
            max_workers=min(12, len(platforms)),
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
                    # One unavailable store never stops the others.
                    continue

        return results
