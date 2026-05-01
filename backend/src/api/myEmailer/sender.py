from typing import Any

from api.myEmailer.strategy import InlineAsset, email_strategy_factory


def send_mail(
    subject: str = "No subject provided",
    content: str = "No message provided",
    to_email: str | None = None,
    html_content: str | None = None,
    inline_assets: list[InlineAsset] | None = None,
) -> Any:
    strategy = email_strategy_factory()
    return strategy.send(
        subject=subject,
        content=content,
        to_email=to_email,
        html_content=html_content,
        inline_assets=inline_assets,
    )
