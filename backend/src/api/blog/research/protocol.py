from typing import Any, Protocol


class ResearchProvider(Protocol):
    """Pluggable web research. Implementations must not import graph nodes."""

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Return raw hit dicts (title, url, snippet/content, optional dates)."""
        ...
