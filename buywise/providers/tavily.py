from __future__ import annotations

import httpx

from buywise.schemas import RawSearchResult
from .base import SearchProvider
from .credentials import get_secret


class TavilyProvider(SearchProvider):
    name = "tavily"
    env_var = "TAVILY_API_KEY"

    def search(self, query: str, country: str, max_results: int) -> list[RawSearchResult]:
        key = get_secret(self.env_var)
        if not key:
            return []
        payload = {"query": f"{query} buy price {country}", "topic": "general", "search_depth": "basic", "max_results": min(max_results, 20), "include_answer": False}
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        with httpx.Client(timeout=15) as client:
            response = client.post("https://api.tavily.com/search", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return [RawSearchResult(
            title=str(item.get("title", "")), url=str(item.get("url", "")),
            snippet=str(item.get("content", "")), provider=self.name, raw_data=item,
        ) for item in data.get("results", [])[:max_results]]
