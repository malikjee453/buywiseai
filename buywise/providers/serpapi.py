from __future__ import annotations

import os

import httpx

from buywise.schemas import RawSearchResult
from .base import SearchProvider


class SerpApiProvider(SearchProvider):
    name = "serpapi"
    env_var = "SERPAPI_API_KEY"

    def search(self, query: str, country: str, max_results: int) -> list[RawSearchResult]:
        key = os.getenv(self.env_var, "").strip()
        if not key:
            return []
        gl = {"Pakistan": "pk", "United States": "us", "United Kingdom": "uk"}.get(country, "us")
        params = {"engine": "google_shopping", "q": query, "api_key": key, "gl": gl, "hl": "en"}
        with httpx.Client(timeout=15) as client:
            response = client.get("https://serpapi.com/search", params=params)
            response.raise_for_status()
            data = response.json()
        results: list[RawSearchResult] = []
        for item in data.get("shopping_results", [])[:max_results]:
            results.append(RawSearchResult(
                title=str(item.get("title", "")), url=str(item.get("product_link") or item.get("link") or ""),
                snippet=str(item.get("snippet", "")), source=str(item.get("source", "")),
                price_text=str(item.get("price", "")) or None, rating_text=str(item.get("rating", "")) or None,
                provider=self.name, raw_data=item,
            ))
        return results
