import os

from settings import load_project_env

load_project_env()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
BLOG_TASKS_TOPIC = os.getenv("BLOG_TASKS_TOPIC", "blog.tasks")
BLOG_SECTIONS_TOPIC = os.getenv("BLOG_SECTIONS_TOPIC", "blog.sections")
BLOG_EVENTS_TOPIC = os.getenv("BLOG_EVENTS_TOPIC", "blog.events")
NUM_TASK_PARTITIONS = int(os.getenv("KAFKA_NUM_TASK_PARTITIONS", "6"))
SECTION_COLLECTION_TIMEOUT_SECONDS = int(
    os.getenv("KAFKA_SECTION_TIMEOUT_SECONDS", "180")
)
SECTION_MAX_ATTEMPTS = int(os.getenv("KAFKA_SECTION_MAX_ATTEMPTS", "3"))
