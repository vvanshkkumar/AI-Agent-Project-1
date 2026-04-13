from langchain_core.messages import HumanMessage, SystemMessage

from api.ai.schemas import EmailMessageSchema
from api.ai.llms import get_chat_llm


def generate_email(query:str) -> EmailMessageSchema :
    llm_base = get_chat_llm()
    llm = llm_base.with_structured_output(EmailMessageSchema)

    message = [
        SystemMessage("You are a helpful Email Assistant writer"),
        HumanMessage(f"{query}, write a small email on this query to send")
    ]

    return llm.invoke(message)
