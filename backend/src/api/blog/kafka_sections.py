import json
import time
from functools import lru_cache

from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from sqlmodel import Session, select

from api.blog.db_models import SectionAttempt
from api.blog.state import BlogState
from db import get_engine
from kafka_config import (
    BLOG_SECTIONS_TOPIC,
    BLOG_TASKS_TOPIC,
    KAFKA_BOOTSTRAP_SERVERS,
    NUM_TASK_PARTITIONS,
    SECTION_COLLECTION_TIMEOUT_SECONDS,
)


@lru_cache(maxsize=1)
def ensure_blog_topics() -> None:
    admin = KafkaAdminClient(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        client_id="blog-topic-admin",
    )
    try:
        existing = set(admin.list_topics())
        missing = []
        if BLOG_TASKS_TOPIC not in existing:
            missing.append(
                NewTopic(BLOG_TASKS_TOPIC, num_partitions=NUM_TASK_PARTITIONS, replication_factor=1)
            )
        if BLOG_SECTIONS_TOPIC not in existing:
            missing.append(
                NewTopic(BLOG_SECTIONS_TOPIC, num_partitions=NUM_TASK_PARTITIONS, replication_factor=1)
            )
        if not missing:
            return
        # Explicit creation keeps local/dev Kafka aligned with the fan-out
        # design. Auto-created topics often use a single partition, which would
        # make multiple blog-worker processes mostly idle.
        admin.create_topics(missing, validate_only=False)
    except TopicAlreadyExistsError:
        return
    finally:
        admin.close()


@lru_cache(maxsize=1)
def get_blog_task_producer() -> KafkaProducer:
    ensure_blog_topics()
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        key_serializer=lambda value: str(value).encode("utf-8"),
        acks="all",
        retries=3,
    )


def publish_blog_tasks(state: BlogState) -> int:
    plan = state["plan"]
    if plan is None:
        raise ValueError("publish_blog_tasks called without a plan.")

    initialize_section_attempts(state)
    producer = get_blog_task_producer()
    expected_total = len(plan.tasks)
    for task in plan.tasks:
        payload = {
            "run_id": state.get("run_id", ""),
            "task_id": task.id,
            "task": task.model_dump(),
            "topic": state["topic"],
            "mode": state["mode"],
            "as_of": state["as_of"],
            "recency_days": state["recency_days"],
            "plan": plan.model_dump(),
            "evidence": [e.model_dump() for e in state.get("evidence", [])],
            "workspace_dir": state.get("workspace_dir", "."),
            "expected_total": expected_total,
        }
        producer.send(
            BLOG_TASKS_TOPIC,
            key=state.get("run_id", ""),
            value=payload,
        )
    producer.flush()
    return expected_total


def initialize_section_attempts(state: BlogState) -> None:
    plan = state["plan"]
    if plan is None:
        raise ValueError("initialize_section_attempts called without a plan.")
    run_id = state.get("run_id", "")
    with Session(get_engine()) as session:
        for task in plan.tasks:
            stmt = select(SectionAttempt).where(
                SectionAttempt.run_id == run_id,
                SectionAttempt.task_id == task.id,
            )
            existing = session.exec(stmt).first()
            if existing is None:
                session.add(
                    SectionAttempt(
                        run_id=run_id,
                        task_id=task.id,
                        status="PENDING",
                    )
                )
        session.commit()


def collect_sections_from_kafka(
    run_id: str,
    expected_count: int,
    timeout_seconds: int = SECTION_COLLECTION_TIMEOUT_SECONDS,
) -> list[tuple[int, str]]:
    ensure_blog_topics()
    consumer = KafkaConsumer(
        BLOG_SECTIONS_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id=f"reducer-{run_id}",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda message: json.loads(message.decode("utf-8")),
        consumer_timeout_ms=1000,
    )
    sections: dict[int, str] = {}
    deadline = time.time() + timeout_seconds

    try:
        while len(sections) < expected_count:
            if time.time() > deadline:
                raise TimeoutError(
                    f"Only {len(sections)}/{expected_count} sections arrived "
                    f"for run {run_id} within {timeout_seconds}s"
                )

            records = consumer.poll(timeout_ms=1000)
            for messages in records.values():
                for message in messages:
                    payload = message.value
                    if payload.get("run_id") != run_id:
                        continue
                    task_id = int(payload["task_id"])
                    sections[task_id] = payload["content"]
                    if len(sections) >= expected_count:
                        break
                if len(sections) >= expected_count:
                    break
    finally:
        consumer.close()

    return [(task_id, sections[task_id]) for task_id in sorted(sections)]
