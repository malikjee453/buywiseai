from __future__ import annotations

from ddgs import DDGS

from buywise.schemas import RawSearchResult
from .base import SearchProvider


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"
    requires_key = False
    env_var = None

    def search(self, query: str, country: str, max_results: int) -> list[RawSearchResult]:
        text = f'{query} Pakistan price'
        with DDGS(timeout=8) as ddgs:
            items = ddgs.text(text, region="pk-en", max_results=min(max_results, 20))
        return [RawSearchResult(
            title=str(item.get("title", "")), url=str(item.get("href", "")),
            snippet=str(item.get("body", "")), provider=self.name, raw_data=item,
        ) for item in items]
