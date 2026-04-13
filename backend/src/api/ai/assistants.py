from api.ai.services import generate_email
from api.ai.tools import send_a_email


def email_assistant(query: str):
    draft = generate_email(query)
    if draft.invalid_request:
        return draft
    send_status = send_a_email.invoke({"subject": draft.subject, "content": draft.content})
    return {
        "subject": draft.subject,
        "content": draft.content,
        "send_status": send_status,
    }
