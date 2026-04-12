from langchain_core.tools import tool
from api.myEmailer.sender import send_mail


@tool
def send_a_email(subject: str, content: str):
    """
    Send an email to myself with a subject and content.

    This tool sends an email to the configured default email address
    using the SMTP sender utility.

    Arguments:
        subject: str - Subject line of the email
        content: str - Body content of the email

    Returns:
        str - "Sent email" if successful, otherwise "Not sent"
    """
    try:
        send_mail(subject, content)
    except Exception:
        return "not sent"
    return "sent"
