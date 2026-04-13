from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from api.blog.config import get_blog_output_root
from api.blog.images.gemini import gemini_generate_image_bytes
from api.blog.schemas import GlobalImagePlan
from api.blog.state import BlogState
from api.blog.storage import get_asset_url
from api.blog.text_utils import safe_slug


def _workspace_path(state: BlogState) -> Path:
    wd = state.get("workspace_dir")
    if wd:
        return Path(wd)
    rid = state.get("run_id")
    if rid:
        return get_blog_output_root() / rid
    return get_blog_output_root() / "default"


def merge_content(state: BlogState) -> dict:
    plan = state["plan"]
    if plan is None:
        raise ValueError("merge_content called without plan.")
    ordered_sections = [md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    body = "\n\n".join(ordered_sections).strip()
    merged_md = f"# {plan.blog_title}\n\n{body}\n"
    return {"merged_md": merged_md}


DECIDE_IMAGES_SYSTEM = """You are an expert technical editor.
Decide if images/diagrams are needed for THIS blog.

Rules:
- Max 3 images total.
- Each image must materially improve understanding (diagram/flow/table-like visual).
- Insert placeholders exactly: [[IMAGE_1]], [[IMAGE_2]], [[IMAGE_3]].
- If no images needed: md_with_placeholders must equal input and images=[].
- Avoid decorative images; prefer technical diagrams with short labels.
Return strictly GlobalImagePlan.
"""


def decide_images(state: BlogState, llm) -> dict:
    planner = llm.with_structured_output(GlobalImagePlan)
    merged_md = state["merged_md"]
    plan = state["plan"]
    assert plan is not None

    image_plan = planner.invoke(
        [
            SystemMessage(content=DECIDE_IMAGES_SYSTEM),
            HumanMessage(
                content=(
                    f"Blog kind: {plan.blog_kind}\n"
                    f"Topic: {state['topic']}\n\n"
                    "Insert placeholders + propose image prompts.\n\n"
                    f"{merged_md}"
                )
            ),
        ]
    )

    return {
        "md_with_placeholders": image_plan.md_with_placeholders,
        "image_specs": [img.model_dump() for img in image_plan.images],
    }


def generate_and_place_images(state: BlogState) -> dict:
    plan = state["plan"]
    assert plan is not None

    workspace = _workspace_path(state)
    workspace.mkdir(parents=True, exist_ok=True)

    md = state.get("md_with_placeholders") or state["merged_md"]
    image_specs = state.get("image_specs", []) or []

    if not image_specs:
        filename = f"{safe_slug(plan.blog_title)}.md"
        out = workspace / filename
        out.write_text(md, encoding="utf-8")
        return {"final": md}

    images_dir = workspace / "images"
    images_dir.mkdir(exist_ok=True)

    for spec in image_specs:
        placeholder = spec["placeholder"]
        filename = spec["filename"]
        out_path = images_dir / filename

        if not out_path.exists():
            try:
                img_bytes = gemini_generate_image_bytes(spec["prompt"])
                out_path.write_bytes(img_bytes)
            except Exception as e:
                prompt_block = (
                    f"> **[IMAGE GENERATION FAILED]** {spec.get('caption', '')}\n>\n"
                    f"> **Alt:** {spec.get('alt', '')}\n>\n"
                    f"> **Prompt:** {spec.get('prompt', '')}\n>\n"
                    f"> **Error:** {e}\n"
                )
                md = md.replace(placeholder, prompt_block)
                continue

        run_id = state.get("run_id", "")
        asset_url = get_asset_url(run_id, f"images/{filename}") if run_id else f"images/{filename}"
        img_md = f"![{spec['alt']}]({asset_url})\n*{spec['caption']}*"
        md = md.replace(placeholder, img_md)

    filename = f"{safe_slug(plan.blog_title)}.md"
    out = workspace / filename
    out.write_text(md, encoding="utf-8")
    return {"final": md}


def build_reducer_subgraph(llm):
    reducer_graph = StateGraph(BlogState)
    reducer_graph.add_node("merge_content", merge_content)
    reducer_graph.add_node("decide_images", lambda s: decide_images(s, llm))
    reducer_graph.add_node("generate_and_place_images", generate_and_place_images)
    reducer_graph.add_edge(START, "merge_content")
    reducer_graph.add_edge("merge_content", "decide_images")
    reducer_graph.add_edge("decide_images", "generate_and_place_images")
    reducer_graph.add_edge("generate_and_place_images", END)
    return reducer_graph.compile()
