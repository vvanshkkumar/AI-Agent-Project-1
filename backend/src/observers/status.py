from sqlalchemy import asc
from sqlmodel import Session, select

from api.blog.db_models import PipelineEvent
from cache import get_redis_client
from db import get_engine
from observers.redis_status_observer import PIPELINE_NODES_ORDERED


def get_run_status(run_id: str) -> dict:
    redis_status = _read_redis_status(run_id)
    history = _read_pipeline_history(run_id)

    completed_nodes = redis_status.get("completed_nodes", [])
    if not completed_nodes:
        completed_nodes = _completed_nodes_from_history(history)

    unique_completed = list(dict.fromkeys(completed_nodes))
    progress_pct = round(
        min(len(unique_completed), len(PIPELINE_NODES_ORDERED))
        / len(PIPELINE_NODES_ORDERED)
        * 100
    )

    return {
        "run_id": run_id,
        "current_node": redis_status.get("current_node"),
        "completed_nodes": unique_completed,
        "progress_pct": progress_pct,
        "last_updated": redis_status.get("last_updated"),
        "history": history,
    }


def _read_redis_status(run_id: str) -> dict:
    try:
        client = get_redis_client()
        raw = client.hgetall(f"run:{run_id}") or {}
        completed = client.lrange(f"run:{run_id}:completed", 0, -1) or []
        return {
            "current_node": raw.get("current_node"),
            "last_updated": raw.get("updated_at"),
            "completed_nodes": completed,
        }
    except Exception:
        return {}


def _read_pipeline_history(run_id: str) -> list[dict]:
    with Session(get_engine()) as session:
        stmt = (
            select(PipelineEvent)
            .where(PipelineEvent.run_id == run_id)
            .order_by(asc(PipelineEvent.created_at), asc(PipelineEvent.id))
        )
        events = session.exec(stmt).all()

    return [
        {
            "node": event.node_name,
            "status": event.status,
            "timestamp": event.created_at.isoformat(),
            "meta": event.meta or {},
        }
        for event in events
    ]


def _completed_nodes_from_history(history: list[dict]) -> list[str]:
    return [
        event["node"]
        for event in history
        if event["status"] == "SUCCESS"
    ]
