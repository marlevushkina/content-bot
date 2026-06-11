"""Content processing service using Anthropic API directly."""

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 600  # 10 minutes for long generation tasks
SEEDS_MODEL = "claude-opus-4-8"
PLAN_MODEL = "claude-sonnet-4-6"
REFINE_MODEL = "claude-sonnet-4-6"
SUMMARIZE_MODEL = "claude-sonnet-4-6"


class ContentProcessor:
    """Handles all content generation: seeds, plans, post writing."""

    def __init__(
        self,
        vault_path: Path,
        api_key: str,
        author_name: str = "",
        channel: str = "",
    ) -> None:
        self.vault_path = vault_path
        self.client = anthropic.Anthropic(api_key=api_key, timeout=DEFAULT_TIMEOUT)
        # Persona/channel are injected into prompts as light framing; the actual
        # voice and strategy live in the vault skills.
        self.author = author_name.strip() or "автора"
        self.channel_label = f"@{channel.strip()}" if channel.strip() else "канала"

    # ─── LLM CALL ───────────────────────────────────────────────────────

    def _call_llm(
        self,
        prompt: str,
        model: str = SEEDS_MODEL,
        max_tokens: int = 8192,
        system: str | list[str] | None = None,
    ) -> str:
        """Call Anthropic API and return text response.

        Static context (skills, tone, strategy) should be passed via ``system``:
        the prefix is marked with ``cache_control`` so repeat calls in a session
        reuse it at a fraction of the cost and latency.
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            blocks = [system] if isinstance(system, str) else [b for b in system if b]
            if blocks:
                system_param: list[dict[str, Any]] = [
                    {"type": "text", "text": b} for b in blocks
                ]
                # Cache the static prefix (ignored automatically if under the
                # model's minimum cacheable token count).
                system_param[-1]["cache_control"] = {"type": "ephemeral"}
                kwargs["system"] = system_param

        message = self.client.messages.create(**kwargs)

        if message.stop_reason == "max_tokens":
            logger.warning(
                "LLM response truncated at max_tokens=%d (model=%s) — output may be incomplete",
                max_tokens,
                model,
            )

        if not message.content:
            logger.warning("LLM returned empty content (model=%s)", model)
            return ""
        return message.content[0].text

    # ─── HTML/MARKDOWN CONVERSION ────────────────────────────────────────

    @staticmethod
    def _html_to_markdown(html: str) -> str:
        """Convert Telegram HTML to Obsidian Markdown."""
        text = html
        text = re.sub(r"<b>(.*?)</b>", r"**\1**", text)
        text = re.sub(r"<i>(.*?)</i>", r"*\1*", text)
        text = re.sub(r"<code>(.*?)</code>", r"`\1`", text)
        text = re.sub(r"<s>(.*?)</s>", r"~~\1~~", text)
        text = re.sub(r"</?u>", "", text)
        text = re.sub(r'<a href="([^"]+)">([^<]+)</a>', r"[\2](\1)", text)
        return text

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        """Convert Obsidian Markdown back to Telegram HTML."""
        text = md
        text = re.sub(
            r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text
        )
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)
        return text

    # ─── VAULT LOADERS ────────────────────────────────────────────────────

    def _load_skill(self, skill_name: str) -> str:
        """Load a skill SKILL.md from vault."""
        path = self.vault_path / f".claude/skills/{skill_name}/SKILL.md"
        if path.exists():
            return path.read_text()
        return ""

    def _load_reference(self, skill_name: str, ref_name: str) -> str:
        """Load a reference file from a skill."""
        path = self.vault_path / f".claude/skills/{skill_name}/references/{ref_name}.md"
        if path.exists():
            return path.read_text()
        return ""

    def _load_content_seeds_skill(self) -> str:
        return self._load_skill("content-seeds")

    def _load_content_planner_skill(self) -> str:
        return self._load_skill("content-planner")

    def _load_tone_of_voice(self) -> str:
        return self._load_reference("content-seeds", "tone-of-voice")

    def _load_humanizer(self) -> str:
        return self._load_reference("content-seeds", "humanizer")

    def _load_strategy(self) -> str:
        return self._load_reference("content-seeds", "strategy")

    def _load_icp(self) -> str:
        return self._load_reference("content-seeds", "icp")

    def _load_tone_examples(self) -> str:
        return self._load_reference("content-seeds", "tone-examples")

    def _load_strategy_notes(self) -> str:
        """Load strategy notes added via /note command."""
        path = self.vault_path / "content" / "strategy-notes.md"
        if path.exists():
            return path.read_text()
        return ""

    def save_strategy_note(self, text: str) -> Path:
        """Save a strategy note to vault/content/strategy-notes.md."""
        notes_dir = self.vault_path / "content"
        notes_dir.mkdir(parents=True, exist_ok=True)
        notes_path = notes_dir / "strategy-notes.md"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{timestamp}] {text.strip()}\n"

        if notes_path.exists():
            existing = notes_path.read_text()
        else:
            existing = "# Strategy Notes\n\n"

        notes_path.write_text(existing + entry)
        logger.info("Strategy note saved to %s", notes_path)
        return notes_path

    def _load_monthly_goals(self) -> str:
        goals_path = self.vault_path / "goals" / "2-monthly.md"
        if goals_path.exists():
            return goals_path.read_text()
        return ""

    def _load_current_plan(self) -> str:
        """Load the most recent content plan."""
        plans_dir = self.vault_path / "content" / "plans"
        if not plans_dir.exists():
            return ""
        plan_files = sorted(plans_dir.glob("*.md"), reverse=True)
        if not plan_files:
            return ""
        content = plan_files[0].read_text()
        return content[:5000] if content else ""

    def _load_all_seeds(self, max_weeks: int = 8) -> str:
        """Load accumulated content seeds from recent weeks."""
        seeds_dir = self.vault_path / "content" / "seeds"
        if not seeds_dir.exists():
            return ""

        unified_path = seeds_dir / "seeds.md"
        if not unified_path.exists():
            return ""

        content = unified_path.read_text()
        # Strip frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()

        # Limit to max_weeks
        if max_weeks < 99:
            week_headers = list(re.finditer(r"^## (\d{4}-W\d{2})", content, re.MULTILINE))
            if len(week_headers) > max_weeks:
                cutoff = week_headers[max_weeks].start()
                content = content[:cutoff]

        return content

    # ─── RAW MATERIAL COLLECTION ──────────────────────────────────────────

    def _summarize_meeting(self, name: str, text: str, cache_dir: Path | None = None) -> str:
        """Summarize a long meeting transcript. Caches result."""
        if cache_dir:
            cache_file = cache_dir / f"{name}.summary.md"
            if cache_file.exists():
                cached = cache_file.read_text()
                if cached.strip():
                    logger.info("Using cached summary for %s", name)
                    return f"[SUMMARY]\n{cached}"

        prompt = (
            "Ты суммаризатор встреч. Извлеки из транскрипта ВСЕ ключевые мысли, "
            "решения, инсайты, интересные идеи и цитаты. Ничего важного не пропускай.\n\n"
            "Формат ответа — краткий конспект (bullet points), до 2000 слов. "
            "Пиши на том же языке, что и транскрипт.\n\n"
            f"=== TRANSCRIPT: {name} ===\n{text}"
        )
        try:
            summary = self._call_llm(prompt, model=SUMMARIZE_MODEL, max_tokens=4096)
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
        """Collect raw material from vault (daily, meetings, thoughts)."""
        today = date.today()
        parts: list[str] = []

        # Daily files
        daily_dir = self.vault_path / "daily"
        if daily_dir.exists():
            for i in range(days):
                day = today - timedelta(days=i)
                daily_file = daily_dir / f"{day.isoformat()}.md"
                if daily_file.exists():
                    content = daily_file.read_text()
                    if content.strip():
                        parts.append(f"=== DAILY {day.isoformat()} ===\n{content}")

        # Meeting transcripts
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
                                    md_file.stem, content, cache_dir=meetings_dir
                                )
                            parts.append(f"=== MEETING {md_file.stem} ===\n{content}")
                except ValueError:
                    continue

        # Thoughts
        thoughts_dir = self.vault_path / "thoughts"
        if thoughts_dir.exists():
            cutoff = today - timedelta(days=days)
            for subdir in thoughts_dir.iterdir():
                if not subdir.is_dir():
                    continue
                for md_file in sorted(subdir.glob("*.md"), reverse=True):
                    try:
                        file_date = date.fromisoformat(md_file.name[:10])
                        if file_date >= cutoff:
                            content = md_file.read_text()
                            if content.strip():
                                parts.append(f"=== THOUGHT {md_file.stem} ===\n{content}")
                    except ValueError:
                        continue

        # Content ideas (from voice messages)
        ideas_path = self.vault_path / "content" / "seeds" / "ideas.md"
        if ideas_path.exists():
            content = ideas_path.read_text()
            if content.strip():
                parts.append(f"=== CONTENT IDEAS (voice notes) ===\n{content}")

        return "\n\n".join(parts) if parts else ""

    # ─── SAVE CONTENT SEEDS ───────────────────────────────────────────────

    def _save_content_seeds(self, html: str, seeds_date: date) -> Path:
        """Save content seeds to unified vault/content/seeds/seeds.md."""
        year, week, _ = seeds_date.isocalendar()
        week_str = f"{year}-W{week:02d}"
        seeds_dir = self.vault_path / "content" / "seeds"
        seeds_dir.mkdir(parents=True, exist_ok=True)
        seeds_path = seeds_dir / "seeds.md"

        content = self._html_to_markdown(html)

        week_section = f"## {week_str} ({seeds_date.strftime('%d %B')})\n"
        week_section += f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"
        week_section += content.strip() + "\n\n"

        if seeds_path.exists():
            existing = seeds_path.read_text()
        else:
            existing = ""

        # Parse frontmatter + body
        frontmatter = ""
        body = existing
        if existing.startswith("---"):
            end_fm = existing.find("---", 3)
            if end_fm != -1:
                fm_end = end_fm + 3
                if fm_end < len(existing) and existing[fm_end] == "\n":
                    fm_end += 1
                frontmatter = existing[:fm_end]
                body = existing[fm_end:]

        # Ensure frontmatter
        if frontmatter:
            frontmatter = re.sub(
                r"last_updated:.*",
                f"last_updated: {datetime.now().strftime('%Y-%m-%d')}",
                frontmatter,
            )
            frontmatter = re.sub(
                r"last_accessed:.*",
                f"last_accessed: {datetime.now().strftime('%Y-%m-%d')}",
                frontmatter,
            )
        else:
            frontmatter = (
                "---\n"
                "type: content-seeds\n"
                f"last_updated: {datetime.now().strftime('%Y-%m-%d')}\n"
                "---\n"
            )

        # Ensure heading
        if "# Content Seeds" not in body:
            body = "\n# Content Seeds\n\n" + body.lstrip("\n")

        # Insert or replace week
        week_header_pattern = rf"## {re.escape(week_str)}\b"
        if re.search(week_header_pattern, body):
            pattern = rf"(## {re.escape(week_str)}\b.*?)(?=\n## \d{{4}}-W\d{{2}}|\Z)"
            body = re.sub(pattern, week_section.rstrip("\n"), body, count=1, flags=re.DOTALL)
        else:
            heading_match = re.search(r"^# Content Seeds\s*\n", body, re.MULTILINE)
            if heading_match:
                insert_pos = heading_match.end()
                body = body[:insert_pos] + "\n" + week_section + body[insert_pos:].lstrip("\n")
            else:
                body = "\n# Content Seeds\n\n" + week_section + body

        new_content = frontmatter + body
        seeds_path.write_text(new_content)
        logger.info("Content seeds saved to %s (week %s)", seeds_path, week_str)
        return seeds_path

    # ─── SAVE CONTENT PLAN ────────────────────────────────────────────────

    def _save_content_plan(self, html: str, plan_date: date) -> Path:
        """Save content plan to vault/content/plans/."""
        year, week, _ = plan_date.isocalendar()
        week_str = f"{year}-W{week:02d}"
        plans_dir = self.vault_path / "content" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plans_dir / f"{week_str}-plan.md"

        content = self._html_to_markdown(html)
        plan_path.write_text(content)
        logger.info("Content plan saved to %s", plan_path)
        return plan_path

    # ─── SELF-REFINE ──────────────────────────────────────────────────────

    def _self_refine_seeds(self, seeds_html: str, tone_rules: str) -> str | None:
        """Self-Refine pass: critique seeds against humanizer/tone rules."""
        system_text = f"""Ты — редактор контента {self.author}. Тебе дают черновик content seeds.

ЗАДАЧА: Найди ВСЕ нарушения правил тона и стиля, затем перепиши seeds с исправлениями.

=== ПРАВИЛА ТОНА И СТИЛЯ ===
{tone_rules}
=== END RULES ===

ИНСТРУКЦИИ:
1. Проверь КАЖДЫЙ hook на AI-паттерны (параллельные конструкции, написанные метафоры, GPT-измы)
2. Проверь эмоджи (должны быть ПОСЛЕ фразы как реакция, не как украшение)
3. Проверь наличие конкретных имён, разговорного языка, скобочных мыслей
4. Если нарушений нет — верни seeds БЕЗ ИЗМЕНЕНИЙ
5. Если есть — исправь и верни полную версию

CRITICAL: Верни ТОЛЬКО исправленную версию seeds в том же HTML-формате.
- НЕ пиши список нарушений, анализ или комментарии — ТОЛЬКО финальные seeds
- Не меняй структуру, количество seeds, темы
- Меняй только формулировки hooks где есть нарушения"""

        refine_prompt = f"""=== ЧЕРНОВИК SEEDS ===
{seeds_html}
=== END SEEDS ==="""

        try:
            refined = self._call_llm(
                refine_prompt, model=REFINE_MODEL, max_tokens=8192, system=system_text
            )
            if not refined or len(refined) < len(seeds_html) * 0.5:
                logger.warning("Self-refine returned suspiciously short result, skipping")
                return None
            logger.info("Self-refine completed: %d -> %d chars", len(seeds_html), len(refined))
            return refined
        except Exception as e:
            logger.warning("Self-refine failed: %s", e)
            return None

    # ─── GENERATE CONTENT SEEDS ───────────────────────────────────────────

    def generate_content_seeds(self) -> dict[str, Any]:
        """Generate content seeds from weekly raw material."""
        today = date.today()

        skill_content = self._load_content_seeds_skill()
        tone_of_voice = self._load_tone_of_voice()
        strategy = self._load_strategy()
        icp = self._load_icp()
        tone_examples = self._load_tone_examples()
        strategy_notes = self._load_strategy_notes()

        raw_material = self._collect_raw_material(days=7)
        if not raw_material:
            return {
                "error": "Нет записей за последние 7 дней для генерации seeds",
                "processed_entries": 0,
            }

        references = ""
        if tone_of_voice:
            references += f"\n=== TONE OF VOICE & HUMANIZER ===\n{tone_of_voice}\n=== END TONE OF VOICE ===\n"
        if strategy:
            references += f"\n=== CONTENT STRATEGY ===\n{strategy}\n=== END STRATEGY ===\n"
        if icp:
            references += f"\n=== ICP & POSITIONING ===\n{icp}\n=== END ICP ===\n"
        if tone_examples:
            references += f"\n=== TONE OF VOICE EXAMPLES ===\n{tone_examples}\n=== END TONE EXAMPLES ===\n"
        if strategy_notes:
            references += f"\n=== STRATEGY NOTES (ПРИОРИТЕТ — учитывай обязательно) ===\n{strategy_notes}\n=== END STRATEGY NOTES ===\n"

        system_text = f"""=== SKILL INSTRUCTIONS ===
{skill_content}
=== END SKILL ===
{references}
CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Follow the output format from SKILL INSTRUCTIONS exactly

CRITICAL RULES:
- Оценивай seeds по матрице из CONTENT STRATEGY (арка, функция, тон)
- Каждый seed ОБЯЗАН принадлежать одной из 3 нарративных арок
- Целься в конкретный сегмент ICP - кто прочтёт и кивнёт?
- Применяй ВСЕ правила из TONE OF VOICE (голос {self.author} + анти-AI фильтр)
- Каждый hook проверяй на AI-паттерны перед выдачей
- Пиши как живой человек, не как ChatGPT"""

        prompt = f"""Сегодня {today}. Сгенерируй content seeds из сырого материала ниже.

=== RAW MATERIAL (last 7 days) ===
{raw_material}
=== END RAW MATERIAL ==="""

        try:
            output = self._call_llm(
                prompt, model=SEEDS_MODEL, max_tokens=8192, system=system_text
            )

            # Self-Refine pass
            refined = self._self_refine_seeds(output, tone_of_voice)
            if refined:
                output = refined

            # Save to vault
            try:
                self._save_content_seeds(output, today)
            except Exception as e:
                logger.warning("Failed to save content seeds: %s", e)

            return {
                "report": output,
                "processed_entries": 1,
            }

        except anthropic.APITimeoutError:
            return {"error": "Content seeds generation timed out", "processed_entries": 0}
        except Exception as e:
            logger.exception("Unexpected error during content seeds generation")
            return {"error": str(e), "processed_entries": 0}

    # ─── GENERATE CONTENT PLAN ────────────────────────────────────────────

    def generate_content_plan(self, channel_posts: str = "") -> dict[str, Any]:
        """Generate weekly content plan from seeds and channel history."""
        today = date.today()

        skill_content = self._load_content_planner_skill()
        strategy = self._load_strategy()
        icp = self._load_icp()
        seeds_content = self._load_all_seeds()
        goals = self._load_monthly_goals()
        strategy_notes = self._load_strategy_notes()

        if not seeds_content:
            return {
                "error": "Нет content seeds. Сначала запусти /content",
                "processed_entries": 0,
            }

        notes_block = ""
        if strategy_notes:
            notes_block = f"\n=== STRATEGY NOTES (ПРИОРИТЕТ — учитывай обязательно) ===\n{strategy_notes}\n=== END STRATEGY NOTES ===\n"

        system_text = f"""Ты составляешь недельный контент-план для {self.channel_label}.

=== SKILL INSTRUCTIONS ===
{skill_content}
=== END SKILL ===

=== CONTENT STRATEGY ===
{strategy[:4000] if strategy else ''}
=== END STRATEGY ===

=== ICP & POSITIONING ===
{icp}
=== END ICP ===

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Follow the output format from SKILL INSTRUCTIONS exactly

RULES:
- Выбирай лучшие seeds из ВСЕГО пула (не только свежие)
- Проверяй последние посты — не повторяй темы
- Один пост должен быть якорным (самый сильный hook)
- Чередуй тяжёлые и лёгкие посты"""

        prompt = f"""Сегодня {today}. Составь контент-план на неделю.
{notes_block}
=== CONTENT SEEDS ===
{seeds_content}
=== END CONTENT SEEDS ===

=== ПОСЛЕДНИЕ ПОСТЫ ИЗ КАНАЛА ===
{channel_posts if channel_posts else 'Нет данных о последних постах'}
=== END CHANNEL POSTS ===

=== ЦЕЛИ МЕСЯЦА ===
{goals if goals else 'Нет данных'}
=== END GOALS ==="""

        try:
            output = self._call_llm(
                prompt, model=PLAN_MODEL, max_tokens=8192, system=system_text
            )

            # Save plan
            try:
                self._save_content_plan(output, today)
            except Exception as e:
                logger.warning("Failed to save content plan: %s", e)

            return {
                "report": output,
                "processed_entries": 1,
            }

        except anthropic.APITimeoutError:
            return {"error": "Content plan generation timed out", "processed_entries": 0}
        except Exception as e:
            logger.exception("Unexpected error during content plan generation")
            return {"error": str(e), "processed_entries": 0}

    # ─── RECONCILE PLAN WITH CHANNEL ────────────────────────────────────

    def reconcile_plan_with_channel(self, channel_posts: str) -> dict[str, Any]:
        """Compare plan with published posts, mark done, suggest adjustments."""
        plan_text = self._load_current_plan()
        if not plan_text:
            return {"error": "Нет текущего плана. Сначала запусти /plan", "processed_entries": 0}

        today = date.today()
        year, week, _ = today.isocalendar()
        week_str = f"{year}-W{week:02d}"

        tone_of_voice = self._load_tone_of_voice()
        strategy = self._load_strategy()

        system_text = f"""Ты сверяешь недельный контент-план с опубликованными постами канала.

=== TONE OF VOICE & HUMANIZER ===
{tone_of_voice}
=== END TONE OF VOICE ===

=== CONTENT STRATEGY ===
{strategy}
=== END STRATEGY ===

ЗАДАЧА:
1. Определи какие посты из плана уже опубликованы - отметь их ✅
2. Для неопубликованных - оставь как есть или скорректируй если нужно
3. Проверь чередование арок по правилам CONTENT STRATEGY
4. Верни полный обновлённый план

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- NO markdown: no **, no ##, no ```, no tables
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Все hooks пиши живым языком по правилам TONE OF VOICE"""

        prompt = f"""Сравни контент-план с опубликованными постами канала.

=== КОНТЕНТ-ПЛАН ({week_str}) ===
{plan_text}
=== END PLAN ===

=== ПОСТЫ КАНАЛА ===
{channel_posts}
=== END POSTS ==="""

        try:
            output = self._call_llm(
                prompt, model=PLAN_MODEL, max_tokens=8192, system=system_text
            )

            try:
                self._save_content_plan(output, today)
            except Exception as e:
                logger.warning("Failed to save reconciled plan: %s", e)

            return {"report": output, "processed_entries": 1}

        except anthropic.APITimeoutError:
            return {"error": "Reconciliation timed out", "processed_entries": 0}
        except Exception as e:
            logger.exception("Unexpected error during reconciliation")
            return {"error": str(e), "processed_entries": 0}

    # ─── WRITE POST ───────────────────────────────────────────────────────

    def write_post(self, user_request: str) -> dict[str, Any]:
        """Write a post based on user request, using seeds and tone rules."""
        tone_of_voice = self._load_tone_of_voice()
        strategy = self._load_strategy()
        icp = self._load_icp()
        tone_examples = self._load_tone_examples()
        relevant_seeds = self._find_relevant_seeds(user_request)
        raw_material = self._collect_raw_material(days=30)

        system_text = f"""Ты — контент-райтер {self.author} для {self.channel_label}. Пишешь посты в этом голосе.

=== TONE OF VOICE & HUMANIZER ===
{tone_of_voice}
=== END TONE OF VOICE ===

=== CONTENT STRATEGY ===
{strategy[:3000] if strategy else ''}
=== END STRATEGY ===

=== ICP & POSITIONING ===
{icp}
=== END ICP ===

=== TONE EXAMPLES ===
{tone_examples[:3000] if tone_examples else ''}
=== END TONE EXAMPLES ===

ПРАВИЛА НАПИСАНИЯ ПОСТОВ [КРИТИЧНО]:

АБСОЛЮТНЫЙ ЗАПРЕТ НА ВЫДУМКИ:
- КАЖДЫЙ факт, сцена, имя, цифра ОБЯЗАНЫ быть из SEEDS или RAW MATERIAL
- Если деталей не хватает — скажи что не хватает, НЕ додумывай

СТИЛЬ:
- Пиши от первого лица {self.author} — живо, разговорно, с самоиронией
- Начинай с конкретной сцены из seeds, НЕ с абстрактного утверждения
- НЕ используй нумерованные списки и подзаголовки
- НЕ используй AI-паттерны: "Не X. А Y.", "это про...", "важно понимать"
- НЕ заканчивай моралью — читатель сам поймёт
- Эмоджи только как реакция ПОСЛЕ фразы, не как декор

CRITICAL OUTPUT FORMAT:
- Return ONLY raw HTML for Telegram (parse_mode=HTML)
- Allowed tags: <b>, <i>, <code>, <s>, <u>
- Be concise - Telegram has 4096 char limit"""

        prompt = f"""Напиши пост.

=== ЗАПРОС ===
{user_request}
=== END ЗАПРОС ===

=== РЕЛЕВАНТНЫЕ SEEDS (ИСПОЛЬЗУЙ ТОЛЬКО ЭТИ ФАКТЫ) ===
{relevant_seeds if relevant_seeds else 'нет seeds по этой теме'}
=== END SEEDS ===

=== RAW MATERIAL ===
{raw_material[:8000] if raw_material else 'нет записей'}
=== END RAW MATERIAL ==="""

        try:
            output = self._call_llm(
                prompt, model=SEEDS_MODEL, max_tokens=4096, system=system_text
            )
            return {"report": output, "processed_entries": 1}
        except Exception as e:
            logger.exception("Failed to write post")
            return {"error": str(e), "processed_entries": 0}

    # ─── REFINE POST ───────────────────────────────────────────────────────

    def refine_post(self, original_post: str, edit_request: str) -> dict[str, Any]:
        """Apply user's edits/feedback to a generated post."""
        tone_of_voice = self._load_tone_of_voice()

        system_text = f"""Ты — контент-райтер {self.author}. Тебе дают пост и правки автора.
Внеси правки, сохрани стиль и тон.

=== TONE OF VOICE ===
{tone_of_voice[:3000] if tone_of_voice else ''}
=== END TONE ===

CRITICAL:
- Верни ТОЛЬКО исправленный пост, без комментариев
- Формат: raw HTML для Telegram (parse_mode=HTML)
- Allowed tags: <b>, <i>, <code>, <s>, <u>"""

        prompt = f"""=== ТЕКУЩИЙ ПОСТ ===
{original_post}
=== END POST ===

=== ПРАВКИ ===
{edit_request}
=== END ПРАВКИ ==="""

        try:
            output = self._call_llm(
                prompt, model=REFINE_MODEL, max_tokens=4096, system=system_text
            )
            return {"report": output, "processed_entries": 1}
        except Exception as e:
            logger.exception("Failed to refine post")
            return {"error": str(e), "processed_entries": 0}

    # ─── FIND RELEVANT SEEDS ──────────────────────────────────────────────

    def _find_relevant_seeds(self, query: str) -> str:
        """Find seeds relevant to the user's request."""
        all_seeds = self._extract_seed_titles()
        if not all_seeds:
            return ""

        # Crude stemming: match on a 5-char prefix so Russian inflections
        # ("автоматизацию" vs "автоматизация") still hit each other.
        stems = [w.lower()[:5] for w in re.findall(r"\w+", query) if len(w) > 3]
        if not stems:
            return "\n\n---\n\n".join(s["full_text"] for s in all_seeds[:5])

        scored = []
        for s in all_seeds:
            text_lower = s["full_text"].lower()
            score = sum(1 for stem in stems if stem in text_lower)
            if score > 0:
                scored.append((score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            return "\n\n---\n\n".join(s["full_text"] for s in all_seeds[:5])

        return "\n\n---\n\n".join(s["full_text"] for _, s in scored[:5])

    # ─── EXTRACT SEED TITLES ─────────────────────────────────────────────

    def _extract_seed_titles(self) -> list[dict]:
        """Extract seed titles from unified seeds.md file."""
        seeds_dir = self.vault_path / "content" / "seeds"
        if not seeds_dir.exists():
            return []

        unified_path = seeds_dir / "seeds.md"
        if not unified_path.exists():
            return []

        content = unified_path.read_text()
        # Strip frontmatter
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                content = content[end + 3:].strip()

        results = []
        # Split by week headers
        week_pattern = re.compile(r"^## (\d{4}-W\d{2})", re.MULTILINE)
        week_starts = list(week_pattern.finditer(content))

        for i, wm in enumerate(week_starts):
            week = wm.group(1)
            start = wm.start()
            end_pos = week_starts[i + 1].start() if i + 1 < len(week_starts) else len(content)
            section = content[start:end_pos]

            seed_pattern = re.compile(
                r"\*{0,2}Seed\s*#(\d+)[:\s]+(.+?)\*{0,2}\s*$",
                re.MULTILINE,
            )
            seed_starts = list(seed_pattern.finditer(section))
            for j, m in enumerate(seed_starts):
                num = int(m.group(1))
                title = m.group(2).strip().rstrip("*~ ")
                is_published = "✅" in m.group(0)
                is_dismissed = "❌" in m.group(0) or "~" in m.group(0)

                s_start = m.start()
                s_end = seed_starts[j + 1].start() if j + 1 < len(seed_starts) else len(section)
                full_text = section[s_start:s_end].strip()

                results.append({
                    "week": week,
                    "num": num,
                    "title": title,
                    "full_text": full_text,
                    "published_in_vault": is_published,
                    "dismissed_in_vault": is_dismissed,
                })

        return results

    # ─── SAVE CONTENT IDEA (from voice) ─────────────────────────────────

    def save_content_idea(self, text: str) -> Path:
        """Save a raw content idea to vault/content/seeds/ideas.md."""
        ideas_dir = self.vault_path / "content" / "seeds"
        ideas_dir.mkdir(parents=True, exist_ok=True)
        ideas_path = ideas_dir / "ideas.md"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n- [{timestamp}] {text.strip()}\n"

        if ideas_path.exists():
            existing = ideas_path.read_text()
        else:
            existing = "# Content Ideas\n\nРaw ideas from voice messages and quick notes.\n"

        ideas_path.write_text(existing + entry)
        logger.info("Content idea saved to %s", ideas_path)
        return ideas_path

    # ─── DISMISSED SEEDS ──────────────────────────────────────────────────

    def _dismissed_path(self) -> Path:
        return self.vault_path / "content" / "seeds" / ".dismissed.json"

    def _load_dismissed(self) -> list[dict]:
        import json
        path = self._dismissed_path()
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return []
        return []

    def _save_dismissed(self, dismissed: list[dict]) -> None:
        import json
        path = self._dismissed_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dismissed, ensure_ascii=False, indent=2))

    def dismiss_seeds(self, seeds_to_dismiss: list[dict]) -> int:
        """Mark seeds as dismissed. Returns count of newly dismissed."""
        dismissed = self._load_dismissed()
        existing_keys = {(d.get("week"), d.get("num")) for d in dismissed}
        newly = 0
        for s in seeds_to_dismiss:
            key = (s.get("week"), s.get("num"))
            if key not in existing_keys:
                dismissed.append(s)
                existing_keys.add(key)
                newly += 1
        self._save_dismissed(dismissed)
        return newly

    def mark_seed_in_file(self, week: str, num: int, marker: str) -> None:
        """Add a marker (✅ or ❌) to a seed title in seeds.md."""
        seeds_path = self.vault_path / "content" / "seeds" / "seeds.md"
        if not seeds_path.exists():
            return

        content = seeds_path.read_text()
        pattern = re.compile(
            rf"(\*{{0,2}}Seed\s*#{num}[:\s]+.+?)(\*{{0,2}}\s*$)",
            re.MULTILINE,
        )

        # Find within the right week section
        week_pattern = re.compile(rf"^## {re.escape(week)}\b", re.MULTILINE)
        week_match = week_pattern.search(content)
        if not week_match:
            return

        # Find next week header
        next_week = re.search(r"^## \d{4}-W\d{2}\b", content[week_match.end():], re.MULTILINE)
        section_end = week_match.end() + next_week.start() if next_week else len(content)
        section = content[week_match.start():section_end]

        seed_match = pattern.search(section)
        if not seed_match:
            return

        old_line = seed_match.group(0)
        if marker in old_line:
            return  # Already marked

        new_line = old_line.rstrip() + f" {marker}"
        abs_start = week_match.start() + seed_match.start()
        abs_end = week_match.start() + seed_match.end()
        content = content[:abs_start] + new_line + content[abs_end:]

        seeds_path.write_text(content)
        logger.info("Marked seed #%d in %s with %s", num, week, marker)

    # ─── LIST UNPUBLISHED SEEDS ───────────────────────────────────────────

    def list_unpublished_seeds(self, channel_posts: str) -> dict[str, Any]:
        """List all seeds, filtering dismissed and published ones."""
        all_seeds = self._extract_seed_titles()
        if not all_seeds:
            return {"error": "Нет seeds. Запусти /content для генерации."}

        dismissed = self._load_dismissed()
        dismissed_keys = {(d.get("week"), d.get("num")) for d in dismissed}

        active_seeds = []
        for s in all_seeds:
            if (s["week"], s["num"]) in dismissed_keys:
                continue
            if s.get("published_in_vault") or s.get("dismissed_in_vault"):
                continue
            active_seeds.append(s)

        if not active_seeds:
            return {"error": "Все seeds удалены или опубликованы. Запусти /content для новых."}

        return {
            "seeds": active_seeds,
            "total": len(all_seeds),
            "active_count": len(active_seeds),
        }
