"""Claude processing service for content generation."""

import json
import logging
import os
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 1200  # 20 minutes


class ContentProcessor:
    """Service for generating content seeds and plans via Claude Code."""

    def __init__(self, vault_path: Path) -> None:
        self.vault_path = Path(vault_path)

    def _build_subprocess_env(self) -> dict[str, str]:
        """Build environment for Claude subprocess."""
        env = os.environ.copy()
        path = env.get("PATH", "/usr/bin:/bin")
        for extra in ["/usr/local/bin", os.path.expanduser("~/.local/bin")]:
            if extra not in path:
                path = f"{extra}:{path}"
        env["PATH"] = path
        if "HOME" not in env:
            env["HOME"] = os.path.expanduser("~")
        return env

    def _html_to_markdown(self, html: str) -> str:
        """Convert Telegram HTML to Markdown."""
        text = html
        text = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
        text = re.sub(r"<i>(.*?)</i>", r"*\1*", text)
        text = re.sub(r"<code>(.*?)</code>", r"`\1`", text)
        text = re.sub(r"<s>(.*?)</s>", r"~~\1~~", text)
        text = re.sub(r"</?u>", "", text)
        text = re.sub(r'<a href="([^"]+)">([^<]+)</a>', r"[\2](\1)", text)
        return text

    def _markdown_to_html(self, md: str) -> str:
        """Convert Markdown back to Telegram HTML."""
        text = md
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)
        text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
        return text

    # --- Content Seeds ---

    def _load_content_seeds_skill(self) -> str:
        """Load content-seeds skill content."""
        skill_path = self.vault_path / ".claude/skills/content-seeds/SKILL.md"
        if skill_path.exists():
            return skill_path.read_text()
        return ""

    def _load_tone_of_voice(self) -> str:
        """Load tone of voice reference."""
        ref_path = self.vault_path / ".claude/skills/content-seeds/references/tone-of-voice.md"
        if ref_path.exists():
            return ref_path.read_text()
        return ""

    def _load_strategy(self) -> str:
        """Load content strategy reference."""
        ref_path = self.vault_path / ".claude/skills/content-seeds/references/strategy.md"
        if ref_path.exists():
            return ref_path.read_text()
        return ""

    def _load_icp(self) -> str:
        """Load ICP & positioning reference."""
        ref_path = self.vault_path / ".claude/skills/content-seeds/references/icp.md"
        if ref_path.exists():
            return ref_path.read_text()
        return ""

    def _load_tone_examples(self) -> str:
        """Load tone of voice examples from real channel posts."""
        ref_path = self.vault_path / ".claude/skills/content-seeds/references/tone-examples.md"
        if ref_path.exists():
            return ref_path.read_text()
        return ""

    def _summarize_meeting(self, name: str, text: str, cache_dir: Path | None = None) -> str:
        """Summarize a long meeting transcript via Claude."""
        if cache_dir:
            cache_file = cache_dir / f"{name}.summary.md"
            if cache_file.exists():
                cached = cache_file.read_text()
                if cached.strip():
                    logger.info("Using cached summary for %s", name)
                    return f"[SUMMARY]\n{cached}"

        prompt = (
            "You are a meeting summarizer. Extract ALL key ideas, decisions, insights, "
            "interesting thoughts and quotes. Don't skip anything important.\n\n"
            "Format: concise bullet points, up to 2000 words. "
            "Write in the same language as the transcript.\n\n"
            f"=== TRANSCRIPT: {name} ===\n{text}"
        )
        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=prompt,
                cwd=self.vault_path.parent,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                summary = result.stdout.strip()
                logger.info("Summarized meeting %s: %d -> %d chars", name, len(text), len(summary))
                if cache_dir:
                    try:
                        cache_file = cache_dir / f"{name}.summary.md"
                        cache_file.write_text(summary)
                    except Exception as e:
                        logger.warning("Failed to cache summary for %s: %s", name, e)
                return f"[SUMMARY]\n{summary}"
        except Exception as e:
            logger.warning("Failed to summarize meeting %s: %s", name, e)
        return text

    def _collect_raw_material(self, days: int = 7) -> str:
        """Collect raw material from vault for content seed generation."""
        today = date.today()
        parts: list[str] = []

        # Collect daily files
        daily_dir = self.vault_path / "daily"
        if daily_dir.exists():
            for i in range(days):
                day = today - timedelta(days=i)
                daily_file = daily_dir / f"{day.isoformat()}.md"
                if daily_file.exists():
                    content = daily_file.read_text()
                    if content.strip():
                        parts.append(f"=== DAILY {day.isoformat()} ===\n{content}")

        # Collect meeting transcripts
        meetings_dir = self.vault_path / "content" / "meetings"
        if meetings_dir.exists():
            cutoff = today - timedelta(days=days)
            for md_file in sorted(meetings_dir.glob("*.md"), reverse=True):
                if md_file.name.endswith(".summary.md"):
                    continue
                try:
                    file_date = date.fromisoformat(md_file.name[:10])
                    if file_date >= cutoff:
                        content = md_file.read_text()
                        if content.strip():
                            if len(content) > 5000:
                                content = self._summarize_meeting(
                                    md_file.stem, content, cache_dir=meetings_dir,
                                )
                            parts.append(
                                f"=== MEETING {md_file.stem} ===\n{content}"
                            )
                except ValueError:
                    continue

        # Collect thoughts
        thoughts_dir = self.vault_path / "thoughts"
        if thoughts_dir.exists():
            cutoff = today - timedelta(days=days)
            for md_file in sorted(thoughts_dir.glob("*.md"), reverse=True):
                try:
                    file_date = date.fromisoformat(md_file.name[:10])
                    if file_date >= cutoff:
                        content = md_file.read_text()
                        if content.strip():
                            parts.append(
                                f"=== THOUGHT {md_file.stem} ===\n{content}"
                            )
                except ValueError:
                    continue

        if not parts:
            return ""

        return "\n\n".join(parts)

    def _save_content_seeds(self, html: str, seeds_date: date) -> Path:
        """Save content seeds to vault/content/seeds/YYYY-WXX-seeds.md."""
        year, week, _ = seeds_date.isocalendar()
        filename = f"{year}-W{week:02d}-seeds.md"
        seeds_dir = self.vault_path / "content" / "seeds"
        seeds_dir.mkdir(parents=True, exist_ok=True)
        seeds_path = seeds_dir / filename

        content = self._html_to_markdown(html)
        frontmatter = f"""---
date: {seeds_date.isoformat()}
type: content-seeds
week: {year}-W{week:02d}
---

"""
        seeds_path.write_text(frontmatter + content)
        logger.info("Content seeds saved to %s", seeds_path)
        return seeds_path

    def generate_content_seeds(self) -> dict[str, Any]:
        """Generate content seeds from weekly raw material."""
        today = date.today()

        skill_content = self._load_content_seeds_skill()
        tone_of_voice = self._load_tone_of_voice()
        strategy = self._load_strategy()
        icp = self._load_icp()
        tone_examples = self._load_tone_examples()

        raw_material = self._collect_raw_material(days=7)
        if not raw_material:
            return {
                "error": "No entries for the last 7 days to generate seeds from",
                "processed_entries": 0,
            }

        references = ""
        if tone_of_voice:
            references += f"\n=== TONE OF VOICE ===\n{tone_of_voice}\n=== END TONE OF VOICE ===\n"
        if strategy:
            references += f"\n=== CONTENT STRATEGY ===\n{strategy}\n=== END STRATEGY ===\n"
        if icp:
            references += f"\n=== ICP & POSITIONING ===\n{icp}\n=== END ICP ===\n"
        if tone_examples:
            references += f"\n=== TONE OF VOICE EXAMPLES ===\n{tone_examples}\n=== END TONE EXAMPLES ===\n"

        prompt = f"""Today is {today}. Generate content seeds from raw material.

=== SKILL INSTRUCTIONS ===
{skill_content}
=== END SKILL ===
{references}
=== RAW MATERIAL (last 7 days) ===
{raw_material}
=== END RAW MATERIAL ===

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Follow the output format from SKILL INSTRUCTIONS exactly

CRITICAL RULES:
- Each seed must have a clear hook and key insight
- Write like a real person, not like AI
- Apply ALL tone of voice rules"""

        try:
            env = self._build_subprocess_env()

            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=prompt,
                cwd=self.vault_path.parent,
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT,
                check=False,
                env=env,
            )

            if result.returncode != 0:
                logger.error("Content seeds generation failed: %s", result.stderr)
                return {
                    "error": result.stderr or "Content seeds generation failed",
                    "processed_entries": 0,
                }

            output = result.stdout.strip()

            try:
                self._save_content_seeds(output, today)
            except Exception as e:
                logger.warning("Failed to save content seeds: %s", e)

            return {"report": output, "processed_entries": 1}

        except subprocess.TimeoutExpired:
            return {"error": "Content seeds generation timed out", "processed_entries": 0}
        except FileNotFoundError:
            return {"error": "Claude CLI not installed", "processed_entries": 0}
        except Exception as e:
            logger.exception("Unexpected error during content seeds generation")
            return {"error": str(e), "processed_entries": 0}

    # --- Content Plan ---

    def _load_all_seeds(self, max_weeks: int = 8) -> str:
        """Load accumulated content seeds from recent weeks."""
        seeds_dir = self.vault_path / "content" / "seeds"
        if not seeds_dir.exists():
            return ""
        seed_files = sorted(seeds_dir.glob("*.md"), reverse=True)[:max_weeks]
        if not seed_files:
            return ""
        parts = []
        for f in seed_files:
            parts.append(f"=== {f.stem} ===\n{f.read_text()}")
        return "\n\n".join(parts)

    def _load_content_planner_skill(self) -> str:
        """Load content-planner skill content."""
        skill_path = self.vault_path / ".claude/skills/content-planner/SKILL.md"
        if skill_path.exists():
            return skill_path.read_text()
        return ""

    def _load_monthly_goals(self) -> str:
        """Load current monthly goals for content alignment."""
        goals_path = self.vault_path / "goals" / "2-monthly.md"
        if goals_path.exists():
            return goals_path.read_text()
        return ""

    def _save_content_plan(self, html: str, plan_date: date) -> Path:
        """Save content plan to vault/content/plans/YYYY-WXX-plan.md."""
        year, week, _ = plan_date.isocalendar()
        filename = f"{year}-W{week:02d}-plan.md"
        plans_dir = self.vault_path / "content" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plans_dir / filename

        content = self._html_to_markdown(html)
        frontmatter = f"""---
date: {plan_date.isoformat()}
type: content-plan
week: {year}-W{week:02d}
---

"""
        plan_path.write_text(frontmatter + content)
        logger.info("Content plan saved to %s", plan_path)
        return plan_path

    def generate_content_plan(
        self, channel_posts: str = "", target_date: date | None = None,
    ) -> dict[str, Any]:
        """Generate weekly content plan from seeds and channel history."""
        today = target_date or date.today()

        skill_content = self._load_content_planner_skill()
        tone_of_voice = self._load_tone_of_voice()
        strategy = self._load_strategy()
        icp = self._load_icp()
        seeds_content = self._load_all_seeds()
        monthly_goals = self._load_monthly_goals()

        if not seeds_content:
            return {
                "error": "No content seeds found. Run /content first",
                "processed_entries": 0,
            }

        context_parts = []
        if channel_posts:
            context_parts.append(
                f"=== RECENT CHANNEL POSTS ===\n{channel_posts}\n=== END CHANNEL POSTS ==="
            )
        if monthly_goals:
            context_parts.append(
                f"=== MONTHLY GOALS ===\n{monthly_goals}\n=== END MONTHLY GOALS ==="
            )
        extra_context = "\n\n".join(context_parts)

        references = ""
        if tone_of_voice:
            references += f"\n=== TONE OF VOICE ===\n{tone_of_voice}\n=== END TONE OF VOICE ===\n"
        if strategy:
            references += f"\n=== CONTENT STRATEGY ===\n{strategy}\n=== END STRATEGY ===\n"
        if icp:
            references += f"\n=== ICP & POSITIONING ===\n{icp}\n=== END ICP ===\n"

        prompt = f"""Today is {today}. Create a weekly content plan.

=== SKILL INSTRUCTIONS ===
{skill_content}
=== END SKILL ===
{references}
=== CONTENT SEEDS ===
{seeds_content}
=== END CONTENT SEEDS ===

{extra_context}

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Follow the output format from SKILL INSTRUCTIONS exactly"""

        try:
            env = self._build_subprocess_env()

            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=prompt,
                cwd=self.vault_path.parent,
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT,
                check=False,
                env=env,
            )

            if result.returncode != 0:
                return {
                    "error": result.stderr or "Content plan generation failed",
                    "processed_entries": 0,
                }

            output = result.stdout.strip()

            try:
                self._save_content_plan(output, today)
            except Exception as e:
                logger.warning("Failed to save content plan: %s", e)

            return {"report": output, "processed_entries": 1}

        except subprocess.TimeoutExpired:
            return {"error": "Content plan generation timed out", "processed_entries": 0}
        except FileNotFoundError:
            return {"error": "Claude CLI not installed", "processed_entries": 0}
        except Exception as e:
            logger.exception("Unexpected error during content plan generation")
            return {"error": str(e), "processed_entries": 0}

    # --- Seed & Plan viewing ---

    def _extract_seed_titles(self) -> list[dict]:
        """Extract seed titles from all seed files."""
        seeds_dir = self.vault_path / "content" / "seeds"
        if not seeds_dir.exists():
            return []

        seed_files = sorted(seeds_dir.glob("*.md"), reverse=True)[:8]
        results: list[dict] = []

        for f in seed_files:
            if f.name == ".gitkeep":
                continue
            content = f.read_text()
            week = ""
            week_match = re.search(r"week:\s*(\S+)", content)
            if week_match:
                week = week_match.group(1)
            else:
                fname_match = re.match(r"(\d{4}-W\d{2})", f.name)
                if fname_match:
                    week = fname_match.group(1)

            body = content
            if body.startswith("---"):
                end = body.find("---", 3)
                if end != -1:
                    body = body[end + 3:].strip()

            seed_pattern = re.compile(
                r"\*{0,2}Seed\s*#(\d+)[:\s]+(.+?)\*{0,2}\s*$", re.MULTILINE,
            )
            seed_starts = list(seed_pattern.finditer(body))
            for i, m in enumerate(seed_starts):
                num = int(m.group(1))
                title = m.group(2).strip().rstrip("*")
                start = m.start()
                end_pos = seed_starts[i + 1].start() if i + 1 < len(seed_starts) else len(body)
                full_text = body[start:end_pos].strip()
                results.append({
                    "week": week,
                    "num": num,
                    "title": title,
                    "full_text": full_text,
                })

        return results

    def get_current_plan(self, week_offset: int = 0) -> dict[str, Any]:
        """Read plan file for current (or offset) week."""
        target = date.today() + timedelta(weeks=week_offset)
        year, week, _ = target.isocalendar()
        week_id = f"{year}-W{week:02d}"
        filename = f"{week_id}-plan.md"
        plan_path = self.vault_path / "content" / "plans" / filename

        if not plan_path.exists():
            return {"error": f"Plan for {week_id} not found"}

        content = plan_path.read_text()
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()

        return {"plan": content, "week": week_id, "path": str(plan_path)}

    def plan_exists_for_week(self, week_offset: int = 0) -> bool:
        """Check if a plan file exists for the given week."""
        target = date.today() + timedelta(weeks=week_offset)
        year, week, _ = target.isocalendar()
        filename = f"{year}-W{week:02d}-plan.md"
        return (self.vault_path / "content" / "plans" / filename).exists()

    # --- Dismissed seeds ---

    @property
    def _dismissed_path(self) -> Path:
        return self.vault_path / "content" / "seeds" / ".dismissed.json"

    def _load_dismissed(self) -> set[str]:
        """Load set of dismissed seed keys like '2026-W07:3'."""
        if not self._dismissed_path.exists():
            return set()
        try:
            data = json.loads(self._dismissed_path.read_text())
            return set(data.get("dismissed", []))
        except Exception:
            return set()

    def _save_dismissed(self, dismissed: set[str]) -> None:
        """Save dismissed seed keys."""
        self._dismissed_path.parent.mkdir(parents=True, exist_ok=True)
        self._dismissed_path.write_text(
            json.dumps({"dismissed": sorted(dismissed)}, ensure_ascii=False, indent=2),
        )

    def dismiss_seeds(self, seeds_to_dismiss: list[dict]) -> int:
        """Mark seeds as dismissed. Returns count of newly dismissed."""
        dismissed = self._load_dismissed()
        count = 0
        for s in seeds_to_dismiss:
            key = f"{s['week']}:{s['num']}"
            if key not in dismissed:
                dismissed.add(key)
                count += 1
        self._save_dismissed(dismissed)
        return count

    def list_unpublished_seeds(self, channel_posts: str) -> dict[str, Any]:
        """List all seeds, marking which have been published."""
        all_seeds = self._extract_seed_titles()
        if not all_seeds:
            return {"error": "No seeds found. Run /content to generate."}

        dismissed = self._load_dismissed()
        active_seeds = [
            s for s in all_seeds
            if f"{s['week']}:{s['num']}" not in dismissed
        ]
        dismissed_count = len(all_seeds) - len(active_seeds)

        if not active_seeds:
            return {"error": "All seeds dismissed or published. Run /content for new ones."}

        titles_text = "\n".join(
            f"{i + 1}. [{s['week']}] Seed #{s['num']}: {s['title']}"
            for i, s in enumerate(active_seeds)
        )

        prompt = f"""You determine which content seeds have already been published in a TG channel.

MATCHING RULES (STRICT):
- A seed is published ONLY if the channel has a post that EXPLICITLY covers the SAME specific story or case
- Thematic similarity does NOT count
- If in doubt — seed is NOT published
- Most seeds are likely NOT published — that's normal

=== SEED LIST ===
{titles_text}
=== END SEEDS ===

=== CHANNEL POSTS ===
{channel_posts}
=== END POSTS ===

Return ONLY the numbers of published seeds separated by commas (example: 1,3,7).
If none are published, return the word "none".
Write nothing else."""

        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=prompt,
                cwd=self.vault_path.parent,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )

            published_indices: set[int] = set()
            if result.returncode == 0 and result.stdout.strip().lower() != "none":
                numbers = re.findall(r"\d+", result.stdout.strip())
                published_indices = {int(n) for n in numbers if 1 <= int(n) <= len(active_seeds)}

            unpublished = []
            for i, s in enumerate(active_seeds):
                s["published"] = (i + 1) in published_indices
                if not s["published"]:
                    unpublished.append(s)

            return {
                "seeds": active_seeds,
                "unpublished": unpublished,
                "total": len(all_seeds),
                "published_count": len(published_indices),
                "dismissed_count": dismissed_count,
            }

        except Exception as e:
            logger.warning("Failed to match seeds with channel: %s", e)
            return {
                "seeds": active_seeds,
                "unpublished": active_seeds,
                "total": len(all_seeds),
                "published_count": 0,
                "dismissed_count": dismissed_count,
            }

    def reconcile_plan_with_channel(self, channel_posts: str) -> dict[str, Any]:
        """Compare plan with published posts, suggest adjustments."""
        plan_data = self.get_current_plan()
        if "error" in plan_data:
            return plan_data

        tone_of_voice = self._load_tone_of_voice()
        strategy = self._load_strategy()

        prompt = f"""Compare the content plan with published channel posts.

=== CONTENT PLAN ({plan_data['week']}) ===
{plan_data['plan']}
=== END PLAN ===

=== CHANNEL POSTS ===
{channel_posts}
=== END POSTS ===

=== TONE OF VOICE ===
{tone_of_voice}
=== END TONE OF VOICE ===

=== CONTENT STRATEGY ===
{strategy}
=== END STRATEGY ===

TASK:
1. Identify which posts from the plan are already published — mark them with checkmark
2. For unpublished — keep as is or adjust if needed
3. Return the full updated plan

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown
- Allowed tags: <b>, <i>, <code>, <s>, <u>"""

        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=prompt,
                cwd=self.vault_path.parent,
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT,
                check=False,
            )

            if result.returncode != 0:
                return {
                    "error": result.stderr or "Reconciliation failed",
                    "processed_entries": 0,
                }

            output = result.stdout.strip()

            try:
                self._save_content_plan(output, date.today())
            except Exception as e:
                logger.warning("Failed to save reconciled plan: %s", e)

            return {"report": output, "processed_entries": 1}

        except subprocess.TimeoutExpired:
            return {"error": "Reconciliation timed out", "processed_entries": 0}
        except Exception as e:
            logger.exception("Unexpected error during reconciliation")
            return {"error": str(e), "processed_entries": 0}

    def edit_plan(self, user_request: str) -> dict[str, Any]:
        """Edit current plan based on user request."""
        plan_data = self.get_current_plan()
        if "error" in plan_data:
            return plan_data

        seeds_content = self._load_all_seeds(max_weeks=4)
        tone_of_voice = self._load_tone_of_voice()
        strategy = self._load_strategy()
        icp = self._load_icp()

        references = ""
        if tone_of_voice:
            references += f"\n=== TONE OF VOICE ===\n{tone_of_voice}\n=== END TONE OF VOICE ===\n"
        if strategy:
            references += f"\n=== CONTENT STRATEGY ===\n{strategy}\n=== END STRATEGY ===\n"
        if icp:
            references += f"\n=== ICP & POSITIONING ===\n{icp}\n=== END ICP ===\n"

        prompt = f"""Edit the content plan based on user request.

=== CURRENT PLAN ({plan_data['week']}) ===
{plan_data['plan']}
=== END PLAN ===

=== AVAILABLE SEEDS ===
{seeds_content}
=== END SEEDS ===
{references}
USER REQUEST: {user_request}

TASK:
- Apply the requested changes
- Keep the overall plan structure
- Use seeds from the list if needed

CRITICAL OUTPUT FORMAT:
- Return the FULL updated plan in raw HTML for Telegram
- NO markdown
- Allowed tags: <b>, <i>, <code>, <s>, <u>"""

        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions"],
                input=prompt,
                cwd=self.vault_path.parent,
                capture_output=True,
                text=True,
                timeout=DEFAULT_TIMEOUT,
                check=False,
            )

            if result.returncode != 0:
                return {
                    "error": result.stderr or "Plan edit failed",
                    "processed_entries": 0,
                }

            output = result.stdout.strip()

            try:
                self._save_content_plan(output, date.today())
            except Exception as e:
                logger.warning("Failed to save edited plan: %s", e)

            return {"report": output, "processed_entries": 1}

        except subprocess.TimeoutExpired:
            return {"error": "Plan edit timed out", "processed_entries": 0}
        except Exception as e:
            logger.exception("Unexpected error during plan edit")
            return {"error": str(e), "processed_entries": 0}
