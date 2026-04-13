import os
from pathlib import Path


class ConfigurationError(RuntimeError):
    """Raised when required runtime configuration is missing or invalid."""


_ENV_LOADED = False
_DEFAULT_DATABASE_URL = "postgresql+psycopg2://dbuser:db-password@localhost:5432/mydb"


def _resolve_project_root(current_file: Path) -> Path:
    current = current_file.resolve()
    ancestors = [current.parent, *current.parents]

    for candidate in ancestors:
        if any(
            (candidate / marker).exists()
            for marker in (".git", "docker-compose.yml", ".env", ".env.example")
        ):
            return candidate

    for candidate in ancestors:
        if (candidate / "main.py").exists() and (candidate / "db.py").exists():
            return candidate

    return current.parent


def get_project_root() -> Path:
    return _resolve_project_root(Path(__file__))


def _parse_env_line(line: str) -> tuple[str, str] | None:
    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None
    if raw.startswith("export "):
        raw = raw[len("export ") :].strip()
    if "=" not in raw:
        return None
    key, value = raw.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    elif " #" in value:
        value = value.split(" #", 1)[0].rstrip()
    return key, value


def load_project_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    candidates = [
        get_project_root() / ".env",
        get_project_root() / "backend" / ".env",
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            parsed = _parse_env_line(line)
            if parsed is None:
                continue
            key, value = parsed
            os.environ.setdefault(key, value)

    _ENV_LOADED = True


def get_database_url() -> str:
    load_project_env()
    return os.environ.get("DATABASE_URL") or _DEFAULT_DATABASE_URL


def get_google_api_key() -> str:
    load_project_env()
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ConfigurationError("GOOGLE_API_KEY is required for Gemini-powered endpoints.")
    return api_key


def get_gemini_text_settings(
    *,
    model_env_key: str = "GEMINI_MODEL_NAME",
) -> dict[str, str]:
    load_project_env()
    model_name = os.environ.get(model_env_key) or os.environ.get("GEMINI_MODEL_NAME") or "gemini-2.5-flash"
    return {
        "model": model_name,
        "api_key": get_google_api_key(),
    }


def get_email_settings() -> dict[str, str | int]:
    load_project_env()
    email_address = os.environ.get("EMAIL_ADDRESS")
    email_password = os.environ.get("EMAIL_PASSWORD")

    missing = []
    if not email_address:
        missing.append("EMAIL_ADDRESS")
    if not email_password:
        missing.append("EMAIL_PASSWORD")
    if missing:
        raise ConfigurationError(
            f"Missing email configuration: {', '.join(missing)}."
        )

    return {
        "EMAIL_ADDRESS": email_address,
        "EMAIL_PASSWORD": email_password,
        "EMAIL_HOST": os.environ.get("EMAIL_HOST") or "smtp.gmail.com",
        "EMAIL_PORT": int(os.environ.get("EMAIL_PORT") or 465),
    }
