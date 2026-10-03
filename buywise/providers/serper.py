from __future__ import annotations

import os

import httpx

from buywise.schemas import RawSearchResult
from .base import SearchProvider


class SerperProvider(SearchProvider):
    name = "serper"
    env_var = "SERPER_API_KEY"

    def search(self, query: str, country: str, max_results: int) -> list[RawSearchResult]:
        key = os.getenv(self.env_var, "").strip()
        if not key:
            return []
        country_code = {"Pakistan": "pk", "United States": "us", "United Kingdom": "gb"}.get(country, "us")
        headers = {"X-API-KEY": key, "Content-Type": "application/json"}
        payload = {"q": query, "gl": country_code, "hl": "en", "num": min(max_results, 20)}
        results: list[RawSearchResult] = []
        with httpx.Client(timeout=15) as client:
            response = client.post("https://google.serper.dev/shopping", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        for item in data.get("shopping", [])[:max_results]:
            results.append(RawSearchResult(
                title=str(item.get("title", "")), url=str(item.get("link", "")),
                snippet=str(item.get("snippet", "")), source=str(item.get("source", "")),
                price_text=str(item.get("price", "")) or None, provider=self.name, raw_data=item,
            ))
        return results
