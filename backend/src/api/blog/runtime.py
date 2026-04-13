from settings import get_gemini_text_settings


def describe_blog_runtime() -> dict[str, str]:
    settings = get_gemini_text_settings(
        model_env_key="BLOG_GEMINI_MODEL_NAME",
    )
    return {
        "provider": "gemini",
        "model": settings["model"],
    }
