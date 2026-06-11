# Content Bot

Telegram-бот, который превращает твои голосовые заметки, транскрипты встреч и текстовые записи в **content seeds** (заготовки постов), недельный **контент-план** и готовые **посты** — в твоём голосе, без AI-канцелярита.

Работает через **Anthropic API** напрямую (нужен только API-ключ — никаких подписок и CLI).

---

## Что умеет

- `/content` — собирает материал за неделю (daily-заметки, транскрипты, мысли) и генерирует 10-15 content seeds. Каждый seed можно отсортировать кнопками ✅/❌.
- `/plan` — недельный контент-план из накопленных seeds (TG + адаптация под LinkedIn), сверяясь с последними постами канала.
- `/write <тема>` — пишет пост по теме или seed'у, строго на фактах из твоих заметок (без выдумок).
- `/seeds` — список неопубликованных seeds.
- `/note <текст>` — заметка к стратегии, которую бот учитывает при генерации.
- **Голосовые** — расшифровка (Deepgram) → сохранить идею или сразу написать пост.
- **Свободный текст** — бот спросит, что сделать (пост / идея / заметка).
- **Ответ на пост бота** — правки: бот перепишет с учётом фидбэка.

Качество стиля держится на двух вещах: твоих **скиллах** (голос, стратегия, ICP) и **анти-AI фильтре** (humanizer), который прогоняется вторым проходом.

## Как устроено

```
Telegram (aiogram) → ContentProcessor → Anthropic API
                          ↑
                    vault/ (скиллы + твои заметки)
```

- Статический контекст (скиллы, тон, стратегия) кэшируется через prompt caching — дешевле и быстрее на повторных запросах.
- Сгенерированный контент сохраняется в `vault/content/` и (опционально) коммитится в git, если vault внутри git-репозитория.

## Требования

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — менеджер пакетов
- Telegram Bot token ([@BotFather](https://t.me/BotFather))
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com/))
- (опц.) Deepgram API key для голосовых ([deepgram.com](https://deepgram.com/))

## Установка

```bash
git clone https://github.com/marlevushkina/content-bot.git
cd content-bot

# 1. Зависимости
uv sync

# 2. Конфиг
cp .env.example .env
#   заполни TELEGRAM_BOT_TOKEN, ANTHROPIC_API_KEY, ALLOWED_USER_IDS, AUTHOR_NAME

# 3. Настрой скиллы под себя (голос, стратегия, ICP)
./scripts/setup.sh          # интерактивный мастер
#   либо отредактируй вручную файлы в vault/.claude/skills/ (см. ниже)

# 4. Запуск
uv run python -m content_bot
```

## Настройка под себя

Весь «характер» бота живёт в `vault/.claude/skills/` — код полностью обезличен.

| Файл | Что это |
|------|---------|
| `content-seeds/SKILL.md` | роль, контент-микс, формат seeds |
| `content-seeds/references/tone-of-voice.md` | твой голос (заполни) |
| `content-seeds/references/tone-examples.md` | 5-15 твоих реальных постов (вставь) |
| `content-seeds/references/strategy.md` | контент-стратегия, арки, темы |
| `content-seeds/references/icp.md` | для кого пишешь, позиционирование |
| `content-seeds/references/humanizer.md` | анти-AI правила (generic, можно не трогать) |
| `content-planner/SKILL.md` | как строить недельный план |

Шаблоны идут с плейсхолдерами `[Your Name]` / `[Your TG Channel]` — замени на своё (или прогони `scripts/setup.sh`). Чем подробнее `tone-examples.md`, тем точнее стиль.

### Откуда бот берёт материал для `/content`

Из `vault/` за последние 7 дней:
- `vault/daily/YYYY-MM-DD.md` — дневные заметки
- `vault/thoughts/<подпапка>/YYYY-MM-DD.md` — отдельные мысли
- `vault/content/meetings/YYYY-MM-DD*.md` — транскрипты встреч (длинные авто-суммаризируются)
- `vault/content/seeds/ideas.md` — быстрые идеи (в т.ч. из голосовых)

Просто клади туда `.md`-файлы или шли боту голосовые/текст. Для быстрого теста сразу работает `/write <тема>` — материал не обязателен.

## Запуск на сервере (systemd)

```bash
# отредактируй пути/пользователя под себя
sudo cp deploy/content-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now content-bot
journalctl -u content-bot -f
```

## Стоимость

Оплата по факту через Anthropic API. Один `/content` или пост — обычно несколько центов (seeds считаются на Opus, план/правки — на Sonnet; цифры зависят от объёма материала). Prompt caching снижает стоимость повторных запросов.

## Ограничения

- Краткосрочный контекст (меню действий, «ответь правкой на пост») хранится в памяти процесса и сбрасывается при рестарте бота.
- Чтение канала работает только для **публичных** Telegram-каналов (через t.me/s/).

## Author

Marina Levushkina — [@letsboss](https://t.me/letsboss)

## Built with

- [aiogram](https://docs.aiogram.dev/) — Telegram Bot framework
- [Anthropic API](https://docs.anthropic.com/) — Claude models
- [Deepgram](https://deepgram.com/) — speech-to-text
- [uv](https://github.com/astral-sh/uv) — Python package manager

## License

MIT — см. [LICENSE](LICENSE).
