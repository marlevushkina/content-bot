"""Telegram message formatting utilities."""

import re
from collections.abc import Callable
from typing import Any


def format_process_report(report: dict) -> str:
    """Format processor result for Telegram."""
    if "error" in report:
        return f"<b>Error:</b> {report['error']}"
    return report.get("report", "No report generated")


def sanitize_telegram_html(text: str) -> str:
    """Remove unsupported HTML tags, keep only Telegram-allowed ones."""
    allowed = {"b", "i", "code", "s", "u", "pre", "a"}
    # Remove all tags except allowed
    def replace_tag(m):
        tag = m.group(1).split()[0].lower().strip("/")
        if tag in allowed:
            return m.group(0)
        return ""
    return re.sub(r"<(/?\w[^>]*)>", replace_tag, text)


def _balance_html_tags(text: str) -> str:
    """Close unclosed HTML tags and remove orphan closing tags."""
    simple_tags = ["b", "i", "code", "s", "u", "pre"]
    open_stack: list[str] = []

    for m in re.finditer(r"<(/?)(\w+)[^>]*>", text):
        is_close = m.group(1) == "/"
        tag = m.group(2).lower()
        if tag not in simple_tags:
            continue
        if is_close:
            if open_stack and open_stack[-1] == tag:
                open_stack.pop()
        else:
            open_stack.append(tag)

    # Close unclosed tags in reverse order
    for tag in reversed(open_stack):
        text += f"</{tag}>"

    return text


def split_html_report(text: str, max_len: int = 4000) -> list[str]:
    """Split long HTML report into Telegram-safe chunks.

    Splits by Seed markers first, then by paragraphs.
    Balances HTML tags in each chunk.
    """
    # Strip tags Telegram doesn't allow (LLM occasionally emits <p>, <h2>, <div>)
    # so we don't fall back to raw-tag plaintext on a parse error.
    text = sanitize_telegram_html(text)

    if len(text) <= max_len:
        return [_balance_html_tags(text)]

    # Strategy 1: Split by Seed markers
    seed_pattern = re.compile(r"(?=<b>Seed #|\*\*Seed #)")
    parts = seed_pattern.split(text)

    if len(parts) > 1:
        chunks = []
        current = ""
        for part in parts:
            if len(current) + len(part) > max_len:
                if current:
                    chunks.append(_balance_html_tags(current.strip()))
                current = part
            else:
                current += part
        if current:
            chunks.append(_balance_html_tags(current.strip()))
        if chunks:
            return chunks

    # Strategy 2: Split by double newlines
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > max_len:
            if current:
                chunks.append(_balance_html_tags(current.strip()))
            current = para
        else:
            current = current + "\n\n" + para if current else para
    if current:
        chunks.append(_balance_html_tags(current.strip()))

    return chunks if chunks else [text[:max_len]]


async def send_report(
    answer_target: Any,
    formatted: str,
    *,
    status_msg: Any = None,
    store: Callable[[int, str], None] | None = None,
    keyboard_last: Any = None,
) -> None:
    """Send a (possibly long) HTML report, splitting and degrading gracefully.

    - ``status_msg``: if given, the first chunk edits this message instead of
      sending a new one (used to replace a "Generating..." placeholder).
    - ``store``: optional callback ``(message_id, formatted)`` to remember the
      sent message (e.g. for reply-to-edit context).
    - ``keyboard_last``: inline keyboard attached to the final chunk only.
    - Falls back to ``parse_mode=None`` if Telegram rejects the HTML.
    """
    parts = split_html_report(formatted)

    for i, part in enumerate(parts):
        keyboard = keyboard_last if i == len(parts) - 1 else None

        if i == 0 and status_msg is not None:
            try:
                await status_msg.edit_text(part, reply_markup=keyboard)
            except Exception:
                await status_msg.edit_text(part, parse_mode=None, reply_markup=keyboard)
            sent = status_msg
        else:
            try:
                sent = await answer_target.answer(part, reply_markup=keyboard)
            except Exception:
                sent = await answer_target.answer(
                    part, parse_mode=None, reply_markup=keyboard
                )

        if store is not None and sent is not None:
            store(sent.message_id, formatted)
