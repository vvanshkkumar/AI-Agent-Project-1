from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from api.blog.config import get_blog_output_root
from api.blog.images.gemini import gemini_generate_image_bytes
from api.blog.kafka_sections import collect_sections_from_kafka
from api.blog.schemas import GlobalImagePlan
from api.blog.state import BlogState
from api.blog.storage import get_asset_url
from api.blog.text_utils import safe_slug
from observers.publisher import publisher


def _workspace_path(state: BlogState) -> Path:
    wd = state.get("workspace_dir")
    if wd:
        return Path(wd)
    rid = state.get("run_id")
    if rid:
        return get_blog_output_root() / rid
    return get_blog_output_root() / "default"


def merge_content(state: BlogState) -> dict:
    run_id = state.get("run_id", "unknown")
    publisher.on_node_enter(run_id, "merge_content")
    try:
        plan = state["plan"]
        if plan is None:
            raise ValueError("merge_content called without plan.")
        expected_count = int(state.get("expected_section_count") or len(plan.tasks))
        if expected_count <= 0:
            raise ValueError("No expected section count found for reducer.")

        # Sections are now produced by external Kafka workers. The reducer waits
        # here so the downstream image/final-write steps only see complete blog
        # content, not partial sections.
        ordered_pairs = collect_sections_from_kafka(run_id, expected_count)
        ordered_sections = [md for _, md in sorted(ordered_pairs, key=lambda item: item[0])]
        body = "\n\n".join(ordered_sections).strip()
        merged_md = f"# {plan.blog_title}\n\n{body}\n"
        publisher.on_node_exit(
            run_id,
            "merge_content",
            "SUCCESS",
            {"section_count": len(ordered_sections), "merged_chars": len(merged_md)},
        )
        return {"merged_md": merged_md}
    except Exception as exc:
        publisher.on_node_exit(run_id, "merge_content", "FAILED", {"error": str(exc)})
        raise


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
    run_id = state.get("run_id", "unknown")
    publisher.on_node_enter(run_id, "decide_images")
    try:
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

        image_specs = [img.model_dump() for img in image_plan.images]
        publisher.on_node_exit(
            run_id,
            "decide_images",
            "SUCCESS",
            {"image_count": len(image_specs)},
        )
        return {
            "md_with_placeholders": image_plan.md_with_placeholders,
            "image_specs": image_specs,
        }
    except Exception as exc:
        publisher.on_node_exit(run_id, "decide_images", "FAILED", {"error": str(exc)})
        raise


def generate_and_place_images(state: BlogState) -> dict:
    run_id = state.get("run_id", "unknown")
    publisher.on_node_enter(run_id, "generate_and_place_images")
    try:
        plan = state["plan"]
        assert plan is not None

        workspace = _workspace_path(state)
        workspace.mkdir(parents=True, exist_ok=True)

        md = state.get("md_with_placeholders") or state["merged_md"]
        image_specs = state.get("image_specs", []) or []
        generated_count = 0
        failed_count = 0

        if not image_specs:
            filename = f"{safe_slug(plan.blog_title)}.md"
            out = workspace / filename
            out.write_text(md, encoding="utf-8")
            publisher.on_node_exit(
                run_id,
                "generate_and_place_images",
                "SUCCESS",
                {"image_count": 0, "final_chars": len(md), "md_file": str(out)},
            )
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
                    generated_count += 1
                except Exception as e:
                    failed_count += 1
                    prompt_block = (
                        f"> **[IMAGE GENERATION FAILED]** {spec.get('caption', '')}\n>\n"
                        f"> **Alt:** {spec.get('alt', '')}\n>\n"
                        f"> **Prompt:** {spec.get('prompt', '')}\n>\n"
                        f"> **Error:** {e}\n"
                    )
                    md = md.replace(placeholder, prompt_block)
                    continue

            asset_url = get_asset_url(run_id, f"images/{filename}") if run_id else f"images/{filename}"
            img_md = f"![{spec['alt']}]({asset_url})\n*{spec['caption']}*"
            md = md.replace(placeholder, img_md)

        filename = f"{safe_slug(plan.blog_title)}.md"
        out = workspace / filename
        out.write_text(md, encoding="utf-8")
        publisher.on_node_exit(
            run_id,
            "generate_and_place_images",
            "SUCCESS",
            {
                "image_count": len(image_specs),
                "generated_image_count": generated_count,
                "failed_image_count": failed_count,
                "final_chars": len(md),
                "md_file": str(out),
            },
        )
        return {"final": md}
    except Exception as exc:
        publisher.on_node_exit(
            run_id,
            "generate_and_place_images",
            "FAILED",
            {"error": str(exc)},
        )
        raise


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
