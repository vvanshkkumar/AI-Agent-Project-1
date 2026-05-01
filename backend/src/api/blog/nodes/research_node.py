from datetime import date, timedelta
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from api.blog.research.protocol import ResearchProvider
from api.blog.schemas import EvidenceItem, EvidencePack
from api.blog.state import BlogState
from observers.publisher import publisher

RESEARCH_SYSTEM = """You are a research synthesizer.

Given raw web search results, produce EvidenceItem objects.

Rules:
- Only include items with a non-empty url.
- Prefer relevant + authoritative sources.
- Normalize published_at to ISO YYYY-MM-DD if reliably inferable; else null (do NOT guess).
- Keep snippets short.
- Deduplicate by URL.
"""


def _iso_to_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def research_node(state: BlogState, llm, provider: ResearchProvider):
    run_id = state.get("run_id", "unknown")
    publisher.on_node_enter(run_id, "research_node")
    try:
        queries = (state.get("queries") or [])[:10]
        raw: List[dict] = []
        for q in queries:
            raw.extend(provider.search(q, max_results=6))

        if not raw:
            publisher.on_node_exit(
                run_id,
                "research_node",
                "SUCCESS",
                {"query_count": len(queries), "raw_result_count": 0, "evidence_count": 0},
            )
            return {"evidence": []}

        extractor = llm.with_structured_output(EvidencePack)
        pack = extractor.invoke(
            [
                SystemMessage(content=RESEARCH_SYSTEM),
                HumanMessage(
                    content=(
                        f"As-of date: {state['as_of']}\n"
                        f"Recency days: {state['recency_days']}\n\n"
                        f"Raw results:\n{raw}"
                    )
                ),
            ]
        )

        dedup = {}
        for e in pack.evidence:
            if e.url:
                dedup[e.url] = e
        evidence = list(dedup.values())

        if state.get("mode") == "open_book":
            as_of = date.fromisoformat(state["as_of"])
            cutoff = as_of - timedelta(days=int(state["recency_days"]))
            evidence = [e for e in evidence if (d := _iso_to_date(e.published_at)) and d >= cutoff]

        publisher.on_node_exit(
            run_id,
            "research_node",
            "SUCCESS",
            {
                "query_count": len(queries),
                "raw_result_count": len(raw),
                "evidence_count": len(evidence),
            },
        )
        return {"evidence": evidence}
    except Exception as exc:
        publisher.on_node_exit(run_id, "research_node", "FAILED", {"error": str(exc)})
        raise
