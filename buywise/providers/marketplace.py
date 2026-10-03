from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ddgs import DDGS

from buywise.schemas import RawSearchResult
from .base import SearchProvider
from .platforms import relevant_platforms


class MarketplaceProvider(SearchProvider):
    """Target individual shopping websites for store-diverse results."""

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
        """Run one fast site-targeted discovery request.

        One request per platform is intentional: BuyWiseAI needs diversity
        across shopping websites, not many results from the same website.
        """
        search_query = f"site:{domain} {query} price"

        try:
            items = []
            # Try the default backend first, then Bing as a fallback.
            for backend in ("auto", "bing"):
                try:
                    with DDGS(timeout=5) as ddgs:
                        items = ddgs.text(
                            search_query,
                            region="pk-en",
                            backend=backend,
                            max_results=min(max_results, 3),
                        )
                    if items:
                        break
                except Exception:
                    continue

            if not items:
                return []

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
                if item.get("href")
            ]
        except Exception:
            # A single store/search-engine failure must never block the
            # remaining platforms.
            return []

    def search(
        self,
        query: str,
        country: str,
        max_results: int,
    ) -> list[RawSearchResult]:
        platforms = relevant_platforms(query, max_platforms=30)
        if not platforms:
            return []

        results: list[RawSearchResult] = []

        with ThreadPoolExecutor(
            max_workers=min(15, len(platforms)),
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
                    # One unavailable store never stops other stores.
                    continue

        return results
