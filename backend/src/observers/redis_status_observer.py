import logging
from datetime import datetime

from cache import get_redis_client
from observers.base import PipelineObserver

logger = logging.getLogger(__name__)

PIPELINE_NODES_ORDERED = [
    "router_node",
    "research_node",
    "orchestrator_node",
    "worker_node",
    "merge_content",
    "decide_images",
    "generate_and_place_images",
]


class RedisStatusObserver(PipelineObserver):
    def on_node_enter(self, run_id: str, node: str) -> None:
        try:
            client = get_redis_client()
            client.hset(
                f"run:{run_id}",
                mapping={
                    "current_node": node,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
            client.expire(f"run:{run_id}", 3600)
        except Exception:
            logger.exception("Failed to update Redis pipeline status")

    def on_node_exit(
        self,
        run_id: str,
        node: str,
        status: str,
        meta: dict,
    ) -> None:
        try:
            client = get_redis_client()
            client.hset(
                f"run:{run_id}",
                mapping={
                    "last_completed_node": node,
                    "last_status": status,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )
            client.expire(f"run:{run_id}", 3600)
            if status == "SUCCESS":
                client.rpush(f"run:{run_id}:completed", node)
                client.expire(f"run:{run_id}:completed", 3600)
        except Exception:
            logger.exception("Failed to update Redis pipeline status")
