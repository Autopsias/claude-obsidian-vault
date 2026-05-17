---
name: kb-curator
description: "Maintain a Cowork project in FLAT or OBSIDIAN substrate (auto-detected). Modes: audit (OBSIDIAN chains 4 scripts: audit_obsidian + audit_bitemporal + audit_rules + audit_plans_index; --with-lint adds lint-orphans + lint-stale), audit-contradictions, audit-orphans, lint-stale (Karpathy LLM-Wiki lint suite), refresh-index, propose-cleanup, cleanup-dryrun, rotate-logs, audit-writes, revert, migrate-vocab, upgrade-audit/propose/apply (FLAT to OBSIDIAN), refresh-rules, refresh-plans-index, promote-lesson. Reads _cowork_contract.json. Triggers: audit kb/vault, kb health check, refresh kb index, propose kb cleanup, rotate kb logs, promote lesson, lint orphan notes, lint stale citations, lint contradictions between notes, find orphan notes, propagate stale wikilinks, find contradictions between notes, convert flat kb to obsidian, or any phrase about checking, pruning, learning, or upgrading the markdown knowledge base. Not for Excel/Word/PDF audits, contract review, or filesystem cleanup."
---

# kb-curator (Galp Vault override)

**This file is the Galp-Vault override of the canonical kb-curator SKILL.md** at
`mnt/.claude/skills/kb-curator/SKILL.md` (read-only plugin install). It documents
the three Karpathy lint modes shipped during Framework Remediation S02-S04
(2026-05-14): `audit-contradictions` (KP-01/02 in S02), `audit-orphans`
(KP-03/04 in S03), and `lint-stale` (KP-05/06 in S04). The default OBSIDIAN
audit chain stays at 4 scripts; lint scripts are opt-in via `--with-lint` or
direct mode invocation.

Operationalises the cleanup ritual (P-1 through P-10 in cowork-preparation, or the equivalent P-10 promotion ritual in Obsidian vaults) as a callable routine. Supports two substrate types detected automatically at Phase 0.

**Two substrates supported:**

| Substrate | Signature | Working zone | Routing reference |
|-----------|-----------|--------------|-------------------|
| **FLAT** | `CLAUDE.md` + `cowork_outputs/` | `cowork_outputs/` | `references/propose-cleanup-flat.md` |
| **OBSIDIAN** | `CLAUDE.md` + `90 System/` + `99 Workspace/` | `99 Workspace/` | `references/propose-cleanup-obsidian.md` |

If neither fingerprint matches, kb-curator refuses with a clear error listing what was checked.

## Phase 0 — substrate detection (mandatory, every mode)

Same as canonical SKILL.md. Run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/detect_substrate.py \
  [--root /path/to/project]
```

- Exit 0 + stdout `FLAT` → FLAT.
- Exit 1 + stdout `OBSIDIAN` → OBSIDIAN.
- Exit 2 + stdout `UNKNOWN` → **hard stop.**

Galp Vault always returns `OBSIDIAN`.

## When to invoke

**Manual triggers:** "audit kb", "kb health check", "weekly maintenance", "refresh index", "propose cleanup", "rotate logs", "lint orphans", "lint stale", "lint contradictions", "find orphan notes", "propagate stale", "check stale citations", "find contradictions".

**Auto-suggest at session start when any threshold is tripped:**

*FLAT projects:* unchanged from canonical.

*OBSIDIAN projects (Galp Vault):*

- `99 Workspace/_cleanup_log.md` > 200 KB
- `99 Workspace/_auto_writes.md` > 80 KB
- File count in `99 Workspace/` > 150
- **NEW (KP-07):** any active `99 Workspace/_lint_stale_*.md` reports `flagged_high >= 5` or `flagged_medium >= 20`.
- **NEW (KP-07):** any active `99 Workspace/_lint_orphans_*.md` reports `orphans_total >= 30` (raised to 30 after the S03 finding that 260 typeless orphans is the steady-state until P-10 backfill happens; default threshold of 5 would auto-suggest every session).
- **NEW (KP-07):** any active `99 Workspace/_lint_contradictions_*.md` reports `contradictions_total >= 1` (Haiku-adjudicated contradictions are high-precision; even one is worth a look).

When a threshold trips, propose the corresponding mode — never auto-execute.

## Pick a mode, then read the matching reference

| Mode | Use when | Reference file |
|------|----------|----------------|
| `audit` | User asks for a health check, weekly maintenance, or any "is the kb OK" question | [`references/audit.md`](references/audit.md) + (OBSIDIAN only) run `scripts/audit_obsidian.py`, `scripts/audit_bitemporal.py`, `scripts/audit_rules.py`, `scripts/audit_plans_index.py`. Pass `--with-lint` to also chain `audit_orphans.py` + `propagate_stale.py`. |
| `audit-contradictions` | **NEW (KP-02, S02 2026-05-14).** User wants semantic-pair contradiction lint over `type:source` + `type:decision`. Standalone — never in audit chain (Haiku cost). | [`references/lint-contradictions.md`](references/lint-contradictions.md) + `scripts/audit_contradictions.py` |
| `audit-orphans` | **NEW (KP-04, S03 2026-05-14).** User wants graph-reachability lint — surface notes with no wikilink-in and no Base type-binding. | [`references/lint-orphans.md`](references/lint-orphans.md) + `scripts/audit_orphans.py` |
| `lint-stale` | **NEW (KP-06, S04 2026-05-14).** User wants stale-citation lint — surface notes whose upstream binary hash has changed or whose cited source has been demoted. | [`references/lint-stale.md`](references/lint-stale.md) + `scripts/propagate_stale.py` |
| `refresh-index` | After a batch of file writes | FLAT only — OBSIDIAN uses Smart Connections |
| `propose-cleanup` | User wants a cleanup proposal | FLAT: [`references/propose-cleanup-flat.md`](references/propose-cleanup-flat.md) · OBSIDIAN: [`references/propose-cleanup-obsidian.md`](references/propose-cleanup-obsidian.md) |
| `rotate-logs` | Rotate operational logs | [`references/rotate-logs.md`](references/rotate-logs.md) |
| `audit-writes` | Reconcile auto-writes log against filesystem | (inline doc) |
| `revert` | Undo an executed cleanup batch | (inline doc) |
| `migrate-vocab` | Compare project vocabulary against curator's | (inline doc — FLAT only) |
| `upgrade-audit` | Read-only check whether project predates current scaffold | FLAT→OBSIDIAN: [`references/upgrade-flat-to-obsidian.md`](references/upgrade-flat-to-obsidian.md) · OBSIDIAN→OBSIDIAN: inline doc |
| `upgrade-propose` | Proposal of additive upgrades | same as upgrade-audit |
| `upgrade-apply` | Create missing canonical files (after approval) | same as upgrade-audit |
| `refresh-rules` | Align `.claude/rules/` with canonical | (OBSIDIAN only — `scripts/audit_rules.py --proposal` + inline doc) |
| `refresh-plans-index` | Rebuild `_plans_index.md` | (OBSIDIAN only — `scripts/audit_plans_index.py --proposal` + inline doc) |
| `promote-lesson` | Promote applied-twice reflections to `_lessons.md` | (inline doc) |
| `cleanup-dryrun` | See actual cross-reference rewrites before approval | (inline doc) |
| `setup-automation` | Canonical scheduled-task creation prompts | (inline doc) |

If ambiguous, default to `audit` — it's read-only and surfaces what other modes are needed. Never run more than one mode per invocation.

## Slash command shortcuts

`/kb-audit`, `/kb-refresh-index`, `/kb-propose-cleanup`, `/kb-rotate-logs`,
`/kb-lint-orphans`, `/kb-lint-stale`, `/kb-lint-contradictions` (the last three
added 2026-05-14) — each maps to its mode directly.

## Routing — what `propose-cleanup` actually moves

Same as canonical: substrate-dependent. After Phase 0 detection, load the
appropriate reference (`propose-cleanup-flat.md` or `propose-cleanup-obsidian.md`).

## OBSIDIAN audit checks (audit mode)

In OBSIDIAN mode, `audit` chains **4 scripts by default**. Run them in this
order; surface results verbatim from each script's stdout. Any FAIL in any
script blocks "all green".

### 1. `scripts/audit_obsidian.py` — structural integrity (6 checks)
### 2. `scripts/audit_bitemporal.py` — P-4 frontmatter conformance
### 3. `scripts/audit_rules.py` — `.claude/rules/` drift
### 4. `scripts/audit_plans_index.py` — plans index consistency

Bodies of these four checks are unchanged from the canonical SKILL.md.
Read the canonical at `mnt/.claude/skills/kb-curator/SKILL.md` for the
detailed bullet lists.

### Optional extension: `audit --with-lint` (KP-07 wiring, added 2026-05-14)

When the user passes `--with-lint` (or the session-start auto-suggest fires
because a stored proposal's threshold tripped), `audit` also runs:

5. **`scripts/audit_orphans.py`** — Karpathy Lint Mode 2 (graph reachability).
   See [`references/lint-orphans.md`](references/lint-orphans.md). Runtime
   ~0.5s. Writes `99 Workspace/_lint_orphans_YYYY-MM-DD.md`.
6. **`scripts/propagate_stale.py`** — Karpathy Lint Mode 3 (stale propagation).
   See [`references/lint-stale.md`](references/lint-stale.md). Runtime ~1-3s.
   Writes `99 Workspace/_lint_stale_YYYY-MM-DD.md`.

`audit_contradictions.py` (Lint Mode 1) is **deliberately NOT chained** by
`--with-lint`. It uses Claude-Haiku adjudication on candidate pairs (~$0.10
per run + ~10s), so it stays standalone (`audit-contradictions` mode) for
explicit invocation only.

**Why this gating design.** A 4-script default audit runs in <2 seconds and
should fire frequently (weekly, on every session start when a threshold
trips). Adding stale + orphans pushes it to ~5 seconds and produces two
extra `_lint_*` files in `99 Workspace/` per run. That's fine when the user
wants the full picture (`--with-lint`) but the default audit stays cheap so
people don't avoid running it.

**Auto-suggest thresholds** (KP-07, repeated here for emphasis):

| Mode | Auto-suggest when |
|---|---|
| `audit` | Weekly cadence OR thresholds trip from prior cleanup state. |
| `audit --with-lint` | Any of the three lint thresholds trip (see Auto-suggest above). |
| `audit-contradictions` | Explicit user trigger only. |
| `audit-orphans` | Explicit user trigger OR auto-suggest at session start when prior `_lint_orphans_*.md` reports `orphans_total >= 30`. |
| `lint-stale` | Explicit user trigger OR auto-suggest at session start when prior `_lint_stale_*.md` reports `flagged_high >= 5` or `flagged_medium >= 20`. |

### Direct mode invocation

The three lint modes can also be invoked directly without `audit`:

```bash
# Lint Mode 1 - contradictions (Haiku-adjudicated, ~10s, ~$0.10/run)
python3 ${PLUGIN_ROOT}/skills/kb-curator/scripts/audit_contradictions.py --root /path/to/vault

# Lint Mode 2 - orphans (markdown regex, <1s, free)
python3 ${PLUGIN_ROOT}/skills/kb-curator/scripts/audit_orphans.py --root /path/to/vault

# Lint Mode 3 - stale (manifest + frontmatter, <3s, free)
python3 ${PLUGIN_ROOT}/skills/kb-curator/scripts/propagate_stale.py --root /path/to/vault
```

For Galp Vault, the vault-local scripts shipped during S02-S04 live under
`.claude/skills/kb-curator/scripts/` (writable; sibling of the canonical
plugin install). Use those paths directly:

```bash
cd <YOUR_VAULT_PATH>
python3 .claude/skills/kb-curator/scripts/audit_contradictions.py --root .
python3 .claude/skills/kb-curator/scripts/audit_orphans.py            --root .
python3 .claude/skills/kb-curator/scripts/propagate_stale.py          --root .
```

All three are proposal-only — they write a single `99 Workspace/_lint_*_YYYY-MM-DD.md` audit file and never edit citing notes.

## How to invoke (universal)

Same project-root resolution as canonical:

1. `--root /path/to/project` flag
2. `COWORK_ROOT` environment variable
3. Auto-detect — walk up from cwd looking for `CLAUDE.md`

## Trust the script (applies to every mode)

`curator.py` and the audit scripts are the source of truth for every probe and
proposal. Read their stdout AND the file they write — do NOT inspect raw input
files and try to judge things by eye. If a lint script says `0 stale flagged`,
report exactly that — don't second-guess it by reading the underlying notes.

## Hard guardrails (apply to every mode, both substrates)

Unchanged from canonical:

- **No content edits.** Never summarise, condense, or rewrite any debrief / battleplan / state file / 6-pager / synthesis.
- **No state-file edits.** Touched only on explicit user trigger.
- **No CLAUDE.md edits.** Same rule.
- **No deletes, ever.** Moves only, after approval.
- **No promotion of work-in-progress.**
- **No moves outside the working zone without line-level approval.**
- **No strategic judgement.** The skill surfaces what mechanically drifted.
- **Pinned files never proposed for move.** (See canonical for full list.)
- **OBSIDIAN archive target is single-root `_archive/<zone>/` only.**

### Lint-specific guardrails (KP-02 / KP-04 / KP-06)

- **Lint scripts NEVER edit citing or candidate notes.** All three write a
  single audit `.md` to `99 Workspace/` and stop.
- **Lint scripts NEVER add `stale:`, `confidence:`, or `orphan:` frontmatter
  fields to source notes.** That's a P-10 typed-zone edit, trigger-only.
- **The lint proposal `.md` is auto-write per P-7 + `auto-write-discipline.md`.**
  Same logging applies as any `99 Workspace/` write.

## Contract-driven configuration

Same as canonical: reads `_cowork_contract.json` for thresholds and
`skill_versions`. KP-07 adds three optional contract keys:

- `lint_orphans_auto_suggest_threshold` (default: 30)
- `lint_stale_high_threshold` (default: 5)
- `lint_stale_medium_threshold` (default: 20)

If unset in the contract, the defaults above apply.

## Migration / upgrade modes

Unchanged from canonical (Path A FLAT→OBSIDIAN and Path B OBSIDIAN→OBSIDIAN).

## Maintenance cadence (recommended)

| Cadence | Mode | Trigger |
|---------|------|---------|
| Every session start | `audit` if any threshold tripped | Auto-suggest |
| Every "wrap up session" | `refresh-index` (FLAT) / Smart Connections re-index (OBSIDIAN) | Bundled with handoff rewrite |
| Weekly (Monday) | `audit` | Calendar habit |
| **Monthly** | **`audit --with-lint`** + retrieval eval re-run | **First Monday — adds orphans + stale to the weekly audit** |
| **Quarterly** | **`audit-contradictions`** + state-file compression + `rotate-logs` | **End of quarter — Haiku-adjudicated contradiction sweep** |

## Companion skills

Unchanged from canonical.

## Cross-references

- **Canonical SKILL.md** (read-only plugin install) — `mnt/.claude/skills/kb-curator/SKILL.md`
- **Lint Mode 1 spec** — `.claude/skills/kb-curator/references/lint-contradictions.md`
- **Lint Mode 2 spec** — `.claude/skills/kb-curator/references/lint-orphans.md`
- **Lint Mode 3 spec** — `.claude/skills/kb-curator/references/lint-stale.md`
- **P-7 autonomy** — `90 System/_operating_guide.md`
- **Auto-write logging** — `.claude/rules/auto-write-discipline.md`
- **Ingestion contract** (manifest schema lint-stale reads) — `90 System/_ingestion_contract.md`

## Change log

- **2026-05-14 (S04, this update):** added `lint-stale` mode, the
  `--with-lint` audit flag, three auto-suggest thresholds, and the
  three new slash-command shortcuts. Default audit chain remains 4 scripts.
- **2026-05-14 (S03):** added `audit-orphans` mode.
- **2026-05-14 (S02):** added `audit-contradictions` mode.
- **2026-05-13:** kb-curator installed at `.claude/skills/kb-curator/`
  with substrate-first dispatch (FLAT / OBSIDIAN / both / neither).
