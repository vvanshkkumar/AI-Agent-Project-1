import logging

from observers.base import PipelineObserver

logger = logging.getLogger(__name__)


class PipelineEventPublisher:
    def __init__(self) -> None:
        self._observers: list[PipelineObserver] = []
        self._observer_keys: set[type[PipelineObserver]] = set()

    def attach(self, observer: PipelineObserver) -> None:
        key = type(observer)
        if key in self._observer_keys:
            return
        self._observers.append(observer)
        self._observer_keys.add(key)

    def on_node_enter(self, run_id: str, node: str) -> None:
        for observer in self._observers:
            try:
                observer.on_node_enter(run_id, node)
            except Exception:
                logger.exception("Pipeline observer failed on node enter")

    def on_node_exit(
        self,
        run_id: str,
        node: str,
        status: str,
        meta: dict | None = None,
    ) -> None:
        payload = meta or {}
        for observer in self._observers:
            try:
                observer.on_node_exit(run_id, node, status, payload)
            except Exception:
                logger.exception("Pipeline observer failed on node exit")


publisher = PipelineEventPublisher()
