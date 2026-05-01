import os
from dataclasses import dataclass
from functools import lru_cache

from settings import load_project_env


RECENTS_CACHE_KEY = "cache:recents:chat"
RECENTS_TTL_SECONDS = 300
PREVIEW_CACHE_PREFIX = "cache:preview:"
DEFAULT_RATE_LIMIT = 3
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60


class CacheUnavailableError(RuntimeError):
    """Raised when Redis-backed protection cannot be checked."""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    count: int
    limit: int
    window_seconds: int


def get_redis_url() -> str:
    load_project_env()
    return os.environ.get("REDIS_URL") or "redis://redis:6379/0"


def get_blog_generate_rate_limit() -> int:
    load_project_env()
    return int(os.environ.get("BLOG_GENERATE_RATE_LIMIT") or DEFAULT_RATE_LIMIT)


def get_blog_generate_rate_window_seconds() -> int:
    load_project_env()
    return int(
        os.environ.get("BLOG_GENERATE_RATE_WINDOW_SECONDS")
        or DEFAULT_RATE_LIMIT_WINDOW_SECONDS
    )


@lru_cache(maxsize=1)
def _redis_client():
    try:
        import redis
    except ImportError as exc:
        raise CacheUnavailableError(
            "The redis package is not installed. Run pip install -r requirements.txt."
        ) from exc
    return redis.Redis.from_url(get_redis_url(), decode_responses=True)


def get_redis_client():
    return _redis_client()


def _is_redis_error(exc: Exception) -> bool:
    try:
        import redis
    except ImportError:
        return False
    return isinstance(exc, redis.RedisError)


def get_cached_recents() -> str | None:
    try:
        return _redis_client().get(RECENTS_CACHE_KEY)
    except Exception as exc:
        if _is_redis_error(exc) or isinstance(exc, CacheUnavailableError):
            return None
        raise


def set_cached_recents(data_json: str) -> None:
    try:
        _redis_client().setex(RECENTS_CACHE_KEY, RECENTS_TTL_SECONDS, data_json)
    except Exception as exc:
        if _is_redis_error(exc) or isinstance(exc, CacheUnavailableError):
            return
        raise


def invalidate_recents_cache() -> None:
    try:
        _redis_client().delete(RECENTS_CACHE_KEY)
    except Exception as exc:
        if _is_redis_error(exc) or isinstance(exc, CacheUnavailableError):
            return
        raise


def get_cached_preview(run_id: str) -> str | None:
    try:
        return _redis_client().get(f"{PREVIEW_CACHE_PREFIX}{run_id}")
    except Exception as exc:
        if _is_redis_error(exc) or isinstance(exc, CacheUnavailableError):
            return None
        raise


def set_cached_preview(run_id: str, html: str) -> None:
    try:
        _redis_client().set(f"{PREVIEW_CACHE_PREFIX}{run_id}", html)
    except Exception as exc:
        if _is_redis_error(exc) or isinstance(exc, CacheUnavailableError):
            return
        raise


def check_rate_limit(
    client_key: str,
    *,
    limit: int | None = None,
    window_seconds: int | None = None,
) -> RateLimitResult:
    resolved_limit = limit if limit is not None else get_blog_generate_rate_limit()
    resolved_window = (
        window_seconds
        if window_seconds is not None
        else get_blog_generate_rate_window_seconds()
    )
    key = f"rate:{client_key}:blog_generate"

    try:
        client = _redis_client()
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, resolved_window)
    except Exception as exc:
        if _is_redis_error(exc) or isinstance(exc, CacheUnavailableError):
            raise CacheUnavailableError(
                "Redis is unavailable, so blog generation rate limits cannot be enforced."
            ) from exc
        raise

    return RateLimitResult(
        allowed=count <= resolved_limit,
        count=count,
        limit=resolved_limit,
        window_seconds=resolved_window,
    )
