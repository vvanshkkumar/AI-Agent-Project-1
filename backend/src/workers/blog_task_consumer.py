import json
import logging
import time
from pathlib import Path

from kafka import KafkaConsumer, KafkaProducer

from api.ai.llms import get_blog_llm
from api.blog.kafka_sections import ensure_blog_topics
from api.blog.nodes.worker_node import generate_section_from_payload
from kafka_config import BLOG_SECTIONS_TOPIC, BLOG_TASKS_TOPIC, KAFKA_BOOTSTRAP_SERVERS
from observers.audit_log_observer import AuditLogObserver
from observers.publisher import publisher
from observers.redis_status_observer import RedisStatusObserver
from observers.structured_log_observer import StructuredLogObserver
from settings import load_project_env

logger = logging.getLogger(__name__)


def section_path_for(payload: dict) -> Path:
    workspace = Path(payload.get("workspace_dir") or f"data/blog_runs/{payload['run_id']}")
    return workspace / "sections" / f"{payload['task_id']}.md"


def section_already_exists(payload: dict) -> bool:
    path = section_path_for(payload)
    return path.exists() and path.stat().st_size > 0


def read_existing_section(payload: dict) -> str:
    return section_path_for(payload).read_text(encoding="utf-8")


def write_section(payload: dict, markdown: str) -> None:
    path = section_path_for(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    # The file write happens before the Kafka offset commit. If the worker dies
    # after this write but before commit, redelivery hits the idempotency check
    # and avoids a duplicate Gemini call.
    path.write_text(markdown, encoding="utf-8")


def build_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        BLOG_TASKS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="blog-worker-group",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=lambda message: json.loads(message.decode("utf-8")),
        session_timeout_ms=30000,
        heartbeat_interval_ms=10000,
    )


def build_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        key_serializer=lambda value: str(value).encode("utf-8"),
        acks="all",
        retries=3,
    )


def configure_observers() -> None:
    publisher.attach(AuditLogObserver())
    publisher.attach(RedisStatusObserver())
    publisher.attach(StructuredLogObserver())


def publish_section(producer: KafkaProducer, payload: dict, markdown: str) -> None:
    producer.send(
        BLOG_SECTIONS_TOPIC,
        key=payload["run_id"],
        value={
            "run_id": payload["run_id"],
            "task_id": payload["task_id"],
            "content": markdown,
        },
    )
    producer.flush()


def run() -> None:
    load_project_env()
    configure_observers()
    wait_for_kafka()
    llm = get_blog_llm()
    consumer = build_consumer()
    producer = build_producer()

    for message in consumer:
        payload = message.value
        run_id = payload["run_id"]
        task_id = payload["task_id"]

        try:
            publisher.on_node_enter(run_id, "worker_node")
            if section_already_exists(payload):
                markdown = read_existing_section(payload)
                logger.info(
                    json.dumps(
                        {
                            "event": "section_cache_hit",
                            "run_id": run_id,
                            "task_id": task_id,
                        }
                    )
                )
            else:
                _task, markdown = generate_section_from_payload(payload, llm)
                write_section(payload, markdown)

            publish_section(producer, payload, markdown)

            # Manual commit is the delivery boundary. Until this succeeds, Kafka
            # is allowed to redeliver the task to this or another worker.
            consumer.commit()
            publisher.on_node_exit(
                run_id,
                "worker_node",
                "SUCCESS",
                {"task_id": task_id, "section_chars": len(markdown)},
            )
            logger.info(
                json.dumps(
                    {
                        "event": "section_completed_offset_committed",
                        "run_id": run_id,
                        "task_id": task_id,
                    }
                )
            )
        except Exception as exc:
            publisher.on_node_exit(run_id, "worker_node", "FAILED", {"error": str(exc)})
            # Do not commit on failure. Kafka will redeliver the task according
            # to consumer group ownership, which is the reliability mechanism.
            logger.exception(
                json.dumps(
                    {
                        "event": "section_failed_offset_not_committed",
                        "run_id": run_id,
                        "task_id": task_id,
                        "error": str(exc),
                    }
                )
            )

def wait_for_kafka(max_attempts: int = 30, delay_seconds: int = 2) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            ensure_blog_topics()
            return
        except Exception as exc:
            logger.warning(
                json.dumps(
                    {
                        "event": "kafka_not_ready",
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "error": str(exc),
                    }
                )
            )
            time.sleep(delay_seconds)
    raise RuntimeError("Kafka did not become ready for blog worker startup.")


if __name__ == "__main__":
    run()
