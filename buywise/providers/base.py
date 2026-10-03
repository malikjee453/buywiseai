from __future__ import annotations

from abc import ABC, abstractmethod

from buywise.schemas import RawSearchResult


class SearchProvider(ABC):
    """Small interface shared by every external search provider."""

    name: str = "base"
    requires_key: bool = True
    env_var: str | None = None

    @abstractmethod
    def search(self, query: str, country: str, max_results: int) -> list[RawSearchResult]:
        """Search for a product query and return normalized raw results."""
        raise NotImplementedError
