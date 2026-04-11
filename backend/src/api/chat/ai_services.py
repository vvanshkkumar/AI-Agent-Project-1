import os
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or None
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME") or ""

if not OPENAI_API_KEY:
    raise NotImplementedError("'OPENAI_API_KEY' is required")

class EmailMessage(BaseModel) :
    subject: str
    content: str
    invalid_request: bool | None = Field(default=False)


openai_params = {
    "model" : OPENAI_MODEL_NAME,
    "api_key": OPENAI_API_KEY
}
if OPENAI_BASE_URL :
    openai_params['base_url'] = OPENAI_BASE_URL

llm_base = ChatOpenAI(**openai_params)

llm = llm_base.with_structured_output(EmailMessage)

message = [
    SystemMessage(content="you are a helpful email assistant"),
    HumanMessage(content="create a small email about benefits of coffee"),
]

result = llm.invoke(message).content

print(result)