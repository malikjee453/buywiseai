from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from ddgs import DDGS

from buywise.schemas import RawSearchResult
from .base import SearchProvider


class MarketplaceProvider(SearchProvider):
    """Explicit Pakistan shopping-site coverage using search-engine discovery."""

    name = "marketplace-targeted"
    requires_key = False
    env_var = None

    TARGETS = {
        "daraz.pk": "site:daraz.pk",
        "aliexpress.com": "site:aliexpress.com",
        "priceoye.pk": "site:priceoye.pk",
        "mega.pk": "site:mega.pk",
        "qeemat.pk": "site:qeemat.pk",
        "geemat.pk": "site:geemat.pk",
        "mobiledaam.pk": "site:mobiledaam.pk",
        "phonebolee.com": "site:phonebolee.com",
        "whatmobile.com.pk": "site:whatmobile.com.pk",
        "hamariweb.com": "site:hamariweb.com",
    }

    def _search_one(
        self,
        domain: str,
        operator: str,
        query: str,
        max_results: int,
    ) -> list[RawSearchResult]:
        search_query = (
            f'{operator} "{query}" '
            f'("Rs" OR "PKR" OR "price") Pakistan'
        )
        with DDGS(timeout=15) as ddgs:
            items = ddgs.text(
                search_query,
                max_results=max(2, min(max_results, 5)),
            )

        return [
            RawSearchResult(
                title=str(item.get("title", "")),
                url=str(item.get("href", "")),
                snippet=str(item.get("body", "")),
                source=domain,
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

        with ThreadPoolExecutor(
            max_workers=min(10, len(self.TARGETS)),
            thread_name_prefix="buywise-market",
        ) as pool:
            futures = {
                pool.submit(
                    self._search_one,
                    domain,
                    operator,
                    query,
                    max_results,
                ): domain
                for domain, operator in self.TARGETS.items()
            }

            for future in as_completed(futures):
                try:
                    results.extend(future.result())
                except Exception:
                    # Search coverage is best-effort; another site must continue.
                    continue

        return results
