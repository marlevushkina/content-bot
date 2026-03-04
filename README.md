# Content Bot

Telegram бот для извлечения контент-идей из голосовых заметок, транскриптов встреч и текстовых записей. Использует Claude Code для интеллектуального анализа и генерации контент-планов.

---

## ⚡ Quick Setup

Если вы хотите быстро настроить бота под себя:

```bash
chmod +x scripts/setup.sh
./scripts/setup.sh
```

Интерактивный скрипт заполнит ваши данные (имя, канал, темы, примеры постов) и настроит tone-of-voice.

**Подробная инструкция:** [SETUP.md](SETUP.md)

**Если нужна полная установка с нуля** — читайте разделы ниже ⬇️

---

## 🎯 Возможности

- **Обработка голосовых заметок** — транскрибация через Deepgram API
- **Генерация content seeds** — извлечение 10-15 заготовок для постов из недельного материала
- **Планирование контента** — еженедельный план публикаций для Telegram и LinkedIn
- **Синхронизация встреч** — автоматическое скачивание транскриптов из Google Drive (Fireflies)
- **Чтение постов канала** — парсинг популярных постов для анализа tone-of-voice
- **Интеграция с Claude** — использование Claude skills для генерации контента

## 🏗️ Архитектура

```
content-bot/
├── src/content_bot/           # Код бота
│   ├── bot/                   # aiogram бот
│   │   ├── handlers/          # Обработчики команд
│   │   │   ├── voice.py       # Голосовые заметки
│   │   │   ├── content.py     # Генерация seeds
│   │   │   ├── content_plan.py # Недельный план
│   │   │   └── commands.py    # Команды бота
│   │   └── main.py            # Точка входа
│   ├── services/              # Бизнес-логика
│   │   ├── processor.py       # Claude Code processor
│   │   ├── transcriber.py     # Deepgram транскрибация
│   │   ├── gdocs.py           # Google Drive sync
│   │   └── channel_reader.py  # Telegram channel parser
│   └── config.py              # Настройки (pydantic-settings)
│
├── vault/                     # Obsidian vault
│   ├── .claude/skills/        # Claude skills
│   │   ├── content-seeds/     # Генератор seeds
│   │   └── content-planner/   # Планировщик контента
│   ├── daily/                 # Ежедневные записи
│   ├── thoughts/              # Обработанные мысли
│   └── content/               # Контент-материалы
│
└── pyproject.toml             # Зависимости проекта
```

## 📋 Требования

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — менеджер пакетов
- Claude Code CLI — для генерации контента
- Telegram Bot Token — от @BotFather
- Deepgram API Key — для транскрибации голоса

## 🚀 Установка

### 1. Клонируйте репозиторий

```bash
git clone https://github.com/marlevushkina/content-bot.git
cd content-bot
```

### 2. Установите зависимости

```bash
uv sync
```

### 3. Настройте переменные окружения

Скопируйте `.env.example` в `.env`:

```bash
cp .env.example .env
```

Заполните обязательные переменные:

```env
# Telegram Bot API token от @BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ

# Deepgram API key для транскрибации голоса
DEEPGRAM_API_KEY=your_deepgram_api_key

# Путь к Obsidian vault (можно оставить ./vault)
VAULT_PATH=./vault

# Telegram user ID, которому разрешён доступ к боту
# Узнать свой ID: напишите @userinfobot в Telegram
ALLOWED_USER_IDS=[123456789]
```

**Опциональные переменные:**

```env
# Google Drive folder ID с транскриптами Fireflies
GOOGLE_DOCS_FOLDER_ID=your_folder_id

# Путь к Google service account JSON
GOOGLE_CREDENTIALS_PATH=./google-credentials.json

# Telegram канал для чтения постов (без @)
TELEGRAM_CHANNEL=your_channel
```

### 4. Установите Claude Code CLI

```bash
# macOS/Linux
curl -fsSL https://anthropic.com/cli/install.sh | sh
```

Подробнее: [Claude Code Documentation](https://docs.anthropic.com/claude/docs/claude-code)

### 5. Настройте Google Drive (опционально)

Для синхронизации транскриптов встреч из Fireflies:

1. Создайте Service Account в [Google Cloud Console](https://console.cloud.google.com)
2. Включите Google Drive API
3. Скачайте JSON ключ и сохраните как `google-credentials.json`
4. Поделитесь папкой с транскриптами с email service account

## 🎮 Использование

### Запуск бота

```bash
uv run python -m content_bot.bot.main
```

Или через uv:

```bash
uv run content-bot
```

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и описание бота |
| `/content` | Генерация content seeds из материалов |
| `/plan` | Создание недельного контент-плана |
| `/sync` | Синхронизация транскриптов из Google Drive |
| `/help` | Список всех команд |

### Работа с голосом

1. Отправьте голосовое сообщение боту
2. Бот транскрибирует через Deepgram
3. Транскрипт сохраняется в `vault/daily/YYYY-MM-DD.md`
4. Используется в генерации seeds через `/content`

### Генерация content seeds

1. Накопите материал за неделю (голосовые, текст, встречи)
2. Запустите `/content`
3. Бот запускает Claude skill `content-seeds`
4. Получите 10-15 заготовок для постов с:
   - Hook (цепляющее начало)
   - Key insight (главная мысль)
   - Источник (откуда материал)
   - Формат (пост/тред/сторис)
   - Тема (категория контента)

### Создание контент-плана

1. Запустите `/plan`
2. Выберите неделю для планирования
3. Бот генерирует план публикаций:
   - Распределяет посты по платформам
   - Учитывает нарративные арки из стратегии
   - Следует tone-of-voice правилам
   - Адаптирует контент под каждую платформу

## 🧠 Claude Skills

Бот использует Claude skills для генерации контента:

### content-seeds

**Путь:** `vault/.claude/skills/content-seeds/`

Извлекает content seeds из сырого материала (daily записи, транскрипты, thoughts).

**Reference файлы:**
- `humanizer.md` — универсальные правила против AI-паттернов
- `strategy.md` — методология нарративных арок (универсальная)
- `tone-of-voice.template.md` ➜ `tone-of-voice.md` — ваш стиль (заполняете сами)
- `tone-examples.template.md` ➜ `tone-examples.md` — ваши посты (заполняете сами)
- `icp.template.md` ➜ `icp.md` — ваша ЦА (заполняете сами)

**Первая настройка:**
1. Скопируйте `.template` файлы без `.template` в названии:
   ```bash
   cd vault/.claude/skills/content-seeds/references/
   cp tone-of-voice.template.md tone-of-voice.md
   cp tone-examples.template.md tone-examples.md
   cp icp.template.md icp.md
   ```
2. Заполните их своим контентом (инструкции внутри каждого файла)
3. Файлы добавлены в `.gitignore` — ваш личный контент не попадёт в git

### content-planner

**Путь:** `vault/.claude/skills/content-planner/`

Создаёт недельный контент-план с учётом:
- Контент-стратегии и нарративных арок (настраивается в reference файлах)
- Баланса тем и форматов
- Адаптации под разные платформы (Telegram, LinkedIn, и др.)
- Tone-of-voice правил

## ⚙️ Настройка контент-стратегии

Бот использует **методологию нарративных арок** (универсальную) + **ваш личный голос и стратегию**.

### 📚 Универсальные файлы (уже готовы):

**`humanizer.md`** — anti-AI паттерны:
- Общие GPT-измы (канцелярит, параллелизмы, шаблоны)
- Правила живого текста
- Работает для любого языка и стиля

**`strategy.md`** — методология нарративных арок:
- Концепция: арки vs рубрики
- Структура арки (5 постов: якорь → кейс → эскалация → кульминация → реальность)
- Важность якорного поста
- Оценка seeds (сильный vs слабый)
- Гайд "Как создать свои арки"

### ✏️ Персональные файлы (заполняете сами):

**`tone-of-voice.md`** (шаблон: `tone-of-voice.template.md`):
- Ваш стиль общения
- Характерные фразы и слова
- Эмоджи (как и когда)
- Структура постов
- Чек-лист перед публикацией

**`tone-examples.md`** (шаблон: `tone-examples.template.md`):
- 4-6 ваших лучших постов с анализом
- Разбор структуры каждого поста
- Tone-приёмы которые работают
- Паттерны успешных постов

**`icp.md`** (шаблон: `icp.template.md`):
- Демография и роли вашей ЦА
- Боли, проблемы, цели
- Где и как потребляют контент
- Язык аудитории

### 🚀 Workflow настройки:

1. **Скопируйте шаблоны:**
   ```bash
   cd vault/.claude/skills/content-seeds/references/
   cp tone-of-voice.template.md tone-of-voice.md
   cp tone-examples.template.md tone-examples.md
   cp icp.template.md icp.md
   ```

2. **Соберите материал:**
   - 10-15 ваших лучших постов (по engagement)
   - Аналитику аудитории (если есть)
   - Примеры слабых постов или GPT-измов

3. **Заполните `tone-examples.md`:**
   - Скопируйте лучшие посты
   - Разберите почему они сильные
   - Выделите tone-приёмы
   - Найдите общие паттерны

4. **Заполните `tone-of-voice.md`:**
   - На основе анализа постов
   - Запишите характерные фразы
   - Правила эмоджи и структуры
   - Создайте чек-лист

5. **Заполните `icp.md`:**
   - Опишите вашу ЦА
   - Их боли и цели
   - Как потребляют контент

6. **Определите свои арки в `strategy.md`:**
   - Используйте методологию из файла
   - Создайте 3-5 своих тематических арок
   - Запишите их в конец файла

7. **Тестируйте и итерируйте:**
   - Запустите `/content` для генерации seeds
   - Оцените качество
   - Уточните правила на основе результатов

## 🔧 Разработка

### Структура кода

- `src/content_bot/config.py` — настройки через pydantic-settings
- `src/content_bot/bot/` — aiogram бот
- `src/content_bot/services/` — бизнес-логика
- `vault/.claude/` — Claude skills и конфигурация

### Линтинг

```bash
uv run ruff check .
uv run ruff format .
```

### Тестирование

```bash
uv run pytest
```

## 📝 License

MIT

## 🤝 Contributing

Pull requests приветствуются! Для больших изменений сначала откройте issue.

## 📧 Author

Marina Levushkina — [@letsboss](https://t.me/letsboss)

---

**Built with:**
- [aiogram](https://docs.aiogram.dev/) — Telegram Bot framework
- [Claude Code](https://docs.anthropic.com/claude/docs/claude-code) — AI-powered code assistant
- [Deepgram](https://deepgram.com/) — Speech-to-text API
- [uv](https://github.com/astral-sh/uv) — Fast Python package manager
