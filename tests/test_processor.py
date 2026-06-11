"""Tests for pure helpers in the content processor and channel reader."""

from content_bot.services.channel_reader import ChannelReader
from content_bot.services.processor import ContentProcessor


def test_html_to_markdown_basic():
    html = "<b>bold</b> <i>it</i> <code>c</code> <s>s</s>"
    md = ContentProcessor._html_to_markdown(html)
    assert md == "**bold** *it* `c` ~~s~~"


def test_markdown_to_html_basic():
    md = "**bold** *it* `c` ~~s~~"
    html = ContentProcessor._markdown_to_html(md)
    assert "<b>bold</b>" in html
    assert "<i>it</i>" in html
    assert "<code>c</code>" in html
    assert "<s>s</s>" in html


def test_markdown_to_html_converts_links():
    md = "see [docs](https://example.com/x)"
    html = ContentProcessor._markdown_to_html(md)
    assert '<a href="https://example.com/x">docs</a>' in html


def test_html_link_roundtrip():
    html = '<a href="https://e.com">label</a>'
    md = ContentProcessor._html_to_markdown(html)
    assert md == "[label](https://e.com)"
    assert ContentProcessor._markdown_to_html(md) == html


def test_parse_views_thousands():
    assert ChannelReader._parse_views("1.2K") == 1200
    assert ChannelReader._parse_views("3M") == 3_000_000
    assert ChannelReader._parse_views("950") == 950
    assert ChannelReader._parse_views("garbage") == 0
