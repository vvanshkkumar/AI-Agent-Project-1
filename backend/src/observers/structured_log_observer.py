import json
import logging
from datetime import datetime

from observers.base import PipelineObserver

logger = logging.getLogger(__name__)


class StructuredLogObserver(PipelineObserver):
    def on_node_enter(self, run_id: str, node: str) -> None:
        logger.info(
            json.dumps(
                {
                    "event": "pipeline_node_started",
                    "run_id": run_id,
                    "node": node,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
        )

    def on_node_exit(
        self,
        run_id: str,
        node: str,
        status: str,
        meta: dict,
    ) -> None:
        logger.info(
            json.dumps(
                {
                    "event": "pipeline_node_finished",
                    "run_id": run_id,
                    "node": node,
                    "status": status,
                    "timestamp": datetime.utcnow().isoformat(),
                    **meta,
                }
            )
        )
