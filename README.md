# AI Agent Project 1

Python FastAPI backend with:

- chat email drafting
- AI-generated blog generation
- scheduled email delivery
- PostgreSQL persistence
- Redis-backed caching and blog generation rate limiting
- Celery-backed scheduled email delivery with retries and failed-job tracking
- Kafka-backed distributed blog section generation

## PostgreSQL vs SQLite

PostgreSQL is the intended app database. Docker Compose already runs PostgreSQL and the app defaults to that stack.

SQLite support is only useful for local smoke tests or temporary validation. It is not required for your normal project flow.

## Setup

1. Copy `.env.example` to `.env`.
2. Fill in the required secrets:
   - `GOOGLE_API_KEY` for Gemini chat, blog generation, and image generation
   - `EMAIL_ADDRESS` and `EMAIL_PASSWORD` for sending mail
   - `DATABASE_URL` if you are not using the default local PostgreSQL URL
   - `EMAIL_PROVIDER=smtp` unless you add another email provider strategy
3. Start PostgreSQL + Redis + API with Docker Compose:

```bash
docker compose up --build
```

The default local database URL is:

```text
postgresql+psycopg2://dbuser:db-password@localhost:5432/mydb
```

## Local Run Without Docker

Start PostgreSQL first, then:

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --app-dir src --reload
```

The app auto-loads `.env` from the project root for local development.

## Endpoints

- `GET /`
- `GET /api/health/`
- `GET /api/recents/`
- `POST /api/create/`
- `POST /api/blog/generate`
- `POST /api/blog/send-existing`
- `POST /api/blog/schedule-existing`
- `GET /api/blog/scheduled`
- `GET /api/blog/runtime`
- `GET /api/blog/runs/{run_id}/status`
- `GET /api/blog/runs/{run_id}/sections`
- `GET /api/blog/runs/{run_id}/markdown`
- `GET /api/blog/runs/{run_id}/preview`
- `GET /api/jobs/failed`
- `POST /api/jobs/failed/{job_id}/retry`

## Redis Caching and Rate Limiting

Redis is used for:

- a 5-minute cache for `GET /api/recents/`
- permanent cache entries for rendered blog previews
- per-client rate limiting on `POST /api/blog/generate`

Default blog generation limit:

```text
BLOG_GENERATE_RATE_LIMIT=3
BLOG_GENERATE_RATE_WINDOW_SECONDS=60
```

If Redis is unavailable, normal cache reads fall back to the database/filesystem. Blog generation fails closed with `503` because the rate limit cannot be enforced.

## Blog Pipeline Observability

Blog generation nodes publish lifecycle events when each node starts and finishes. Events are written to:

- PostgreSQL `pipeline_events` table for durable history
- Redis keys for live status polling
- structured JSON application logs

Use:

```text
GET /api/blog/runs/{run_id}/status
```

to inspect the current node, completed nodes, progress percentage, and full node history for a blog run.

## Reliable Scheduled Email Delivery

Scheduled emails are dispatched by Celery Beat every 60 seconds and sent by Celery workers through the configured email provider strategy. The old in-process API scheduler is not started by the FastAPI app, which prevents duplicate schedulers when multiple API instances run.

Email send tasks use late acknowledgements, worker-lost rejection, and exponential retry backoff. When retries are exhausted, the scheduled email is marked `failed` and a row is written to `failed_jobs`.

Use:

```text
GET /api/jobs/failed
POST /api/jobs/failed/{job_id}/retry
```

to inspect and requeue failed scheduled email jobs.

## Kafka Blog Section Fan-out

Blog section writing is distributed through Kafka:

```text
orchestrator_node
  -> publishes one message per planned section to blog.tasks
blog-worker
  -> consumes blog.tasks
  -> writes section markdown under data/blog_runs/{run_id}/sections/
  -> publishes completed sections to blog.sections
reducer
  -> waits for all expected sections
  -> merges, plans images, and writes final markdown
```

The blog worker uses manual Kafka offset commits. It writes the section file and publishes the result before committing the consumed task offset, so a worker crash before commit causes Kafka redelivery. Existing section files are treated as idempotency hits to avoid duplicate Gemini calls on redelivery.

Each planned section also gets a `section_attempts` row. Workers update those rows from `PENDING` to `PROCESSING`, `DONE`, `FAILED`, or `PERMANENTLY_FAILED`. A section is treated as a poison message after `KAFKA_SECTION_MAX_ATTEMPTS=3`, and the worker commits the Kafka offset so the consumer group can continue.

Use:

```text
GET /api/blog/runs/{run_id}/sections
```

to inspect per-section status, attempts, timestamps, and errors.

Run multiple workers locally with:

```bash
docker compose up --build --scale blog-worker=3
```

## Optional Keys

- `TAVILY_API_KEY` enables web research during blog generation
- `GOOGLE_API_KEY` enables Gemini-powered text and image generation
- `SENDGRID_API_KEY` is reserved for a future SendGrid email strategy

Without those optional keys, the app still runs. Research falls back to no web results, and image generation inserts a failure note instead of crashing the request.

## Email Provider Strategy

Email delivery now goes through a provider strategy behind the existing `send_mail(...)` helper. SMTP remains the default provider and preserves support for plain text, HTML, and inline newsletter images. Set `EMAIL_PROVIDER=smtp` for the current implementation.

## Model Usage

- `GOOGLE_API_KEY` is used by the Gemini text and image flows.
- `GEMINI_MODEL_NAME` is used by the chat/email flow.
- Blog generation uses `BLOG_GEMINI_MODEL_NAME` if set, otherwise it falls back to `GEMINI_MODEL_NAME`.
- `GOOGLE_API_KEY` is only used for image generation during the final blog image step.
- `TAVILY_API_KEY` is only used for the blog research step.

## Viewing Generated Blogs

Each successful blog generation now returns:

- `markdown_url`: raw Markdown with web-safe image links
- `preview_url`: rendered HTML preview in the browser

Generated files are also persisted locally under `backend/data/` through Docker Compose.

To send an already-generated blog without re-running AI, use `send-existing` or `schedule-existing` with the saved `run_id`.
