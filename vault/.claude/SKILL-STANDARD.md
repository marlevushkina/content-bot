# Skill Creation Standard

Based on [skill-conductor](https://github.com/smixs/skill-conductor) best practices.

## Universal Principles

1. **Progressive disclosure** — Load metadata first, then body content, then references
2. **Clean structure** — No README, CHANGELOG, or extraneous files inside skills
3. **Description as trigger, not process** — Describe *when* to use the skill, not *how* it works
4. **Right tool selection** — Use scripts for fragile operations; use prose for judgment calls
5. **Naming conventions** — kebab-case, third-person, imperative voice

## Critical Rule: The "Process Leak"

**NEVER put process steps in the skill description.**

When descriptions list workflows ("exports assets, generates specs"), Claude follows those instructions and ignores the actual skill body.

❌ BAD:
```yaml
description: Personal assistant for processing daily voice/text entries from Telegram. Classifies content, creates TickTick tasks aligned with goals, saves thoughts to Obsidian with wiki-links, generates HTML reports.
```

✅ GOOD:
```yaml
description: Triggers on /process command or daily 21:00 cron. Processes daily entries into tasks and thoughts.
```

## Standard Frontmatter

```yaml
---
type: note
description: [WHEN to use - triggers only, NO process steps]
name: skill-name
tier: active/warm/cold
last_accessed: YYYY-MM-DD
relevance: 0.0-1.0
---
```

### Fields:
- **type**: Always `note`
- **description**: Trigger-based (when/what), NOT process-based (how)
- **name**: kebab-case identifier
- **tier**: `active` (frequently used), `warm` (occasionally), `cold` (rarely)
- **last_accessed**: Auto-updated by memory system
- **relevance**: Auto-calculated by memory system (0.0-1.0)

## Structure

```
skill-name/
├── SKILL.md           # Core instructions (frontmatter + body)
├── references/        # On-demand documentation (one level deep only)
│   ├── example.md
│   └── patterns.md
├── scripts/           # Deterministic, tested operations (optional)
│   └── process.py
└── assets/            # Templates and images (optional)
```

## SKILL.md Template

```markdown
---
type: note
description: Triggers on [command/event]. [Brief purpose in one sentence].
name: skill-name
tier: active
---

# Skill Name

[One-sentence summary of what this skill does]

## Use Cases

- Trigger 1: [when this happens]
- Trigger 2: [when user asks for X]

## Instructions

[Core logic and decision-making guidance]

## Output Format

[Expected output structure]

## References

- references/patterns.md — [what's in this file]
- references/example.md — [what's in this file]
```

## Description Formula

**Structure:** `Triggers on [X]. [Purpose in one sentence].`

**Examples:**
- `Triggers on /graph command. Analyzes vault link structure and suggests connections.`
- `Triggers on /content command. Generates content seeds from weekly raw material.`
- `Triggers on /process or daily 21:00 cron. Processes daily entries into tasks and thoughts.`

**NOT:**
- ❌ Lists workflow steps
- ❌ Describes internal logic
- ❌ Explains how it works

## Evaluation Checklist

Before committing a skill, verify:

- [ ] Description is trigger-based (no process steps)
- [ ] Frontmatter follows standard format
- [ ] No README/CHANGELOG inside skill folder
- [ ] References are one level deep only
- [ ] Name is kebab-case
- [ ] Body has progressive disclosure (metadata → instructions → examples)

## When to Create a Skill vs Reference

**Create a skill when:**
- Agent needs to make judgments or decisions
- Workflow varies based on context
- Multiple tools/commands need orchestration

**Create a reference when:**
- Information is purely factual
- No decision-making required
- Just documentation/examples

---

*Updated: 2026-03-04*
*Source: https://github.com/smixs/skill-conductor*
