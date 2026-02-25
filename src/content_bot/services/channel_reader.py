"""Telegram channel reader service via public web page."""

import logging
import re
from datetime import date
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

TG_CHANNEL_URL = "https://t.me/s/{channel}"


class ChannelReader:
    """Reads posts from a public Telegram channel via t.me/s/ web page."""

    def __init__(self, channel: str, vault_path: Path) -> None:
        self.channel = channel
        self.vault_path = Path(vault_path)

    async def get_recent_posts(self, limit: int = 50) -> list[dict]:
        """Fetch recent posts from the channel web page."""
        url = TG_CHANNEL_URL.format(channel=self.channel)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        html = resp.text
        return self._parse_posts(html, limit)

    def _parse_posts(self, html: str, limit: int) -> list[dict]:
        """Parse posts from Telegram channel web page HTML."""
        post_ids = re.findall(
            rf'data-post="{re.escape(self.channel)}/(\d+)"', html
        )

        raw_texts = re.findall(
            r'class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            html,
            re.DOTALL,
        )

        raw_views = re.findall(
            r'class="tgme_widget_message_views">([^<]+)<', html
        )

        raw_dates = re.findall(r'datetime="([^"]+)"', html)

        posts: list[dict] = []
        count = min(len(post_ids), len(raw_texts))

        for i in range(count):
            clean_text = re.sub(r"<br\s*/?>", "\n", raw_texts[i])
            clean_text = re.sub(r"<[^>]+>", "", clean_text).strip()

            if not clean_text:
                continue

            views = 0
            if i < len(raw_views):
                views = self._parse_views(raw_views[i].strip())

            post_date = ""
            if i < len(raw_dates):
                post_date = raw_dates[i][:10]

            posts.append({
                "id": int(post_ids[i]),
                "date": post_date,
                "text": clean_text,
                "views": views,
            })

        posts.reverse()
        posts = posts[:limit]

        logger.info("Fetched %d posts from @%s", len(posts), self.channel)
        return posts

    @staticmethod
    def _parse_views(views_str: str) -> int:
        """Parse view count string like '1.2K' into int."""
        views_str = views_str.strip().upper()
        if views_str.endswith("K"):
            return int(float(views_str[:-1]) * 1000)
        if views_str.endswith("M"):
            return int(float(views_str[:-1]) * 1_000_000)
        try:
            return int(views_str)
        except ValueError:
            return 0

    def format_for_prompt(self, posts: list[dict], limit: int = 20) -> str:
        """Format posts for inclusion in Claude prompt."""
        if not posts:
            return ""

        lines = []
        for post in posts[:limit]:
            lines.extend([
                f"--- POST [{post['date']}] (views: {post['views']}) ---",
                post["text"],
                "",
            ])

        return "\n".join(lines)

    async def generate_tone_examples(self, limit: int = 50) -> Path:
        """Fetch posts and save best ones as tone-of-voice examples."""
        posts = await self.get_recent_posts(limit=limit)
        if not posts:
            raise ValueError(f"No posts found in @{self.channel}")

        sorted_posts = sorted(posts, key=lambda p: p["views"], reverse=True)
        top_posts = sorted_posts[:15]
        top_posts.sort(key=lambda p: p["date"])

        today = date.today().isoformat()
        lines = [
            "# Tone of Voice - examples from channel",
            "",
            f"Auto-collected {today} from @{self.channel}.",
            "Claude should study the tone, rhythm, structure and write seeds in this style.",
            "",
            "---",
            "",
        ]

        for i, post in enumerate(top_posts, 1):
            lines.extend([
                f"### Example {i}",
                f"**Date:** {post['date']} | **Views:** {post['views']}",
                "",
                post["text"],
                "",
                "---",
                "",
            ])

        ref_path = (
            self.vault_path
            / ".claude/skills/content-seeds/references/tone-examples.md"
        )
        ref_path.write_text("\n".join(lines))
        logger.info("Tone examples saved to %s (%d posts)", ref_path, len(top_posts))
        return ref_path
