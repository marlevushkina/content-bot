"""Report formatters for Telegram messages."""

import html
import re
from typing import Any

ALLOWED_TAGS = {"b", "i", "code", "pre", "a", "s", "u"}


def sanitize_telegram_html(text: str) -> str:
    """Sanitize HTML for Telegram, keeping only allowed tags."""
    if not text:
        return ""

    result = []
    i = 0
    while i < len(text):
        if text[i] == "<":
            tag_match = re.match(r"</?([a-zA-Z]+)(?:\s[^>]*)?>", text[i:])
            if tag_match:
                tag_name = tag_match.group(1).lower()
                if tag_name in ALLOWED_TAGS:
                    result.append(tag_match.group(0))
                    i += len(tag_match.group(0))
                    continue
                else:
                    result.append("&lt;")
                    i += 1
                    continue
            else:
                result.append("&lt;")
                i += 1
                continue
        elif text[i] == ">":
            result.append("&gt;")
            i += 1
        elif text[i] == "&":
            entity_match = re.match(r"&(amp|lt|gt|quot|#\d+|#x[0-9a-fA-F]+);", text[i:])
            if entity_match:
                result.append(entity_match.group(0))
                i += len(entity_match.group(0))
            else:
                result.append("&amp;")
                i += 1
        else:
            result.append(text[i])
            i += 1

    return "".join(result)


def validate_telegram_html(text: str) -> bool:
    """Validate that HTML tags are properly closed."""
    tag_stack = []
    tag_pattern = re.compile(r"<(/?)([a-zA-Z]+)(?:\s[^>]*)?>")

    for match in tag_pattern.finditer(text):
        is_closing = match.group(1) == "/"
        tag_name = match.group(2).lower()

        if tag_name not in ALLOWED_TAGS:
            continue

        if is_closing:
            if not tag_stack or tag_stack[-1] != tag_name:
                return False
            tag_stack.pop()
        else:
            tag_stack.append(tag_name)

    return len(tag_stack) == 0


def truncate_html(text: str, max_length: int = 4096) -> str:
    """Truncate HTML text while keeping tags balanced."""
    if len(text) <= max_length:
        return text

    cut_point = max_length - 50

    last_open = text.rfind("<", 0, cut_point)
    last_close = text.rfind(">", 0, cut_point)

    if last_open > last_close:
        cut_point = last_open

    truncated = text[:cut_point]

    tag_pattern = re.compile(r"<(/?)([a-zA-Z]+)(?:\s[^>]*)?>")
    open_tags = []

    for match in tag_pattern.finditer(truncated):
        is_closing = match.group(1) == "/"
        tag_name = match.group(2).lower()

        if tag_name not in ALLOWED_TAGS:
            continue

        if is_closing and open_tags and open_tags[-1] == tag_name:
            open_tags.pop()
        elif not is_closing:
            open_tags.append(tag_name)

    closing_tags = "".join(f"</{tag}>" for tag in reversed(open_tags))

    return truncated + "..." + closing_tags


def format_process_report(report: dict[str, Any]) -> str:
    """Format processing report for Telegram HTML."""
    if "error" in report:
        error_msg = html.escape(str(report["error"]))
        return f"Error: <b>{error_msg}</b>"

    if "report" in report:
        raw_report = report["report"]
        sanitized = sanitize_telegram_html(raw_report)

        if not validate_telegram_html(sanitized):
            return html.escape(raw_report)

        return truncate_html(sanitized, max_length=4096)

    return "Done"


def split_html_report(text: str, max_length: int = 4000) -> list[str]:
    """Split long HTML report into parts by Seed boundaries."""
    if len(text) <= max_length:
        return [text]

    parts: list[str] = []
    chunks = re.split(r"(?=<b>Seed #)", text)

    current = ""
    for chunk in chunks:
        if not chunk:
            continue
        if len(current) + len(chunk) <= max_length:
            current += chunk
        else:
            if current:
                parts.append(current.strip())
            current = chunk

    if current:
        parts.append(current.strip())

    if not parts:
        return [truncate_html(text, max_length)]

    result: list[str] = []
    for part in parts:
        if len(part) <= max_length:
            result.append(part)
        else:
            result.append(truncate_html(part, max_length))

    return result
