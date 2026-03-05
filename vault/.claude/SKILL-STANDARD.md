# Skill Creation Standard

Based on [skill-conductor v2](https://github.com/smixs/skill-conductor).

## Universal Principles

1. **Progressive disclosure** — Load metadata first, then body content, then references
2. **Clean structure** — No README, CHANGELOG, or extraneous files inside skills
3. **Description as trigger, not process** — Describe *when* to use the skill, not *how* it works
4. **Right tool selection** — Use scripts for fragile operations; use prose for judgment calls
5. **Naming conventions** — kebab-case, third-person, imperative voice
6. **TDD baseline** — Before writing a skill, verify the agent FAILS without it

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
├── evals/             # Test scenarios (optional)
│   └── evals.json
└── assets/            # Templates and images (optional)
```

## Architecture Patterns (Choose Before Writing)

Choose a primary pattern. Most skills combine elements from multiple patterns.

| Pattern | When to use | Key elements |
|---------|-------------|-------------|
| **Sequential Workflow** | Steps have dependencies | Explicit ordering, validation at each stage, rollback on failure |
| **Iterative Refinement** | Quality-sensitive output | Quality criteria, iteration cap (max 3), validation scripts |
| **Context-Aware Selection** | Same goal, different tools by context | Decision tree, transparency about choices, fallback |
| **Domain Intelligence** | Specialized knowledge, compliance | Pre-check rules before action, audit trail |
| **Multi-Service Coordination** | Workflow spans multiple MCPs | Phase separation, data passing, validation between phases |

### Our skills and their patterns:

| Skill | Pattern(s) |
|-------|-----------|
| dbrain-processor | Sequential + Domain Intelligence + Multi-Service (TickTick + Planfix + Calendar) |
| content-seeds | Iterative Refinement (gap analysis) + Context-Aware (content mix) |
| content-planner | Context-Aware (LinkedIn vs TG) + Sequential (week planning) |
| graph-builder | Domain Intelligence (entity extraction rules) |

## Degrees of Freedom

How much control vs. flexibility the skill gives the agent:

| Freedom | When | Example |
|---------|------|---------|
| **Low** (scripts) | Fragile, error-prone, must be exact | API calls, PDF rotation, file format conversion |
| **Medium** (pseudocode) | Preferred pattern exists, some variation ok | Data processing, report generation |
| **High** (text) | Multiple valid approaches, judgment needed | Content creation, design decisions |

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

## Anti-patterns

| Anti-pattern | Why it fails | Fix |
|-------------|-------------|-----|
| **Wall of text** | Agent skims paragraphs, misses critical detail | Break into numbered steps with clear actions |
| **Assumed context** | "Use the standard approach" — standard to whom? | Define every term, link every reference |
| **Synonym cycling** | template/boilerplate/scaffold for same concept | Pick one term, use it everywhere |
| **Hidden prerequisites** | Required tools/envs not mentioned until step 5 | List all prerequisites upfront |
| **Description as manual** | Workflow in description → agent skips body entirely | Description = triggers only. Process lives in body |

## Evaluation Checklist

Before committing a skill, verify:

- [ ] **TDD baseline**: Agent FAILS without this skill (skill is necessary)
- [ ] Description is trigger-based (no process steps)
- [ ] Architecture pattern chosen and documented
- [ ] Degrees of freedom specified (Low/Medium/High)
- [ ] Frontmatter follows standard format
- [ ] No README/CHANGELOG inside skill folder
- [ ] References are one level deep only
- [ ] Name is kebab-case
- [ ] Body has progressive disclosure (metadata → instructions → examples)
- [ ] Consistent terminology (no synonym cycling)
- [ ] Prerequisites listed upfront

## Operating Modes

| Mode | When | What happens |
|------|------|-------------|
| **CREATE** | Building a new skill | Intent → architecture → scaffold → write → test |
| **IMPROVE** | Fixing a skill | Diagnose → eval loop → blind comparison → iterate |
| **VALIDATE** | Testing a skill | Structural checks + trigger testing + 5-axis scoring |
| **REVIEW** | Third-party assessment | 11-point quality gate |
| **OPTIMIZE** | Improving triggers | Automated description optimization with train/test split |
| **PACKAGE** | Distribution | Validate + bundle into .skill file |

### Mode 1: CREATE workflow

1. **Capture Intent** — Extract 2-3 concrete scenarios (trigger, non-trigger, edge case)
2. **Baseline (TDD RED)** — Run scenario without skill, document what fails
3. **Choose Architecture** — Pick pattern from table above, specify degrees of freedom
4. **Scaffold** — Create folder structure
5. **Write SKILL.md** — Follow template
6. **Test (TDD GREEN)** — Run same scenario with skill, verify it works

### Mode 2: IMPROVE workflow

1. **Diagnose** — Identify what's failing (use grader agent)
2. **Eval loop** — Run evals, compare versions (use comparator agent)
3. **Analyze** — Understand WHY version A beats B (use analyzer agent)
4. **Iterate** — Apply fixes, re-test

## Evaluation Agents

Three agents available in `vault/.claude/agents/`:

| Agent | Role |
|-------|------|
| **grader** | Evaluates assertions against execution transcript. Evidence-based pass/fail. |
| **comparator** | Blind A/B comparison of two outputs. Rubric scoring without bias. |
| **analyzer** | Post-hoc analysis: WHY did winner win? Actionable improvement suggestions. |

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

*Updated: 2026-03-05*
*Source: https://github.com/smixs/skill-conductor (v2)*
