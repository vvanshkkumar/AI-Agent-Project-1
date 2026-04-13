import os

from api.blog.research.null_provider import NullResearchProvider
from api.blog.research.protocol import ResearchProvider
from api.blog.research.tavily_provider import TavilyResearchProvider


def get_research_provider() -> ResearchProvider:
    if os.getenv("TAVILY_API_KEY"):
        return TavilyResearchProvider()
    return NullResearchProvider()
