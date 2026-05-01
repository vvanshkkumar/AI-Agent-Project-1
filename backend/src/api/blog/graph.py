from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from api.ai.llms import get_blog_llm
from api.blog.nodes.orchestrator_node import orchestrator_node
from api.blog.nodes.reducer import build_reducer_subgraph
from api.blog.nodes.research_node import research_node
from api.blog.nodes.router_node import route_next, router_node
from api.blog.research.factory import get_research_provider
from api.blog.state import BlogState


def build_blog_app():
    llm = get_blog_llm()
    research = get_research_provider()
    reducer_subgraph = build_reducer_subgraph(llm)

    def _router(state: BlogState):
        return router_node(state, llm)

    def _research(state: BlogState):
        return research_node(state, llm, research)

    def _orchestrator(state: BlogState):
        return orchestrator_node(state, llm)

    g = StateGraph(BlogState)
    g.add_node("router", _router)
    g.add_node("research", _research)
    g.add_node("orchestrator", _orchestrator)
    g.add_node("reducer", reducer_subgraph)

    g.add_edge(START, "router")
    g.add_conditional_edges("router", route_next, {"research": "research", "orchestrator": "orchestrator"})
    g.add_edge("research", "orchestrator")
    g.add_edge("orchestrator", "reducer")
    g.add_edge("reducer", END)

    return g.compile()


@lru_cache(maxsize=1)
def get_blog_app():
    return build_blog_app()
