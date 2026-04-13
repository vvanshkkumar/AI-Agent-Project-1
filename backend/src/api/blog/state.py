from __future__ import annotations

import operator
from typing import Annotated, List, Optional

from typing_extensions import NotRequired, TypedDict

from api.blog.schemas import EvidenceItem, Plan


class BlogState(TypedDict):
    topic: str
    run_id: NotRequired[str]
    workspace_dir: NotRequired[str]

    mode: str
    needs_research: bool
    queries: List[str]
    evidence: List[EvidenceItem]
    plan: Optional[Plan]

    as_of: str
    recency_days: int

    sections: Annotated[List[tuple[int, str]], operator.add]

    merged_md: str
    md_with_placeholders: str
    image_specs: List[dict]
    final: str
