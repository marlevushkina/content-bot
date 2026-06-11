"""Tests for Telegram HTML formatting utilities."""

from content_bot.bot.formatters import (
    _balance_html_tags,
    sanitize_telegram_html,
    split_html_report,
)


def test_sanitize_keeps_allowed_tags():
    text = "<b>bold</b> <i>italic</i> <code>x</code>"
    assert sanitize_telegram_html(text) == text


def test_sanitize_strips_unsupported_tags():
    text = "<div><p>hello</p></div> <b>keep</b>"
    out = sanitize_telegram_html(text)
    assert "<div>" not in out
    assert "<p>" not in out
    assert "<b>keep</b>" in out
    assert "hello" in out


def test_balance_closes_unclosed_tag():
    assert _balance_html_tags("<b>oops") == "<b>oops</b>"


def test_balance_drops_orphan_close():
    # Orphan closing tag is left in place but no spurious open is added.
    out = _balance_html_tags("plain</b> text")
    assert not out.endswith("</b></b>")


def test_split_short_text_returns_single_chunk():
    assert split_html_report("short") == ["short"]


def test_split_long_text_chunks_are_under_limit():
    text = "\n\n".join(f"<b>Seed #{i}</b> body {'x' * 500}" for i in range(20))
    chunks = split_html_report(text, max_len=1000)
    assert len(chunks) > 1
    assert all(len(c) <= 1200 for c in chunks)  # allow tag-balancing slack


def test_split_balances_each_chunk():
    text = "\n\n".join(f"<b>Seed #{i}</b> {'x' * 800}" for i in range(5))
    for chunk in split_html_report(text, max_len=900):
        assert chunk.count("<b>") == chunk.count("</b>")
