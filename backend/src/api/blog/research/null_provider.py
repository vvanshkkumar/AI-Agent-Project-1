from typing import Any


class NullResearchProvider:
    """No external search (e.g. missing API keys)."""

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        return []
