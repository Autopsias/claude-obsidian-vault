# vault-skills

The active-maintenance skill bundle. Install after `vault-framework` —
these skills assume a vault scaffolded with the framework's rules and
templates.

## What it ships

```
vault-skills/
├── .claude-plugin/plugin.json
└── skills/
    ├── kb-curator/              # Audit/lint/refresh-index/propose-cleanup/rotate-logs
    ├── plan-builder/            # HTML dashboards for multi-session work
    ├── save-conversation/       # Chat → typed vault note with quality filter
    └── autoresearch-loop/       # Karpathy-style scored optimisation
```

## kb-curator

The vault's maintenance kernel. Auto-detects FLAT vs OBSIDIAN substrate
from `_cowork_contract.json`, then runs the appropriate audit chain.

Modes:
- `audit` — full chain (OBSIDIAN: audit_obsidian + audit_bitemporal + audit_rules + audit_plans_index). `--with-lint` adds lint-orphans + lint-stale.
- `audit-contradictions` — find conflicting claims across notes
- `audit-orphans` — find notes with zero inbound wikilinks
- `lint-stale` — Karpathy LLM-Wiki stale-citation suite
- `refresh-index` — rebuild `_index.md` content catalog
- `propose-cleanup` — P-10 promotion candidates
- `cleanup-dryrun` — preview a propose-cleanup without writing
- `rotate-logs` — when `_auto_writes.md` > 80 KB or `_cleanup_log.md` > 200 KB
- `audit-writes` — reconcile hash-chain against filesystem reality
- `migrate-vocab` — bulk rename a frontmatter vocabulary term across the vault
- `upgrade-audit` / `upgrade-propose` / `upgrade-apply` — FLAT → OBSIDIAN
- `refresh-rules` / `refresh-plans-index` — keep meta-files current
- `promote-lesson` — promote a `_lessons.md` line to a discipline rule

Reads `_cowork_contract.json` for substrate detection. Triggers on phrases
like "audit kb/vault", "refresh kb index", "find orphan notes", "lint stale
citations", "convert flat kb to obsidian".

## plan-builder

Build self-contained HTML plan dashboards for multi-session work. Output
ships with sticky session strip, twin donut rings, session-arc timeline,
categories grid, copy-pasteable per-session prompts with embedded closeout
protocols, light/dark theme, and a plan-achievement infographic (5
templates).

The HTML embeds an Operating Manual that future Claude sessions read before
editing so progress updates stay drift-free.

Triggers: "create a plan", "execution plan", "session plan", "improvement
plan", "rollout plan", "multi-session plan". Do NOT use for simple to-do
lists or one-off charts.

## save-conversation

Promote a mid-conversation analysis from chat into a typed vault note.
Auto-classifies the destination zone (60 Concepts / 50 Sources/_analysis /
70 Decisions / 10 People / 20 Companies / 00 Inbox when uncertain), applies
the three-question quality filter, proposes title and frontmatter, presents
one accept/reject/edit question, and on approval writes the file and logs
it.

Triggers: `/save`, "save this", "save this to the vault", "save this
analysis", "promote this to [zone]", "this is worth keeping".

Karpathy principle: good answers shouldn't disappear into chat history.

## autoresearch-loop

Autonomous Karpathy-style optimization loop for any scorable text artefact.
Five-question scoping gate; three-phase loop (setup / iterate / promotion
review). NEVER STOP directive once it's running.

Use for: any text artefact with a measurable output where you want
overnight iterative improvement. Don't use for: stateful systems, unclear
value correlation, irreversible side effects.

## How they compose

`kb-curator` is the daily / weekly maintenance. `plan-builder` is the
project-management surface for execution work. `save-conversation` is the
mid-session capture ritual. `autoresearch-loop` is the autonomous
improvement engine — point it at any of the above to make it better.

## Version

`0.1.0` — initial extraction. Each underlying skill carries its own
version history; this plugin pins them at the versions current as of
2026-05-17.
