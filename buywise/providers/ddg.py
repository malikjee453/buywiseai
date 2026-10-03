from __future__ import annotations

from ddgs import DDGS

from buywise.schemas import RawSearchResult
from .base import SearchProvider


class DuckDuckGoProvider(SearchProvider):
    name = "duckduckgo"
    requires_key = False
    env_var = None

    def search(self, query: str, country: str, max_results: int) -> list[RawSearchResult]:
        # DDGS can legitimately raise DDGSException when a backend returns no
        # results or is temporarily unavailable. Try a neutral region and Bing
        # fallback before reporting the provider as empty.
        queries = [
            (f"{query} Pakistan price", "pk-en", "auto"),
            (f"{query} Pakistan price", "wt-wt", "bing"),
        ]

        for text, region, backend in queries:
            try:
                with DDGS(timeout=8) as ddgs:
                    items = ddgs.text(
                        text,
                        region=region,
                        backend=backend,
                        max_results=min(max_results, 10),
                    )
                if items:
                    return [
                        RawSearchResult(
                            title=str(item.get("title", "")),
                            url=str(item.get("href", "")),
                            snippet=str(item.get("body", "")),
                            provider=self.name,
                            raw_data=item,
                        )
                        for item in items
                    ]
            except Exception:
                continue

        # No result is not a provider failure. Other providers should continue.
        return []
