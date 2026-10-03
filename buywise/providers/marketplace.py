from __future__ import annotations

from ddgs import DDGS

from buywise.schemas import RawSearchResult
from .base import SearchProvider


class MarketplaceProvider(SearchProvider):
    """
    Keyless marketplace-focused search for marketplaces that should be explicitly
    covered even when general search providers do not surface them.
    """

    name = "marketplace-targeted"
    requires_key = False
    env_var = None

    MARKETPLACES = {
        "Pakistan": {
            "daraz": "site:daraz.pk",
            "aliexpress": "site:aliexpress.com",
        },
        "United States": {
            "daraz": "site:daraz.com",
            "aliexpress": "site:aliexpress.com",
        },
        "United Kingdom": {
            "daraz": "site:daraz.com",
            "aliexpress": "site:aliexpress.com",
        },
    }

    def search(self, query: str, country: str, max_results: int) -> list[RawSearchResult]:
        targets = self.MARKETPLACES.get(country, self.MARKETPLACES["United States"])
        results: list[RawSearchResult] = []

        per_marketplace = max(3, min(max_results, 10))
        with DDGS(timeout=15) as ddgs:
            for marketplace, operator in targets.items():
                search_query = f"{operator} {query} price"
                try:
                    items = ddgs.text(
                        search_query,
                        max_results=per_marketplace,
                    )
                    for item in items:
                        results.append(
                            RawSearchResult(
                                title=str(item.get("title", "")),
                                url=str(item.get("href", "")),
                                snippet=str(item.get("body", "")),
                                source=marketplace,
                                provider=self.name,
                                raw_data=item,
                            )
                        )
                except Exception:
                    # One marketplace failing must not remove the other.
                    continue

        return results
