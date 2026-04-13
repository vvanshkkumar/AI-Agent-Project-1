from typing import Any


class TavilyResearchProvider:
    """Tavily-backed search; requires TAVILY_API_KEY."""

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        from langchain_community.tools.tavily_search import TavilySearchResults

        tool = TavilySearchResults(max_results=max_results)
        results = tool.invoke({"query": query})
        out: list[dict[str, Any]] = []
        for r in results or []:
            out.append(
                {
                    "title": r.get("title") or "",
                    "url": r.get("url") or "",
                    "snippet": r.get("content") or r.get("snippet") or "",
                    "published_at": r.get("published_date") or r.get("published_at"),
                    "source": r.get("source"),
                }
            )
        return out
