"""Shared sensor helpers."""

import html
import re


def clean_html(text: str) -> str:
    """Remove HTML tags and normalize paragraph spacing."""
    text = html.unescape(text).replace("\xa0", " ")
    text = re.sub(
        r"<br\s*/?>|</p\s*>\s*<p\b[^>]*>",
        "\n",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()
