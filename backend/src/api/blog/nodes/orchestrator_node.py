from langchain_core.messages import HumanMessage, SystemMessage

from api.blog.kafka_sections import publish_blog_tasks
from api.blog.schemas import Plan
from api.blog.state import BlogState
from observers.publisher import publisher

ORCH_SYSTEM = """You are a senior technical writer and developer advocate.
Produce a highly actionable outline for a technical blog post.

Requirements:
- 5–9 tasks, each with goal + 3–6 bullets + target_words.
- Tags are flexible; do not force a fixed taxonomy.

Grounding:
- closed_book: evergreen, no evidence dependence.
- hybrid: use evidence for up-to-date examples; mark those tasks requires_research=True and requires_citations=True.
- open_book: weekly/news roundup:
  - Set blog_kind="news_roundup"
  - No tutorial content unless requested
  - If evidence is weak, plan should explicitly reflect that (don’t invent events).

Output must match Plan schema.
"""


def orchestrator_node(state: BlogState, llm):
    run_id = state.get("run_id", "unknown")
    publisher.on_node_enter(run_id, "orchestrator_node")
    try:
        planner = llm.with_structured_output(Plan)
        mode = state.get("mode", "closed_book")
        evidence = state.get("evidence", [])

        forced_kind = "news_roundup" if mode == "open_book" else None

        plan = planner.invoke(
            [
                SystemMessage(content=ORCH_SYSTEM),
                HumanMessage(
                    content=(
                        f"Topic: {state['topic']}\n"
                        f"Mode: {mode}\n"
                        f"As-of: {state['as_of']} (recency_days={state['recency_days']})\n"
                        f"{'Force blog_kind=news_roundup' if forced_kind else ''}\n\n"
                        f"Evidence:\n{[e.model_dump() for e in evidence][:16]}"
                    )
                ),
            ]
        )
        if forced_kind:
            plan.blog_kind = "news_roundup"

        state_with_plan = {**state, "plan": plan}
        expected_section_count = publish_blog_tasks(state_with_plan)
        publisher.on_node_exit(
            run_id,
            "orchestrator_node",
            "SUCCESS",
            {
                "blog_kind": plan.blog_kind,
                "task_count": len(plan.tasks),
                "published_task_count": expected_section_count,
                "evidence_count": len(evidence),
            },
        )
        return {"plan": plan, "expected_section_count": expected_section_count}
    except Exception as exc:
        publisher.on_node_exit(run_id, "orchestrator_node", "FAILED", {"error": str(exc)})
        raise
