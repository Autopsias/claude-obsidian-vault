# upgrade-audit / upgrade-propose / upgrade-apply — FLAT → OBSIDIAN

This reference is the source of truth for the three upgrade modes when the
project's substrate is **FLAT** (`CLAUDE.md` + `cowork_outputs/`) and the
user wants to migrate it to **OBSIDIAN** (Johnny-Decimal vault). The modes
must run in order:

  1. `upgrade-audit`   — read-only diff against the OBSIDIAN baseline.
  2. `upgrade-propose` — write a proposal file the user reviews.
  3. `upgrade-apply`   — execute the proposal after explicit approval.

These modes do not delete a single byte of the existing FLAT project. The
legacy state is preserved in `_archive/legacy-cowork_outputs/` (see "Legacy
preservation" below) — that single rule is the load-bearing one.

If the project is already OBSIDIAN, route to the in-substrate variant of
upgrade (compare its scaffold against current canonical) instead — covered
in the inline doc for `upgrade-audit` in SKILL.md.

---

## The OBSIDIAN baseline (what we're upgrading to)

A complete OBSIDIAN vault has these surfaces. The upgrade pipeline creates
the missing ones from canonical templates, preserves anything that already
exists in the FLAT project, and archives whatever doesn't have a home.

### 1. Eleven Johnny-Decimal zones (vault root)

```
00 Inbox/            10 People/           20 Companies/
30 Projects/         40 Meetings/         50 Sources/
60 Concepts/         70 Decisions/        80 Daily/
90 System/           99 Workspace/
```

Each zone gets a `README.md` describing what lives there (sourced from
canonical templates). `00 Inbox/`, `80 Daily/`, and `99 Workspace/` are
auto-write zones (per `.claude/rules/auto-write-discipline.md`); the rest
are trigger-only.

### 2. Eleven canonical Bases (`90 System/Bases/`)

```
People.base          Companies.base       Projects.base
Meetings.base        Sources.base         Decisions.base
Open Items.base      Tier-2 Sources.base  Latest Only.base
As Of.base           Version Chain.base
```

Copied verbatim from canonical resources (see "Canonical source" below).

### 3. Seven `.claude/rules/` discipline files

```
auto-write-discipline.md          daily-notes-discipline.md
freshness-discipline.md           inbox-discipline.md
mount-discipline.md               plugin-security-discipline.md
state-moc-edit-discipline.md
```

These are layered-rules files that Claude auto-loads in OBSIDIAN sessions.
Copied verbatim from canonical.

### 4. `_operating_guide.md` at `90 System/` — 13 P-rules

The full 13 P-rules (P-1 through P-13). Treated as a template — the upgrade
ships the canonical version. If the FLAT project carried a `_guide_*.md`
file with custom content, that file is preserved in `_archive/` (NOT merged
automatically — the user merges by hand if they want).

### 5. `_plans_index.md` at vault root

Empty header by default, populated as plans are added. If the FLAT project
had any `_plan_*.html` files, they're moved into `99 Workspace/` and the
index seeded with one row per plan (computed via `audit_plans_index.py
--proposal`).

### 6. Retrieval trio at `90 System/`

```
_retrieval_contract.md       — the eval contract (what queries the vault
                               must answer in ≤2 retrieval hops)
_eval_retrieval.md           — the latest eval run's results
_smoke_test_retrieval.py     — automated smoke test
```

All three from canonical templates. The contract carries a frontmatter
`last_updated:` field — audit_obsidian.py check 6 flags it when >30 days
old.

### 7. Two top-level pinned files

```
CLAUDE.md                    — stable prefix (preserved from FLAT if the
                               user wants — otherwise replaced by template)
_cowork_contract.json        — thresholds / vocab_version / skill_versions
                               (copied as-is from FLAT if present)
```

---

## Legacy preservation — the CRITICAL rule

**Do NOT merge `cowork_outputs/` into the new JD zones.** Trying to route
each file to its "correct" zone is a content judgment, not a structural
move — and kb-curator does not make content judgments (see "No strategic
judgement" in SKILL.md hard guardrails).

Instead, the entire `cowork_outputs/` tree is moved verbatim:

```
<root>/cowork_outputs/   →   <root>/_archive/legacy-cowork_outputs/
```

This is the same pattern Galp Vault used during its S09 conversion: the
old surface stays intact, addressable, and grep-able as a single archived
unit. Future curation (deciding which legacy debriefs deserve promotion
into `40 Meetings/` etc.) happens session-by-session via the normal
`propose-cleanup` flow against the new OBSIDIAN substrate — never as part
of the upgrade itself.

Any other legacy folders unique to the FLAT project (`02_Final_Deliverables/`,
`05_Knowledge_Base/`, `06_Templates/`) are moved into `_archive/`
preserving their internal structure. Each gets a single-line note in
`_archive/_README.md` explaining its origin.

---

## Canonical source — where templates come from

Templates are looked up in this order:

  1. `--canonical /path/to/dir`            (explicit flag)
  2. `KB_CURATOR_CANONICAL` env var
  3. `<vault>/90 System/_skill_resources/galp-vault-canonical/`
  4. `<vault>/90 System/_skill_resources/<any-canonical>/`
  5. The skill's own `references/canonical/` fallback (if shipped)

The Galp Vault stores its canonical at the path in (3) — that's the
reference implementation. Any OBSIDIAN scaffolding skill
(`obsidian-project-new`, `obsidian-project-convert`) ships an identical
folder so kb-curator can find it.

If no canonical source is found, upgrade-audit reports a hard error and
points the user at the install instructions for the scaffolding skill.

---

## upgrade-audit — read-only diff

Phase 0 detects FLAT substrate. Then:

  1. Resolve the canonical source (see above). Hard-stop if none found.
  2. Enumerate which of the 7 OBSIDIAN surfaces above exist in the FLAT
     project and which don't. (Most won't.)
  3. Tally legacy artefacts that would move to `_archive/`:
     * `cowork_outputs/`         → file count, total bytes
     * `02_Final_Deliverables/`  → file count, total bytes
     * `05_Knowledge_Base/`      → per-subzone file count
     * `06_Templates/`           → file count
     * Any other top-level folder not in the JD eleven    → list
  4. Read `_cowork_contract.json` if present; capture `vocab_version` and
     `skill_versions` for the proposal.
  5. Print a structured report to stdout:

```
upgrade-audit (FLAT → OBSIDIAN): <project root>

CURRENT FLAT SUBSTRATE
  cowork_outputs/                     <N> files, <M> KB
  02_Final_Deliverables/              <N> files, <M> KB
  05_Knowledge_Base/<subzones>        ...
  06_Templates/                       <N> files, <M> KB
  _cowork_contract.json               vocab_version="<v>" (canonical=<vc>)

OBSIDIAN BASELINE — present / missing
  00 Inbox/                           MISSING
  10 People/                          MISSING
  ...
  90 System/Bases/                    MISSING (0/11 .base files)
  90 System/_operating_guide.md       MISSING
  .claude/rules/                      MISSING (0/7 discipline files)
  _plans_index.md                     MISSING
  90 System/_retrieval_contract.md    MISSING

UPGRADE FOOTPRINT (preview)
  Files to CREATE      : <N>   (from canonical templates)
  Files to MOVE        : <N>   (cowork_outputs/ + sibling folders → _archive/)
  Files to PRESERVE    : <N>   (CLAUDE.md, _cowork_contract.json, _plan_*.html)
  Files to DELETE      : 0     (we never delete during upgrade)
```

Exit 0 if no upgrade is needed (project already aligned — unlikely for FLAT);
exit 1 if any surface is missing or any legacy artefact would move.

---

## upgrade-propose — write the proposal

Writes a proposal file at:

```
<root>/cowork_outputs/_upgrade_proposal_<YYYY-MM-DD>.md
```

(The proposal lives in the FLAT working zone so it gets archived along
with `cowork_outputs/` when `upgrade-apply` runs — a free audit trail.)

Proposal contents (template):

```markdown
---
type: cleanup-log
date: YYYY-MM-DD
provenance: kb-curator upgrade-propose flat→obsidian
status: PENDING_APPROVAL
---

# Upgrade proposal — FLAT → OBSIDIAN — YYYY-MM-DD

## Phase 1 — Create JD zones (11 directories)
- mkdir 00 Inbox/ + README.md
- mkdir 10 People/ + README.md
- ... (one line per zone)

## Phase 2 — Install canonical Bases (11 files)
- 90 System/Bases/People.base                ← <canonical path>
- 90 System/Bases/Companies.base             ← <canonical path>
- ... (one line per Base)

## Phase 3 — Install .claude/rules/ (7 files)
- .claude/rules/auto-write-discipline.md     ← <canonical>
- ... (one line per rule)

## Phase 4 — Install 90 System/ scaffolding (5 files)
- 90 System/_operating_guide.md              ← <canonical>
- 90 System/_retrieval_contract.md           ← <canonical>
- 90 System/_eval_retrieval.md               ← <canonical>
- 90 System/_smoke_test_retrieval.py         ← <canonical>
- 90 System/_bases_verifier.py               ← <canonical>

## Phase 5 — Seed _plans_index.md at root
- _plans_index.md                            (seeded with N existing plans)

## Phase 6 — Archive legacy substrate (single moves, verbatim trees)
- cowork_outputs/                            → _archive/legacy-cowork_outputs/
- 02_Final_Deliverables/                     → _archive/02_Final_Deliverables/
- 05_Knowledge_Base/                         → _archive/05_Knowledge_Base/
- 06_Templates/                              → _archive/06_Templates/
- <any other top-level non-JD folder>        → _archive/<name>/

## Phase 7 — Preserve at root
- CLAUDE.md                                  (kept verbatim; user merges with template later)
- _cowork_contract.json                      (kept verbatim)
- _plan_*.html                               (moved into 99 Workspace/)

## Manual attention needed (NOT done by upgrade-apply)
- CLAUDE.md      — merge canonical stable-prefix template into existing content by hand.
- _operating_guide.md — review the 13 P-rules; tailor wording (the canonical version is generic).
- .claude/rules/freshness-discipline.md — the canonical refers to "the state MOC";
  replace with your project's state-MOC path (e.g. "30 Projects/<Project>.md").
- 99 Workspace/_session_handoff.md — write the first OBSIDIAN session handoff
  (carry over the last few entries from any FLAT handoff for continuity).

## Rollback
After upgrade-apply, the project's full pre-upgrade state lives at
`_archive/legacy-cowork_outputs/` and `_archive/<other>/` — bit-identical.
To roll back, copy these directories back to the root and remove the JD zones.
This is a "moves only" upgrade — no content was modified or deleted.
```

Exit 0 always (proposal writing is idempotent).

---

## upgrade-apply — execute after explicit approval

Phase 0 detects FLAT. Then:

  1. Read the most recent `cowork_outputs/_upgrade_proposal_*.md`. If
     `status:` != `APPROVED`, hard-stop and ask the user to flip the flag
     (or add `approve upgrade proposal` in the next message — curator.py
     parses this and rewrites the file).
  2. Execute each Phase in order. Each operation is logged to
     `_archive/_upgrade_log.md` as:

```
YYYY-MM-DDTHH:MM:SSZ | mkdir | <path>
YYYY-MM-DDTHH:MM:SSZ | copy  | <canonical_src> | <dst>
YYYY-MM-DDTHH:MM:SSZ | move  | <src>           | <dst>
```

  3. For Phase 6 moves, use `cp -a` (atomic across devices) followed by
     a `cmp -r` byte-identical verification before deleting the source —
     same pattern as `mount-discipline.md` recovery procedure.
  4. After all phases, write a session handoff stub at
     `99 Workspace/_session_handoff.md` describing what was done and what
     manual attention is still needed.
  5. Print a summary:

```
upgrade-apply complete.

  Created : <N> files in <K> zones
  Moved   : <N> files (legacy → _archive/)
  Preserved: <N> files at root
  Log     : _archive/_upgrade_log.md

NEXT STEPS (manual — these were NOT done by upgrade-apply):
  1. Merge CLAUDE.md (template + your existing content).
  2. Tailor 90 System/_operating_guide.md and freshness-discipline.md
     to your project.
  3. Run `kb-audit` to verify the new OBSIDIAN substrate.
  4. Re-run the smoke test: python3 90 System/_smoke_test_retrieval.py
```

Exit 0 on success; exit 1 on any cmp mismatch (and roll back that phase).

---

## Idempotency

Re-running upgrade-apply after a partial run is safe: every Phase checks
`if dst already exists, skip (log "already present")`. Files that exist
are NEVER overwritten — they're listed as "manual attention needed" in
the final summary so the user can decide whether to merge by hand.

---

## Companion scripts (curator.py wiring)

`curator.py` exposes upgrade modes as:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/curator.py upgrade-audit    --root <root>
python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/curator.py upgrade-propose  --root <root>
python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/curator.py upgrade-apply    --root <root>
```

Each mode runs `detect_substrate.py` as Phase 0 and refuses if substrate
isn't FLAT. (For OBSIDIAN-to-OBSIDIAN upgrades — comparing your scaffold
against a newer canonical — see the inline doc for `upgrade-audit` in
SKILL.md.)
