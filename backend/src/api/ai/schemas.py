from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI


class EmailMessageSchema(BaseModel) :
    subject: str
    content: str
    invalid_request: bool | None = Field(default=False)