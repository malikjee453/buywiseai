from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ddgs import DDGS

from buywise.schemas import RawSearchResult
from .base import SearchProvider


class MarketplaceProvider(SearchProvider):
    """Explicit Pakistan marketplace coverage for Daraz and AliExpress."""

    name = "marketplace-targeted"
    requires_key = False
    env_var = None

    TARGETS = {
        "daraz": "site:daraz.pk",
        "aliexpress": "site:aliexpress.com",
    }

    def _search_one(
        self,
        marketplace: str,
        operator: str,
        query: str,
        max_results: int,
    ) -> list[RawSearchResult]:
        search_query = (
            f'{operator} "{query}" price Pakistan '
            f"product buy online"
        )
        with DDGS(timeout=15) as ddgs:
            items = ddgs.text(
                search_query,
                max_results=max(3, min(max_results, 10)),
            )

        return [
            RawSearchResult(
                title=str(item.get("title", "")),
                url=str(item.get("href", "")),
                snippet=str(item.get("body", "")),
                source=marketplace,
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
        results: list[RawSearchResult] = []

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                pool.submit(
                    self._search_one,
                    marketplace,
                    operator,
                    query,
                    max_results,
                ): marketplace
                for marketplace, operator in self.TARGETS.items()
            }

            for future in as_completed(futures):
                try:
                    results.extend(future.result())
                except Exception:
                    continue

        return results
