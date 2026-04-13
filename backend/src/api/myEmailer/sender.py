import smtplib
from email.message import EmailMessage

from settings import get_email_settings


def send_mail(
    subject: str = "No subject provided",
    content: str = "No message provided",
    to_email: str | None = None,
    html_content: str | None = None,
    inline_assets: list[dict[str, str | bytes]] | None = None,
):
    email_settings = get_email_settings()
    sender = str(email_settings["EMAIL_ADDRESS"])
    recipient = to_email or sender

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(content)
    if html_content:
        msg.add_alternative(html_content, subtype="html")
        html_part = msg.get_payload()[-1]
        for asset in inline_assets or []:
            html_part.add_related(
                asset["data"],
                maintype=str(asset["maintype"]),
                subtype=str(asset["subtype"]),
                cid=f"<{asset['cid']}>",
                filename=str(asset["filename"]),
                disposition="inline",
            )

    with smtplib.SMTP_SSL(
        str(email_settings["EMAIL_HOST"]),
        int(email_settings["EMAIL_PORT"]),
    ) as smtp:
        smtp.login(sender, str(email_settings["EMAIL_PASSWORD"]))
        return smtp.send_message(msg)
