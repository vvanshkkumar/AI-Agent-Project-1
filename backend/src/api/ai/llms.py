from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel

from settings import get_gemini_text_settings


@dataclass
class GeminiTextMessage:
    content: str


def _coerce_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _split_messages(messages: list[Any]) -> tuple[str, str]:
    system_parts: list[str] = []
    user_parts: list[str] = []

    for message in messages:
        content = _coerce_message_text(getattr(message, "content", message)).strip()
        if not content:
            continue
        if message.__class__.__name__ == "SystemMessage":
            system_parts.append(content)
        else:
            user_parts.append(content)

    return "\n\n".join(system_parts), "\n\n".join(user_parts) or "Respond to the latest request."


def _extract_response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if text:
        return text

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        text_parts = [part.text for part in parts if getattr(part, "text", None)]
        if text_parts:
            return "\n".join(text_parts)
    return ""


class GeminiStructuredInvoker:
    def __init__(self, llm: "GeminiLLM", schema: type[BaseModel]):
        self._llm = llm
        self._schema = schema

    def invoke(self, messages: list[Any]):
        response = self._llm._generate(messages, schema=self._schema)
        text = _extract_response_text(response).strip()
        if not text:
            raise RuntimeError("Gemini returned an empty structured response.")
        return self._schema.model_validate_json(text)


class GeminiLLM:
    def __init__(self, *, model_env_key: str = "GEMINI_MODEL_NAME"):
        settings = get_gemini_text_settings(model_env_key=model_env_key)
        self.model = settings["model"]
        self.client = genai.Client(api_key=settings["api_key"])

    def _generate(self, messages: list[Any], schema: type[BaseModel] | None = None):
        system_instruction, prompt = _split_messages(messages)
        config_kwargs: dict[str, Any] = {}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction
        if schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = schema

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
        return self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config,
        )

    def invoke(self, messages: list[Any]) -> GeminiTextMessage:
        response = self._generate(messages)
        text = _extract_response_text(response).strip()
        if not text:
            raise RuntimeError("Gemini returned an empty text response.")
        return GeminiTextMessage(content=text)

    def with_structured_output(self, schema: type[BaseModel]) -> GeminiStructuredInvoker:
        return GeminiStructuredInvoker(self, schema)


def get_openai_llm(
    *,
    model_env_key: str = "GEMINI_MODEL_NAME",
):
    return GeminiLLM(model_env_key=model_env_key)


def get_chat_llm():
    return get_openai_llm()


def get_blog_llm():
    return get_openai_llm(
        model_env_key="BLOG_GEMINI_MODEL_NAME",
    )
