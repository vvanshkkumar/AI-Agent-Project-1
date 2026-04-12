from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from api.ai.llms import get_openai_llm
from api.ai.tools import send_a_email

EMAIL_TOOLS = {
    "send_a_email": send_a_email,
}


def email_assistant(query: str):
    llm_base = get_openai_llm()
    llm = llm_base.bind_tools(list(EMAIL_TOOLS.values()))

    messages = [
        SystemMessage(
            "You are a helpful Email Assistant. After drafting the email, you must "
            "call send_a_email with subject and content so it is actually delivered."
        ),
        HumanMessage(f"{query}, write a small email on this query to send"),
    ]

    ai_msg = llm.invoke(messages)
    messages.append(ai_msg)

    tool_calls = getattr(ai_msg, "tool_calls", None) or []
    for tc in tool_calls:
        if tool := EMAIL_TOOLS.get(tc["name"]):
            messages.append(
                ToolMessage(
                    content=str(tool.invoke(tc["args"])),
                    tool_call_id=tc["id"],
                )
            )
    # Each `tc` is one tool request from the model:
    # - tc["name"] — which tool to run (must match a key in EMAIL_TOOLS, e.g. "send_a_email").
    # - tc["args"] — keyword args for that tool, e.g. {"subject": "...", "content": "..."}.
    # - tc["id"] — id the provider uses so this ToolMessage is paired with that exact request.

    return llm.invoke(messages) if tool_calls else ai_msg