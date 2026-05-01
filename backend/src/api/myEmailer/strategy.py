import os
import smtplib
from abc import ABC, abstractmethod
from email.message import EmailMessage
from typing import Any

from settings import ConfigurationError, get_email_settings, load_project_env


InlineAsset = dict[str, str | bytes]


class EmailStrategy(ABC):
    @abstractmethod
    def send(
        self,
        *,
        subject: str,
        content: str,
        to_email: str | None = None,
        html_content: str | None = None,
        inline_assets: list[InlineAsset] | None = None,
    ) -> Any:
        """Send an email or raise an exception on failure."""


class SMTPEmailStrategy(EmailStrategy):
    def __init__(self) -> None:
        self.email_settings = get_email_settings()

    def send(
        self,
        *,
        subject: str,
        content: str,
        to_email: str | None = None,
        html_content: str | None = None,
        inline_assets: list[InlineAsset] | None = None,
    ) -> Any:
        sender = str(self.email_settings["EMAIL_ADDRESS"])
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
            str(self.email_settings["EMAIL_HOST"]),
            int(self.email_settings["EMAIL_PORT"]),
        ) as smtp:
            smtp.login(sender, str(self.email_settings["EMAIL_PASSWORD"]))
            return smtp.send_message(msg)


class SendGridEmailStrategy(EmailStrategy):
    def __init__(self) -> None:
        load_project_env()
        self.api_key = os.environ.get("SENDGRID_API_KEY")

    def send(
        self,
        *,
        subject: str,
        content: str,
        to_email: str | None = None,
        html_content: str | None = None,
        inline_assets: list[InlineAsset] | None = None,
    ) -> Any:
        raise NotImplementedError(
            "EMAIL_PROVIDER=sendgrid is configured, but SendGrid delivery is not implemented yet."
        )


def get_email_provider() -> str:
    load_project_env()
    return (os.environ.get("EMAIL_PROVIDER") or "smtp").strip().lower()


def email_strategy_factory() -> EmailStrategy:
    provider = get_email_provider()
    if provider == "smtp":
        return SMTPEmailStrategy()
    if provider == "sendgrid":
        return SendGridEmailStrategy()
    raise ConfigurationError(
        f"Unsupported EMAIL_PROVIDER '{provider}'. Supported providers: smtp, sendgrid."
    )
