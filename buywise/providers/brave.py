from __future__ import annotations

import os

import httpx

from buywise.schemas import RawSearchResult
from .base import SearchProvider


class BraveProvider(SearchProvider):
    name = "brave"
    env_var = "BRAVE_API_KEY"

    def search(self, query: str, country: str, max_results: int) -> list[RawSearchResult]:
        key = os.getenv(self.env_var, "").strip()
        if not key:
            return []
        country_code = {"Pakistan": "PK", "United States": "US", "United Kingdom": "GB"}.get(country, "US")
        headers = {"X-Subscription-Token": key, "Accept": "application/json"}
        params = {"q": f"{query} price", "country": country_code, "search_lang": "en", "count": min(max_results, 20)}
        with httpx.Client(timeout=15) as client:
            response = client.get("https://api.search.brave.com/res/v1/web/search", headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
        return [RawSearchResult(
            title=str(item.get("title", "")), url=str(item.get("url", "")),
            snippet=str(item.get("description", "")), provider=self.name, raw_data=item,
        ) for item in data.get("web", {}).get("results", [])[:max_results]]
