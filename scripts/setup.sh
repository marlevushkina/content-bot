#!/bin/bash
# Content Bot Setup - Interactive configuration wizard
# Replaces placeholders in SKILL.md files with your personal data

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🎨 Content Bot Setup"
echo "══════════════════════════════════════════════"
echo ""
echo "Этот скрипт поможет настроить content-bot под вас."
echo "Заполним базовые данные и создадим примеры вашего стиля."
echo ""

# ============================================================================
# ОБЯЗАТЕЛЬНЫЕ ДАННЫЕ
# ============================================================================

echo "📝 БАЗОВАЯ ИНФОРМАЦИЯ (обязательно)"
echo "────────────────────────────────────"
echo ""

read -p "Как вас зовут? (имя): " USER_NAME
while [[ -z "$USER_NAME" ]]; do
    echo "❌ Имя обязательно!"
    read -p "Как вас зовут? (имя): " USER_NAME
done

read -p "Полное имя (для LinkedIn, например 'Мария Иванова'): " FULL_NAME
while [[ -z "$FULL_NAME" ]]; do
    echo "❌ Полное имя обязательно!"
    read -p "Полное имя: " FULL_NAME
done

read -p "Telegram-канал (@username или название): " TG_CHANNEL
while [[ -z "$TG_CHANNEL" ]]; do
    echo "❌ Название канала обязательно!"
    read -p "Telegram-канал: " TG_CHANNEL
done

read -p "Основной хештег вашего канала (например, #myblog): " MAIN_HASHTAG
MAIN_HASHTAG=${MAIN_HASHTAG:-"#yourhashtag"}

# ============================================================================
# ОПЦИОНАЛЬНЫЕ ДАННЫЕ
# ============================================================================

echo ""
echo "📝 ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ (опционально)"
echo "────────────────────────────────────"
echo ""

read -p "Ваш город (оставьте пустым если не хотите указывать): " USER_CITY
USER_CITY=${USER_CITY:-"[Your City]"}

read -p "Имена команды через запятую (например, 'Оля, Женя') или Enter чтобы пропустить: " TEAM_MEMBERS
if [[ -z "$TEAM_MEMBERS" ]]; then
    TEAM_MEMBERS="[Team Member 1], [Team Member 2], [Team Member 3]"
fi

read -p "Названия ваших проектов/бизнесов через запятую (или Enter чтобы пропустить): " BUSINESSES
if [[ -z "$BUSINESSES" ]]; then
    BUSINESS_A="[Business A]"
    BUSINESS_B="[Business B]"
    BUSINESS_C="[Business C]"
else
    # Split by comma and trim
    IFS=',' read -ra BIZ_ARRAY <<< "$BUSINESSES"
    BUSINESS_A="${BIZ_ARRAY[0]##*( )}"
    BUSINESS_A="${BUSINESS_A%%*( )}"
    BUSINESS_B="${BIZ_ARRAY[1]##*( )}"
    BUSINESS_B="${BUSINESS_B%%*( )}"
    BUSINESS_C="${BIZ_ARRAY[2]##*( )}"
    BUSINESS_C="${BUSINESS_C%%*( )}"
    BUSINESS_A=${BUSINESS_A:-"[Business A]"}
    BUSINESS_B=${BUSINESS_B:-"[Business B]"}
    BUSINESS_C=${BUSINESS_C:-"[Business C]"}
fi

# ============================================================================
# КОНТЕНТ-СТРАТЕГИЯ
# ============================================================================

echo ""
echo "🎯 КОНТЕНТ-СТРАТЕГИЯ"
echo "────────────────────────────────────"
echo ""
echo "Опишите основные темы вашего канала."
echo "Это поможет боту генерировать релевантные content seeds."
echo ""

read -p "Основная тема 1 (например, 'Психология предпринимательства'): " THEME_1
THEME_1=${THEME_1:-"Ваша тема 1"}

read -p "Основная тема 2 (например, 'Системы и процессы в бизнесе'): " THEME_2
THEME_2=${THEME_2:-"Ваша тема 2"}

read -p "Основная тема 3 (опционально): " THEME_3
THEME_3=${THEME_3:-"Ваша тема 3"}

# ============================================================================
# TONE OF VOICE - ПРИМЕРЫ ПОСТОВ
# ============================================================================

echo ""
echo "✍️  TONE OF VOICE - ПРИМЕРЫ ПОСТОВ"
echo "────────────────────────────────────"
echo ""
echo "Теперь нужно добавить 3-5 примеров ваших постов."
echo "Это поможет боту писать в вашем стиле."
echo ""
echo "Варианты:"
echo "1) Вставить текст постов прямо здесь"
echo "2) Указать ссылки на посты (их можно будет скопировать вручную позже)"
echo ""

read -p "Выберите вариант (1 или 2): " TONE_CHOICE

TONE_EXAMPLES=""

if [[ "$TONE_CHOICE" == "1" ]]; then
    echo ""
    echo "Вставьте текст первого поста (закончите ввод пустой строкой):"
    POST_TEXT=""
    while IFS= read -r line; do
        [[ -z "$line" ]] && break
        POST_TEXT+="$line"$'\n'
    done
    TONE_EXAMPLES+="## Пример 1\n\n$POST_TEXT\n\n"

    echo "Вставьте текст второго поста (или Enter чтобы пропустить):"
    POST_TEXT=""
    while IFS= read -r line; do
        [[ -z "$line" ]] && break
        POST_TEXT+="$line"$'\n'
    done
    if [[ -n "$POST_TEXT" ]]; then
        TONE_EXAMPLES+="## Пример 2\n\n$POST_TEXT\n\n"
    fi

    echo "Вставьте текст третьего поста (или Enter чтобы пропустить):"
    POST_TEXT=""
    while IFS= read -r line; do
        [[ -z "$line" ]] && break
        POST_TEXT+="$line"$'\n'
    done
    if [[ -n "$POST_TEXT" ]]; then
        TONE_EXAMPLES+="## Пример 3\n\n$POST_TEXT\n\n"
    fi

else
    echo ""
    echo "Укажите ссылки на ваши посты (по одной на строку, Enter чтобы закончить):"
    LINKS=()
    while IFS= read -r line; do
        [[ -z "$line" ]] && break
        LINKS+=("$line")
    done

    TONE_EXAMPLES+="# Tone of Voice Examples\n\n"
    TONE_EXAMPLES+="TODO: Скопируйте тексты постов по ссылкам ниже:\n\n"
    for link in "${LINKS[@]}"; do
        TONE_EXAMPLES+="- $link\n"
    done
fi

# ============================================================================
# ПРИМЕНЯЕМ ИЗМЕНЕНИЯ
# ============================================================================

echo ""
echo "✅ Применяю настройки..."
echo ""

# Replace placeholders in content-seeds SKILL.md
SEEDS_SKILL="$PROJECT_ROOT/vault/.claude/skills/content-seeds/SKILL.md"
if [[ -f "$SEEDS_SKILL" ]]; then
    echo "📝 Обновляю content-seeds/SKILL.md..."
    sed -i.bak \
        -e "s/\[Your Name\]/$USER_NAME/g" \
        -e "s/\[Your Full Name\]/$FULL_NAME/g" \
        -e "s/\[Your TG Channel\]/$TG_CHANNEL/g" \
        -e "s/\[Your City\]/$USER_CITY/g" \
        -e "s/\[Team Member 1\], \[Team Member 2\], \[Team Member 3\]/$TEAM_MEMBERS/g" \
        -e "s/\[Business A\]/$BUSINESS_A/g" \
        -e "s/\[Business B\]/$BUSINESS_B/g" \
        -e "s/\[Business C\]/$BUSINESS_C/g" \
        -e "s/#yourhashtag/$MAIN_HASHTAG/g" \
        "$SEEDS_SKILL"
    rm -f "$SEEDS_SKILL.bak"
fi

# Replace placeholders in content-planner SKILL.md
PLANNER_SKILL="$PROJECT_ROOT/vault/.claude/skills/content-planner/SKILL.md"
if [[ -f "$PLANNER_SKILL" ]]; then
    echo "📝 Обновляю content-planner/SKILL.md..."
    sed -i.bak \
        -e "s/\[Your Name\]/$USER_NAME/g" \
        -e "s/\[Your Full Name\]/$FULL_NAME/g" \
        -e "s/\[Your TG Channel\]/$TG_CHANNEL/g" \
        -e "s/\[Your City\]/$USER_CITY/g" \
        -e "s/\[Business B\]/$BUSINESS_B/g" \
        "$PLANNER_SKILL"
    rm -f "$PLANNER_SKILL.bak"
fi

# Create tone-examples.md
TONE_FILE="$PROJECT_ROOT/vault/.claude/skills/content-seeds/references/tone-examples.md"
mkdir -p "$(dirname "$TONE_FILE")"
echo "📝 Создаю tone-examples.md..."
echo -e "$TONE_EXAMPLES" > "$TONE_FILE"

# Create basic strategy.md
STRATEGY_FILE="$PROJECT_ROOT/vault/.claude/skills/content-seeds/references/strategy.md"
echo "📝 Создаю strategy.md..."
cat > "$STRATEGY_FILE" << EOF
# Контент-стратегия

## Основные темы

1. **$THEME_1**
2. **$THEME_2**
3. **$THEME_3**

## Контент-микс

TODO: Определите приоритеты тем (в процентах):
- Тема 1: ___%
- Тема 2: ___%
- Тема 3: ___%
- Life/Meta: ___%

## Форматы

- Пост (300-800 слов)
- Тред (3-7 частей)
- Мысль (50-150 слов)
- Сторис (серия коротких)

## Recurring Themes

TODO: Добавьте повторяющиеся темы, о которых пишете регулярно:
- Тема А (например, еженедельные инсайты)
- Тема Б (например, кейсы из практики)
EOF

# Create vault structure
echo "📁 Создаю структуру vault..."
mkdir -p "$PROJECT_ROOT/vault/content/seeds"
mkdir -p "$PROJECT_ROOT/vault/content/posts"
mkdir -p "$PROJECT_ROOT/vault/daily"

# ============================================================================
# ГОТОВО
# ============================================================================

echo ""
echo "══════════════════════════════════════════════"
echo "✅ SETUP ЗАВЕРШЁН!"
echo "══════════════════════════════════════════════"
echo ""
echo "Что сделано:"
echo "  ✓ Заполнены SKILL.md файлы вашими данными"
echo "  ✓ Создан tone-examples.md с примерами постов"
echo "  ✓ Создан strategy.md (доработайте его под себя)"
echo "  ✓ Создана базовая структура vault/"
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Откройте references/tone-examples.md и добавьте больше примеров"
echo "2. Откройте references/strategy.md и доработайте контент-стратегию"
echo "3. Скопируйте references/humanizer.md из примеров (если нужно)"
echo "4. Запустите бота и попробуйте /content команду"
echo ""
echo "Подробности: см. SETUP.md"
echo ""
