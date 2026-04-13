# AI Agent Project 1

Python FastAPI backend with:

- chat email drafting
- AI-generated blog generation
- scheduled email delivery
- PostgreSQL persistence

## PostgreSQL vs SQLite

PostgreSQL is the intended app database. Docker Compose already runs PostgreSQL and the app defaults to that stack.

SQLite support is only useful for local smoke tests or temporary validation. It is not required for your normal project flow.

## Setup

1. Copy `.env.example` to `.env`.
2. Fill in the required secrets:
   - `OPENAI_API_KEY` for chat and blog generation
   - `EMAIL_ADDRESS` and `EMAIL_PASSWORD` for sending mail
   - `DATABASE_URL` if you are not using the default local PostgreSQL URL
3. Start PostgreSQL + API with Docker Compose:

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
- `GET /api/blog/runs/{run_id}/markdown`
- `GET /api/blog/runs/{run_id}/preview`

## Optional Keys

- `TAVILY_API_KEY` enables web research during blog generation
- `GOOGLE_API_KEY` enables image generation during blog creation

Without those optional keys, the app still runs. Research falls back to no web results, and image generation inserts a failure note instead of crashing the request.

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
