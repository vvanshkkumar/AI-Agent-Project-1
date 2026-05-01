import logging
from datetime import datetime

from sqlmodel import Session

from api.blog.db_models import PipelineEvent
from db import get_engine
from observers.base import PipelineObserver

logger = logging.getLogger(__name__)


class AuditLogObserver(PipelineObserver):
    def on_node_enter(self, run_id: str, node: str) -> None:
        self._write_event(run_id, node, "RUNNING", {})

    def on_node_exit(
        self,
        run_id: str,
        node: str,
        status: str,
        meta: dict,
    ) -> None:
        self._write_event(run_id, node, status, meta)

    def _write_event(
        self,
        run_id: str,
        node: str,
        status: str,
        meta: dict,
    ) -> None:
        try:
            with Session(get_engine()) as session:
                session.add(
                    PipelineEvent(
                        run_id=run_id,
                        node_name=node,
                        status=status,
                        meta=meta,
                        created_at=datetime.utcnow(),
                    )
                )
                session.commit()
        except Exception:
            logger.exception("Failed to persist pipeline audit event")
