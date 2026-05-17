---
name: "{{PROJECT_NAME}} — Operating Guide"
description: Behavioural rules for the {{PROJECT_NAME}} vault — nine universal P-rules (kernel) plus four extension slots this project must fill. Kernel version 1.2. If this guide and CLAUDE.md conflict, this guide wins for behaviour; CLAUDE.md wins for facts.
type: guide
cadence: monthly-or-on-structural-change
last_updated: "{{DATE}}"
provenance: Scaffolded by obsidian-project-new skill (kernel v1.2, lifted from a mature reference implementation). Nine universal P-rules distilled into the kernel; four extension slots (EXT-2 / EXT-5 / EXT-9 / EXT-13) are stubs — this project must complete them.
---

# {{PROJECT_NAME}} — Operating Guide

> **How to use this guide.** Read at session start when the task is non-trivial.
> Skip on routine continuation work — the session handoff carries enough context.
> `CLAUDE.md` wins for facts; this guide wins for behaviour. If they conflict,
> surface the conflict and pause.

> **Kernel status (v1.2).** Nine universal P-rules are complete (P-1/3/4/6/7/8/10/11/12).
> Four extension slots are stubs — search for `[EXTENSION SLOT]` and fill them in
> before treating this guide as load-bearing. An unfilled slot is not a violation;
> it is a documented gap. Operate without it, flag it in the session handoff, and
> fill it when the project pattern becomes clear.

---

## P-1 — Stable prefix discipline

**Rule.** `CLAUDE.md` is the stable prefix for this vault. Before adding to or
editing it, apply the **six-month test**: "will this still be true in six months?"
If yes → CLAUDE.md (with explicit user trigger). If no → state MOC (EXT-2) or
session handoff. If uncertain → state MOC. Moving facts *down* to the stable prefix
later is cheap; moving them *up* out of CLAUDE.md after cache drift is expensive.

**Three surfaces, three content lifetimes:**

- `CLAUDE.md` — facts that change at most twice a year: project identity, canonical
  vault path, architecture principles, "where things live" pointers, title/naming
  rules, key people roster.
- **State MOC (EXT-2)** — live project state: current workstreams, open threads,
  counterparty status, active decisions, in-flight phase. Anything that changes
  within a month belongs here, not in CLAUDE.md.
- **Session handoff** (`99 Workspace/_session_handoff.md`) — ephemeral context:
  what was worked on today, open threads from this session, next session's first
  action. Replaced every session; survives as forensic record in the archive.

**Why.** Stable-prefix prompt caching degrades with every CLAUDE.md edit and
invalidates the cache for the next session. Mixing stable and volatile content
silently corrupts retrieval — the volatile content becomes hard to update without
touching the stable surface, and the stable surface accumulates drift it should
not carry.

**How to apply.** Run the six-month test before any CLAUDE.md edit. When in doubt,
write to the state MOC — the friction of moving a fact up later is much lower than
the cost of a stale, cache-busting CLAUDE.md. Never write session-specific state
into CLAUDE.md.

**Cross-references.** `CLAUDE.md`; EXT-2 (state MOC); `99 Workspace/_session_handoff.md`;
`99 Workspace/_session_handoff_archive/`.

---

## P-3 — Five-step retrieval cascade with temporal routing matrix

<!-- KERNEL RULE — universal. The cascade steps (0–4) and the temporal routing
     matrix (Step −1) are fixed. The M9 multilingual fall-through is project-
     specific — document it in the Step 1 entry and in P-11.
     Projects with no temporal content simply never fire Routes A/B/C and
     always land on Route D. -->

**Rule.** When retrieving information from the vault, walk the cascade in order.
Stop at the first clear hit; fall through only when the current step's output is
empty, ambiguous, or low-confidence. **Before walking the cascade**, run the
temporal-intent routing matrix (Step −1 below) to choose which subset of steps to
run; absent any temporal signal, the default is the full 5-step cascade (Route D).

### Step −1 — Temporal intent routing matrix

Scan the query for **temporal-intent tokens** and route to the pre-classified path.
The cascade steps (0–4) keep their existing numbers; the matrix only chooses *which
subset to run, in what order, and against which Base*.

| Route | Trigger tokens (EN; add project-language equivalents in P-11) | Cascade subset | Primary Base |
|-------|------------------------------------------------------------------|----------------|--------------|
| **A — Current** | `current`, `latest`, `now`, `today`, `most recent`, `live`, `as it stands` | Step 0 → Step 2 | `Latest Only.base` |
| **B — As-Of** | `as of <date>`, `effective <date>`, `on <date>`, specific year ref (`in 2025`, `in Q1`), `back when`, `before <event>`, `prior to <date>` | Step 2 only, date plugged into `AS_OF_DATE` placeholder | `As Of.base` |
| **C — History** | `history`, `historical`, `evolved`, `evolution`, `changed`, `previous`, `predecessor`, `how did`, `how has`, `version chain`, `over time`, `progression` | Step 0 → Step 3 (wikilink-walk) → Step 4 (deep-read) | `Version Chain.base` |
| **D — Default** | No temporal signal detected | Full 5-step cascade (0 → 1 → 2 → 3 → 4); tie-break: prefer hit with most recent `document_date` (desc sort) | All Bases |

**[PROJECT-SPECIFIC: If your project uses Portuguese, Spanish, or another non-English
language, add the language-equivalent trigger tokens to the table above. Example —
PT/ES for Route A: `atual`, `agora`, `hoje`; Route B: `em <date>`, `a partir de
<date>`; Route C: `histórico`, `evolução`, `como mudou`. Add once; applies to all
sessions.]**

**Decision tree (ASCII).** Left-to-right; first matching branch wins.
Ties: Route B over A (date present); Route C over A ("previous"/"changed" alongside "current"):

```
                      Query arrives
                            |
                            v
              +-------------------------------+
              | Scan tokens (EN + project     |
              | language equivalents)         |
              +---------------+---------------+
                              |
       +-----------+-----------+-----------+-----------+
       |           |           |           |           |
    as-of /     history /   current /  no temporal  ambiguous
    effective   evolution / latest /    signal       (≥2 routes
    on date /   previous / now /         detected    plausibly
    year ref    how did    today                      fire)
       |           |           |           |           |
       v           v           v           v           v
    ROUTE B     ROUTE C     ROUTE A     ROUTE D     Ask user
     Step 2     Step 0      Step 0    Full 5-step  which route
    (As Of     → Step 3    → Step 2   cascade with  fits — do
     .base      → Step 4   (Latest    doc_date desc  NOT guess
    with        (Version    Only.base) tie-break
    date)       Chain.base)
       |           |           |           |
       +-----------+-----+-----+-----------+
                         |
                         v
               Emit answer + cite route taken
               (route letter in audit trail)
```

**When in doubt: ask the user which route.** If the query matches more than one route
(e.g. "what's the *current history* of X" — both Routes A and C plausibly fire), or
carries an ambiguous date reference (e.g. "before the ruling" without naming the date),
**do not silently pick.** Surface the two candidate routes and let the user choose.
The cost of a one-line clarifying question is much lower than the cost of running the
wrong route and returning a stale answer.

**Audit trail.** Every retrieval answer that turned on the routing matrix must cite the
route letter in its reasoning trace:
> "Route B — As-Of — queried `As Of.base` with `AS_OF_DATE=2025-04-14`"

The route letter is what makes the eval's T (temporal-correct) dimension scorable.

### Steps 0–4 — Five-step cascade

- **Step 0 — Lexical.** `grep` / `ripgrep` for identifiers, exact names, version
  strings, frontmatter values, anchored section headers. Cheapest, most precise.
  Use first for any query that names a specific file, person, version, or phrase.
- **Step 1 — Semantic.** Smart Connections `mcp__smart-connections__lookup` for
  paraphrase recall and conceptual proximity. **M9 multilingual caveat:** if the
  query is in the project's non-English language(s) and the embedding model degrades
  on that language, **skip step 1 entirely** and fall through to step 2 directly.
  [PROJECT: verify whether your pinned model degrades on your language — test at M2
  eval time and document the threshold in P-11.]
- **Step 2 — Structural.** Bases views under `90 System/Bases/`, queried by
  frontmatter — "all meetings with X", "all decisions on workstream Y". The temporal
  Bases (Latest Only, As Of, Version Chain) are routed here by the matrix.
- **Step 3 — Link-expand.** Wikilink BFS from a step-0/1 anchor. Depth 1, then
  depth 2. Stop when novelty drops or the relevant cluster is covered.
- **Step 4 — Deep-read.** Open the file. For long files, use anchored sections
  (EXT-2 vocabulary) to skip straight to the relevant passage.

**Retrieval is complete when:** (a) a clear hit at any step, OR (b) explicit dead ends
across all five steps — each step walked, each result null or below bar, surfaced
honestly. A genuine dead end is **not** a P-3 violation.

**Acceptance template for a genuine dead end:**
> Walked L/S/B/W/D for query "[X]"; closest hits were [list files or "nothing above
> noise floor"]; none meet the bar of [criterion]. Returning explicit dead end.

**Why.** The cascade is the load-bearing primitive. The routing matrix adds temporal
precision: "current state" and "state as of April 1" must not return the same retrieval
strategy. The temporal Bases and bitemporal frontmatter (`document_date`,
`is_latest_version`, `superseded_by`) are the substrate the matrix exploits — without
the matrix they sit unused.

**How to apply.** Run Step −1 first — always. Then match cascade step to query shape:
specific name → step 0; English paraphrase → step 1; non-English or "show me all X"
→ step 2; "what connects to Z" → step 3; "why did we decide Y" → step 4. When step 1
returns nothing, do **not** retry with a different paraphrase — fall through to step 2.

**Cross-references.** `90 System/_retrieval_contract.md` (pinned substrate + M9
baseline); `90 System/_eval_retrieval.md` (T dimension scores temporal routing);
`90 System/_smoke_test_retrieval.py` (M11 smoke-test; gates plugin updates);
`90 System/Bases/` (11 views including 3 temporal Bases); `90 System/_bases_verifier.py`;
P-11 (multilingual fall-through + plugin security).
`.claude/rules/retrieval-cascade-discipline.md` enforces this rule as an
always-on pre-answer checklist for substantive queries — see that rule
for the substantive-vs-lookup classifier and the reasoning-trace opener.

---


## P-4 — Frontmatter discipline and type vocabulary

**Rule.** Every file in a typed zone (`10 People/`, `20 Companies/`, `30 Projects/`,
`40 Meetings/`, `50 Sources/`, `60 Concepts/`, `70 Decisions/`, `90 System/`)
carries YAML frontmatter with at minimum:

```yaml
---
name: <human-readable name>
description: <one sentence — used by retrieval to disambiguate>
type: <from closed vocabulary below>
last_updated: YYYY-MM-DD
---
```

**Closed type vocabulary** (extend only with verifier + Bases update simultaneously):
`person` | `company` | `project` | `meeting` | `source` | `concept` | `decision` |
`guide` | `contract` | `log` | `handoff` | `handoff_archive` | `eval` | `inbox` |
`daily` | `template` | `base` | `system`

**Excluded zones** (no strict frontmatter): `00 Inbox/`, `80 Daily/`, `99 Workspace/`.

---

### Temporal frontmatter (bitemporal model)

Three types support versioning and require additional frontmatter. The model separates
**transaction-time** (when the *file* was touched) from **valid-time** (when the
*content* was authored or became effective in the world). This separation is what
allows the three temporal Bases to answer "what was current on date X?" correctly.

**The two-clock rule:**

| Field | Clock | Meaning |
|-------|-------|---------|
| `last_updated` | Transaction-time | When the *file* was last edited. Managed automatically by the vault. |
| `document_date` | Valid-time | When the *content* was authored, published, or the event occurred. Must be set manually. |

Never use `last_updated` to answer "is this the latest version?" — a whitespace edit today
would make a 2023 document outrank a 2026 document in "current" queries. Use
`is_latest_version` (for sources/meetings) or `superseded_by` (for decisions) instead.

---

#### type: source — MVP temporal fields (2 required)

```yaml
document_date: "YYYY-MM-DD"   # REQUIRED. Valid-time: when the source was authored/published.
                               # Distinct from last_updated (transaction-time/file mtime).
                               # Default at creation: today. Backfill from document
                               # metadata, filename prefix, or a version→date map.
is_latest_version: true        # REQUIRED. Boolean. true = current/live version.
                               # Flip to false at supersession, simultaneously promoting
                               # the new version. Used by Latest Only.base (Route A).
```

Optional versioning fields (add when the source has multiple versions):

```yaml
document_version: ""           # e.g. "v30", "3.2", "final" — used by Version Chain.base
previous_version: ""           # "[[predecessor note name]]" — chain navigation backlink
family: ""                     # family slug for Version Chain.base By Family view
                               # e.g. "6pager" — add to ALL members of a version family
```

---

#### type: meeting — MVP temporal fields (2 required)

Meetings use the same MVP as sources. They do NOT use the full decision split because
meetings are almost always additive (they don't supersede each other). `document_date`
derives canonically from the filename YYYY-MM-DD prefix, making it unambiguous to populate.

```yaml
document_date: "YYYY-MM-DD"   # REQUIRED. Meeting date. MUST match the YYYY-MM-DD
                               # prefix of the filename exactly. The filename prefix is
                               # the authoritative valid-time anchor.
is_latest_version: true        # REQUIRED. Nearly always true for meetings.
                               # Flip to false only when a re-run meeting's debrief
                               # explicitly retires this note.
```

---

#### type: decision — Full bitemporal split (5 required)

Decisions use the **full** bitemporal split because they have an effective date
(valid-time start) that can differ from the recording date. This enables the
point-in-time query pattern: "what decision was in force on date X?"

```yaml
document_date: "YYYY-MM-DD"   # REQUIRED. Transaction-time of recording — when the
                               # decision was authored in the system.
effective_date: "YYYY-MM-DD"  # REQUIRED. Valid-time start — when the decision applies
                               # in the world. Three cases:
                               #   pre-dates document_date  → retroactive / back-dated
                               #   post-dates document_date → scheduled future cutover
                               #   equals document_date     → "decided and effective now"
superseded_by: ""              # REQUIRED. [[WikilinkToSuccessor]] when superseded;
                               # empty string ("") while current.
superseded_date: ""            # REQUIRED. ISO date the supersession was RECORDED
                               # (transaction-time of the supersession event itself).
                               # NOT the successor's effective_date — those are different
                               # dates and must not be conflated. Empty while current.
previous_version: ""           # REQUIRED. [[WikilinkToPredecessor]] in the linear chain;
                               # empty string ("") for the chain's first entry.
                               # Distinct from `replaces:` (which is a list, for decisions
                               # that collapse multiple predecessors into one).
```

**Point-in-time query pattern** — "what decision was in force on date X?":
```
effective_date <= X  AND  (superseded_date > X  OR  superseded_date == "")
```

**Two-clock model for decisions:**

| Field | Clock | Notes |
|-------|-------|-------|
| `document_date` | Transaction-time | When the decision was recorded in the system |
| `effective_date` | Valid-time start | When the decision became operative in the world |
| `superseded_date` | Transaction-time | When supersession was recorded — NOT successor's effective_date |

---

### Per-type required-field summary

| Field | `source` | `meeting` | `decision` | Notes |
|-------|----------|-----------|------------|-------|
| `name` | ✓ | ✓ | ✓ | Human-readable |
| `description` | ✓ | ✓ | ✓ | One sentence |
| `type` | ✓ | ✓ | ✓ | Closed vocabulary |
| `last_updated` | ✓ | ✓ | ✓ | File mtime (transaction-time) |
| `document_date` | ✓ | ✓ | ✓ | Content date (valid-time) |
| `is_latest_version` | ✓ | ✓ | — | Route A filter |
| `effective_date` | — | — | ✓ | Valid-time start |
| `superseded_by` | — | — | ✓ | Chain forward link |
| `superseded_date` | — | — | ✓ | Supersession transaction-time |
| `previous_version` | — | — | ✓ | Chain backward link |

Templates for all types: `90 System/Templates/`. Bitemporal templates are in
`references/templates.md`.

---

### Optional epistemic fields — confidence + stale (added 2026-05-14)

Two optional fields extend P-4 to make epistemic state explicit. Both are
**enforced when present** (the verifier validates ranges and enums) but neither
is required — absent = pass. Verifier constants: `CONFIDENCE_TYPES`,
`STALE_VALID_VALUES` in `bases-verifier.py`.

#### `confidence:` — float 0.0–1.0

Applicable to `type:` ∈ `{source, decision, meeting, concept}`. Rubric:

| Value | Tier | Meaning |
|-------|------|---------|
| `1.0` | Direct primary | Authored in-vault or quoted verbatim from an extracted primary artefact (audit, signed decision, transcript). |
| `0.7` | Corroborated secondary | Extracted or summarised from one or more primary sources; cross-checked. |
| `0.4` | Single-source secondary | Single-source extraction or single-pass summary; useful but uncorroborated. |
| `0.2` | Speculation / inference | Inferred, hypothesised, or speculative — flag for verification before action. |

Surface low-confidence content via `Low Confidence.base` (filter `confidence < 0.5
AND is_latest_version: true`). Backfill at ingestion time when feasible — the
`source_type → confidence` heuristic table belongs in the project's
`_audit_confidence_calibration_*.md` workpaper.

#### `stale:` — tri-state enum

Applicable to any typed note. Valid values:

| Value | Meaning |
|-------|---------|
| `pending` | Flagged stale by lint (e.g. `propagate_stale.py`) but not yet adjudicated by a human. |
| `confirmed` | Reviewed by a human and confirmed stale — citing notes need updating. |
| `cleared` | Reviewed by a human and confirmed still valid despite a triggering supersession event. |

Surface via `Open Items.base` → "Stale Flagged (pending + confirmed)" view.
Tri-state lifecycle is: absent → `pending` (lint flag) → `confirmed` or `cleared`
(human action). When `cleared`, the field MAY be removed entirely once the
triggering condition is no longer relevant.

#### How they interact with lint

The optional fields exist primarily as **lint outputs and human adjudication
inputs**. The Karpathy lint suite (`audit_contradictions.py`, `audit_orphans.py`,
`propagate_stale.py`) writes proposals that recommend setting `stale: pending`;
human review then sets `confirmed` or `cleared`. `confidence` is set at authoring
or backfilled from the calibration heuristic; lint scripts MAY use it as a tie-
breaker but do not set it.

---

**Why.** Frontmatter is the structural index. Without `type:`, Bases (step 2) cannot
filter. Without `document_date`, temporal Bases (Routes A/B/C) return incorrect or
empty results. Without `is_latest_version` / `superseded_by`, "current" queries cannot
be answered without a full-text scan. `confidence` + `stale` make epistemic state
visible to retrieval and surface degradation through the Karpathy lint loop. The
verifier detects schema drift before it corrupts retrieval.

**How to apply.** Before writing any typed-zone file, populate the four base keys plus
the temporal fields for the file's type. Do not invent new `type:` values without
updating the verifier and Bases schemas simultaneously. `confidence` is set at
authoring per the rubric; `stale` is set by lint then adjudicated by humans.

**Cross-references.** `90 System/Templates/`; `90 System/_bases_verifier.py`;
`90 System/Bases/` (especially `Latest Only.base`, `As Of.base`, `Version Chain.base`,
`Low Confidence.base`, `Open Items.base` "Stale Flagged" view); P-3 temporal routing
matrix (Step −1, Routes A/B/C); `references/lint-contradictions.md`,
`lint-orphans.md`, `lint-stale.md` for the lint surface that produces `stale:` values.
---

## P-6 — Memory landscape

**Rule.** Memory in this vault has four discrete surfaces. Know which one you are
reading from and writing to — writing the wrong content to the wrong surface
corrupts both.

- **Vault content** (typed zones: `10 People/`, `20 Companies/`, `30 Projects/`,
  `40 Meetings/`, `50 Sources/`, `60 Concepts/`, `70 Decisions/`, `90 System/`).
  Durable, structured, retrieval-cascade-indexed. The primary substrate. Anything
  that needs to survive across sessions and be retrievable belongs here, promoted
  via P-10.
- **Working memory** (`99 Workspace/_session_handoff.md` and the state MOC —
  EXT-2). Live state for the current session and project phase. Replaced
  (handoff) or evolved (state MOC) every session. Read first, written last.
- **Forensic memory** (`99 Workspace/_session_handoff_archive/`,
  `99 Workspace/_auto_writes.md`, `99 Workspace/_cleanup_log.md`,
  `99 Workspace/_reflection_log.md`). Append-only, immutable. The audit surface.
  Used to reconstruct what happened weeks ago when the live handoff has long
  since rotated.
- **Cross-project memory** (auto-memory —
  `~/Library/Application Support/Claude/.../memory/`, MEMORY.md + per-fact
  files). Persists across vaults and projects. User profile, durable feedback
  rules, references to external systems. Updated with discretion — small and
  global.

These are **not** redundant. The vault is for facts and structured content; the
working memory is for live state; the forensic memory is for audit; the
cross-project memory is for things that outlive the vault.

**Precedence rule.** When in-context vault facts conflict with cross-project
auto-memory, **in-context wins**. Auto-memory is reference, not authority — it
carries no vault-specific audit trail, no per-section freshness markers, and no
Bases-backed verification. When a conflict is detected: (a) note it, (b) apply
the vault's version, (c) flag the auto-memory entry for update at the next
`consolidate-memory` ritual.

**Why.** Without a memory landscape rule, two failure modes recur: (a) durable
content gets written to the handoff and lost when the handoff is replaced;
(b) ephemeral session state leaks into typed zones, bloating the vault with
stale detritus and corrupting Bases views. The four-surface model gives an
explicit answer to "where does this go?"

**How to apply.** When writing, ask "where does this belong six months from
now?" — "nowhere → irrelevant" → working memory at most, only if it influences
the next session. "In a typed zone" → write to `99 Workspace/` first, propose
P-10 promotion. "Audit trail only" → forensic memory (`_auto_writes.md` line,
archive entry). "Across projects" → auto-memory after the `consolidate-memory`
ritual. When reading, ask "which surface am I querying?" Do not search the
archive for live state; do not consult auto-memory for project-specific facts.

**Cross-references.** `.claude/rules/session-bootstrap-discipline.md` enforces
this rule as an always-on session-start checklist with the 30-second
orientation requirement and skippable-when criteria. Also `99 Workspace/_session_handoff.md` and
`_session_handoff_archive/`; `99 Workspace/_auto_writes.md`, `_cleanup_log.md`;
`99 Workspace/_reflection_log.md` and `_lessons.md` (P-12 forward-ref);
P-7 (auto-write zone discipline); P-10 (promotion ritual);
P-12 (learning surface — forensic → lesson path);
EXT-5 (session bootstrap — when to read which surface).

---

## P-7 — Autonomy boundary (write zones and auto-write logging)

**Rule.** Three **auto-write zones** (write OK, log required); everything else is
**trigger-only** (no write without explicit user authorisation).

**Auto-write zones:**
- `00 Inbox/` — quick-capture untyped notes
- `80 Daily/` — daily notes
- `99 Workspace/` — session outputs, audits, drafts, logs

**Trigger-only zones:**
- All typed content zones: `10 People/`, `20 Companies/`, `30 Projects/`,
  `40 Meetings/`, `50 Sources/`, `60 Concepts/`, `70 Decisions/`
- `90 System/` — operating discipline, eval, scripts, Bases, Templates
- Special files: `CLAUDE.md`; state MOC (EXT-2); `99 Workspace/_session_handoff.md`

**Auto-write logging.** Every auto-write → one line in `99 Workspace/_auto_writes.md`:
```
YYYY-MM-DD | verb | path | one-line reason
```
Verbs: `write`, `edit`, `rename`, `note`, `delete`. Append-only. If >5 writes this
session, propose `kb-curator refresh-index`.

**State MOC and CLAUDE.md edits do not log to `_auto_writes.md`** — they surface
in the next session handoff instead.

**OS-junk delete carve-out.** `.~lock.*`, `~$*`, `.DS_Store`, `Thumbs.db`, `*.tmp`
may be deleted without per-file authorisation — provided deletion is logged with
verb `delete`. Real artefacts remain "no deletes — moves only, after approval".

**Why.** The cost of a wrong auto-write (corrupts retrieval, breaks Bases, requires
manual reconciliation) vastly exceeds the cost of one false-stop conversation.

**How to apply.** Before any write, identify the target zone. If not in the three
auto-write zones, stop and ask. After every auto-write, log it.

**Cross-references.** `99 Workspace/_auto_writes.md`; `99 Workspace/_cleanup_log.md`;
P-10 (promotion ritual — the path from auto-write zone into typed zones); EXT-5
(write-audit scheduled task).

---

## P-8 — Eval and measurement

**Rule.** The vault's behavioural rules are falsifiable through a recurring
**retrieval eval**. Eval set: `90 System/_eval_retrieval.md` — questions tagged
by cascade step, scored on two binary dimensions: **Supersession-correct (S)** and
**Retrieval-complete (X)**. Pass bar: **≥80% on each dimension**. Cadence:
**monthly**, surfaced by the `{{PROJECT_SLUG}}-eval-recency` scheduled task (EXT-5).

A faster **smoke-test** (`90 System/_smoke_test_retrieval.py`) gates every plugin
update from "provisional" to "accepted" (P-11).

**Banner-level alert.** If the last eval is >30 days old, surface as **first line**
of session orientation:
> **EVAL DUE — last baseline is [N] days old (≥30). Run
> `90 System/_eval_retrieval.md` before substantive new work this session.**

**Why.** Three failure modes the eval catches: (1) silent retrieval drift — Smart
Connections re-embeds and recall degrades without any signal; (2) concealed misses
— P-3 violations look identical to genuine dead ends from the outside; (3) step-
level blind spots — aggregate scores stay green while one cascade step silently
dies.

**How to apply.**
- **At vault creation.** Run eval after first Smart Connections indexing. Record
  baseline at `99 Workspace/_eval_baseline_{{YYYY-MM-DD}}.md`. Vault is not
  load-bearing until this baseline is green.
- **Monthly.** Walk all questions, score S and X. Root-cause sweep if below 80%.
  Never repair the eval by changing question phrasing — the eval set has its own
  maintenance rules.
- **After plugin updates.** Smoke-test gates the update; full eval not required.

**Cross-references.** `90 System/_eval_retrieval.md`; `90 System/_smoke_test_retrieval.py`;
`99 Workspace/_eval_baseline_*.md`; EXT-5 (eval-recency task); P-11 (smoke-test
is the plugin update gate); P-3 (what the eval scores).

---

## P-10 — Promotion ritual (99 Workspace/ → typed zones)

**Rule.** Content reaches typed zones **only via the P-10 promotion ritual** —
never directly from session work. (Exception: direct trigger-authored writes bypass
the ritual.)

**The ritual:**
1. **Propose.** Claude produces a candidate move list from `99 Workspace/` to typed
   zones, with target path and rationale. Output: `99 Workspace/_cleanup_proposal_{{YYYY-MM-DD}}.md`.
2. **Quality-filter each row.** Three questions:
   - *Is this still true?* (vs state MOC and recent context)
   - *Will this affect tomorrow's decisions?*
   - *Is this encoded elsewhere?* (duplicate check)
   If any answer is "no" or "duplicate" → move row to archive section. Do not
   silently drop rows.
3. **Approve.** User reviews the filtered proposal. Acceptance is explicit.
4. **Execute.** Move files; update frontmatter; repair wikilinks pointing at old
   `99 Workspace/` paths.
5. **Log.** Batch entry in `99 Workspace/_cleanup_log.md` — date, sources, targets,
   filter outcomes, reference-repair count.

**Optional step 6 — Verify.** For high-stakes content, spawn a verification sub-
agent before approval.

**Trigger.** Run when: auto-write count exceeds 5 in a session; a workspace block
looks "complete enough"; a full meeting debrief + analysis has settled.

**Why.** Without the ritual: bloat-by-accumulation (workspace files become silently
load-bearing without entering Bases) OR premature codification (typed zones fill
with churn). The three-question filter is the cheap fix in both directions.

**How to apply.** Filter aggressively — the default outcome is "archive instead"
or "skip — duplicate". Update wikilinks at execution time.

**Cross-references.** `90 System/_promotion_quality_guide.md`; `99 Workspace/_cleanup_log.md`;
P-4 (frontmatter at execution); P-7 (auto-write boundary the ritual exits); P-12
(parallel ritual shape for lessons).

---

## P-11 — Plugin security and substrate hygiene

**Rule.** The Obsidian community-plugins surface is treated as a small, audited,
**whitelisted** dependency. The whitelist for any vault scaffolded by this skill
is exactly `["smart-connections"]`. Bases is exempt — it is a CORE plugin
shipped with Obsidian. Three load-bearing disciplines:

- **No new plugin install without an explicit user trigger.** Adding any plugin
  requires (a) a security audit (purpose, permissions, vendor, licence, version,
  hash), (b) explicit user decision on the audit, (c) hash-baseline refresh. The
  whitelist is closed; extending it is structural.
- **Plugin updates are gated by the M11 smoke-test.** Smart Connections is
  **pinned at the version installed at bootstrap** — record as
  `[FILL: vX.Y.Z at bootstrap]` in `90 System/_plugin_security.md`. Auto-update
  is OFF (the Obsidian default). Before any update: tarball the existing
  `.obsidian/plugins/smart-connections/`. After any update: run
  `90 System/_smoke_test_retrieval.py`. Pass → update accepted, log the outcome.
  Fail → restore the tarball, log the failure.
- **Weekly hash-check is a tripwire.** The `{{PROJECT_SLUG}}-health` scheduled
  task (EXT-5) computes the SHA-256 of `.obsidian/plugins/` and compares against
  `99 Workspace/_plugin_hash_baseline.txt`.

  ```bash
  # Capture at bootstrap (run from .obsidian/):
  find plugins -type f -exec sha256sum {} \; | sort -k2 | sha256sum
  ```

  Record the result as the baseline. Any drift not preceded by a logged manual
  update writes `99 Workspace/_audit_<YYYY-MM-DD>_plugin_drift.md` and surfaces
  at next session start.

**Multilingual caveat.** If the project's primary language is not English,
document the embedding model's degradation threshold for that language and set
the P-3 Step 1 fall-through rule: skip semantic search for non-English queries,
fall through to Step 2 directly. Record model and threshold here and in
`90 System/_retrieval_contract.md`.

**Why.** The vault's substrate stack is intentionally small — Obsidian + Bases
+ Smart Connections. The threat model is narrow: supply-chain compromise of
Smart Connections (the only third-party plugin) would have direct access to
vault content. The pin + hash-check + smoke-test gating are three independent
layers. Whitelist creep is the second threat — plugins are easy to install and
hard to audit retrospectively.

**How to apply.**
- **At session start.** If the prior `{{PROJECT_SLUG}}-health` run flagged hash
  drift, surface it before any other work. Read the drift audit file first.
- **When a new plugin is proposed.** Run the security audit; recommend; let the
  user decide. Refresh the baseline only after explicit acceptance.
- **When Smart Connections shows an available update.** Tarball current; install;
  run the smoke-test; report. Do not auto-accept without logging.

**TODO — complete at bootstrap (one-time setup):**
- [ ] Record Smart Connections version pinned at first install in
      `90 System/_plugin_security.md`
- [ ] Capture SHA-256 baseline: `find .obsidian/plugins -type f -exec sha256sum
      {} \; | sort -k2 | sha256sum` → save to `99 Workspace/_plugin_hash_baseline.txt`
- [ ] Create `90 System/_plugin_security.md` with audit record and version pin
- [ ] Confirm `{{PROJECT_SLUG}}-health` task is configured (per EXT-5)
- [ ] If non-English project: fill the multilingual caveat above

**Cross-references.** `.claude/rules/plugin-security-discipline.md`;
`90 System/_plugin_security.md`; `90 System/_smoke_test_retrieval.py` (M11 gate,
from P-8); `99 Workspace/_plugin_hash_baseline.txt`; P-8 (eval framework —
smoke-test is the M11 gate); EXT-13 (T+180 substrate review re-evaluates this
rule's premises).

---

## P-12 — Reflection and lessons (the learning surface)

**Rule.** Two-tier learning surface. Both files created **lazily on first use**.

**Tier 1 — `99 Workspace/_reflection_log.md`** (append-only, auto-write OK).
Single-occurrence learning events. Format:
```markdown
## YYYY-MM-DD — [one-line title]
**What happened.** [Description]
**Why it matters.** [Why worth recording]
**Triggers next time:** [If the pattern is concrete enough — omit if not]
```

**Tier 2 — `99 Workspace/_lessons.md`** (durable rules). Promoted from
`_reflection_log.md` via `kb-curator promote-lesson` when a reflection has
applied at least **twice**. Entry: rule statement, **Why:**, **How to apply:**.

**Applied-twice threshold** is the rate-limiter: a reflection becomes a lesson
only after a second application. Prevents premature codification of one-off
observations into permanent rules.

**Promotion path.** Vault lesson that applies a third time → candidate for cross-
project auto-memory. Direction always **vault → auto-memory**, never the reverse.

**Why.** Without the reflection log, observations land in handoffs and rotate out.
Without the applied-twice threshold, the vault accumulates contradictory low-
confidence rules. Without the lessons file, genuinely useful patterns are lost.

**How to apply.** Something surprises you mid-session → append to
`_reflection_log.md` immediately. At session start/end → scan for entries that
just applied for the second time; those are promotion candidates.

**Cross-references.** `99 Workspace/_reflection_log.md`; `99 Workspace/_lessons.md`;
P-7 (auto-write zone); P-10 (parallel ritual shape); P-6 (cross-project memory
promotion path).

---

## Extension Slots — Project-Specific Rules

Four P-rules could not be shipped as universal kernel rules because their content
is inherently project-specific. Each slot documents the **failure mode** of
skipping it and a **TODO checklist**. An unfilled slot is a documented gap, not
a violation.

*Search `[EXTENSION SLOT]` to find all stubs in one pass.*

---

### EXT-2 — State MOC [EXTENSION SLOT]

**Failure mode if skipped.** Live project state has no canonical home. Session
handoffs bloat carrying what a state MOC should hold. Retrieval step 4 cannot
navigate effectively. Every session reconstructs context from the handoff archive.

**What to define.** One source-of-truth file for live project state with anchored
section vocabulary, per-section `Last touched: YYYY-MM-DD` markers, and a
freshness threshold.

**Minimum viable.** One file in `30 Projects/` with 2–3 anchored section types
and `Last touched:` markers. Complexity grows with the project.

**[EXAMPLE — a mature state MOC from a reference implementation]** A real
project's `30 Projects/<state-moc-slug>.md` evolved to 5 anchored types
(`## Concept:` / `## Workstream:` / `## Counterparty:` / `## Decision:` /
`## Archive:`), 14-day freshness threshold, ~839 lines at project maturity.
Yours will likely look different — pick anchored types that match your domain
(e.g. for a sales project: `## Account:` / `## Stage:` / `## Decision:`).

**TODO — this project must decide:**
- [ ] State MOC file path (suggested: `30 Projects/{{PROJECT_SLUG}}.md`)
- [ ] Anchored section vocabulary for this domain
- [ ] Freshness threshold (days before a section is stale)
- [ ] Edit discipline: does editing the state MOC log to `_auto_writes.md`?
- [ ] Does `CLAUDE.md` Session Bootstrap section point to this file?

---

### EXT-5 — Session lifecycle [EXTENSION SLOT]

**Failure mode if skipped.** No bootstrap/handoff discipline. Sessions start cold.
State compacts away. Open threads drop. Maintenance drift (stale eval, log bloat,
index rot) goes undetected.

**What to define.** Bootstrap sequence; handoff artefacts; scheduled maintenance
tasks.

**Minimum viable bootstrap sequence** (adapt; fill in project-specific files):

1. **Mount check.** Verify the canonical vault folder is mounted; hard-stop on any
   unexpected similarly-named folder at mount root.
2. **Read `99 Workspace/_session_handoff.md`** for last session context. Run three
   sanity checks: (a) date consistency with archive, (b) file-list consistency,
   (c) maintenance-flag currency. Any mismatch → flag to user before starting work.
3. **Read this operating guide** when the task is non-trivial.
4. **Open today's daily note** `80 Daily/YYYY-MM-DD.md`; create stub if missing.
4.5. **Read `_plans_index.md`** at vault root. Identify the canonical (un-archived)
   plan — the one NOT marked archived / superseded. Read its **Operating Manual**
   section at the top of the HTML file and the **Up Next session card** (the first
   session article whose `data-status` is not DONE). Skip silently if no plan is
   in progress.

   *Why step 4.5 matters.* Cold-session multi-session work loses continuity without
   this: the live handoff carries one session of context; the plan's Operating Manual
   carries the full arc — decisions made, constraints, what "done" looks like for the
   entire programme. The Up Next card is the single authoritative prompt for the next
   session. This is the "load the active plan at bootstrap" discipline.
5. **Check Open Items Base** `90 System/Bases/Open Items.base` for at-a-glance
   state across People, Companies, Projects, and Decisions.
6. **Smart Connections health.** `mcp__smart-connections__stats`. Flag if index
   is >7 days stale or source-count drift >2%.
7. **Check prior handoff for next-session triggers** — consolidation backlog, eval
   re-run due, log rotation pending. Surface before starting new work.

Then give a 30-second orientation: last session date, what was worked on, open
threads, next actions.

**⚠ Banner-level eval alert (required, from P-8).** If `{{PROJECT_SLUG}}-eval-recency`
signals that the last eval is >30 days old, surface as the **first line** of the
orientation — before any other content:
> **EVAL DUE — last baseline is [N] days old (≥30). Run the eval before substantive
> new work this session.**

**Handoff artefacts (three, each session end):**
- Live handoff at `99 Workspace/_session_handoff.md` (target ≤15 KB; 3-strike
  compression at consecutive >15 KB sessions per `freshness-discipline.md`).
- Archive entry at `99 Workspace/_session_handoff_archive/YYYY-MM-DDTHHMM_<descriptor>.md`
  (append-only, immutable forensic record).
- Daily note `80 Daily/YYYY-MM-DD.md` updated with `## Session Summary` link to archive.

**[EXAMPLE — reference implementation P-5]** A mature project's bootstrap has 7
steps: (1) mount check, (2) read `_hot.md` + `_session_handoff.md` + 3 sanity
checks, (3) read operating guide on non-trivial work, (4) open today's daily
note, (4.5) read `_plans_index.md` and load the canonical plan's Operating
Manual + Up Next card, (4.6) read `_index.md` (vault content catalog, top 100
lines) — regenerate if stale, (5) glance at `Open Items.base`, (6) Smart
Connections health, (7) check prior handoff for next-session triggers. The
matching maintenance family is 5 scheduled tasks
(handoff-freshness / write-audit / health / eval-recency / log-rotation).

**TODO — this project must decide:**
- [ ] Full bootstrap sequence (confirm which specific files to read at session start)
- [ ] `_plans_index.md` path and plan file format (step 4.5 assumes plan-builder HTML)
- [ ] Handoff size target and compression trigger ([EXAMPLE: ≤15 KB, 3-strike rule])
- [ ] Maintenance task names: `{{PROJECT_SLUG}}-handoff-freshness`, `{{PROJECT_SLUG}}-write-audit`, `{{PROJECT_SLUG}}-health`, `{{PROJECT_SLUG}}-eval-recency`, `{{PROJECT_SLUG}}-log-rotation`
- [ ] Session start sanity checks specific to this project
- [ ] Banner-level alerts beyond the P-8 eval alert

---

### EXT-9 — Lifecycle triggers [EXTENSION SLOT]

**Failure mode if skipped.** No explicit "what happens when this project ends?" —
accumulates indefinitely; canonical paths rot; substrate never re-evaluated.

**What to define.** Named lifecycle triggers with invocation conditions, action
checklists, and durable record format.

**Minimum viable.** One `close-project` trigger: what to archive, persist,
decommission. Each trigger is **explicit user invocation only** — Claude never
auto-fires. Each produces a dated audit file in `99 Workspace/`.

**[EXAMPLE — reference implementation P-9]** A reference project defined three
triggers (`freeze canonical`, `rollback move`, `substrate review`) — each with
explicit conditions, an action checklist, and a durable audit-record path.
Your project's triggers may differ; the load-bearing requirement is that they
exist and are explicit.

**TODO — this project must decide:**
- [ ] Does this project have a known end date or decommission timeline?
- [ ] `close-project` trigger checklist
- [ ] Rollback scenario (would you ever undo the vault setup?)
- [ ] Substrate review schedule (see EXT-13)

---

### EXT-13 — Substrate review [EXTENSION SLOT]

**Failure mode if skipped.** Substrate calcification — migration cost rises
monotonically; substrate choice never re-tested. Alternatively: reactive migration
under pressure when a plugin is abandoned or Obsidian breaks.

**Three standard questions for Obsidian + Smart Connections + Bases:**
1. **Bases stable?** Verifier clean; no significant workarounds; step 2 hit on
   >20% of eval questions where tagged primary.
2. **Smart Connections maintained?** Vendor active (releases in last 6 months);
   model unchanged or upgraded with smoke-test green; multilingual fall-through
   premise still valid.
3. **Obsidian competitive?** No substrate emerged that would obviously displace
   this stack (half-day pilot would show clear gains).

**2-of-3 negative** → produce migration plan sketch (not an immediate migration).
**0-or-1 negative** → stay; file action list; schedule next review at T+next-interval.

**[EXAMPLE — reference cadence]** A reference project sets the first substrate
review at T+180 from bootstrap, with annual reviews thereafter.

**TODO — this project must decide:**
- [ ] First review date (suggested: T+180 from bootstrap = {{DATE_PLUS_180}})
- [ ] Any project-specific modifications to the three standard questions?
- [ ] Review record path: `99 Workspace/_substrate_review_{{YYYY-MM-DD}}.md`


---

## Conflict resolution

Bump `last_updated:` in frontmatter on every body edit.

**Precedence (highest to lowest):**
1. `.claude/rules/` files — auto-loaded, sharper operational edge. Win for their specific scope. Any conflict signals this guide has drifted.
2. This guide — wins for behaviour over `CLAUDE.md`.
3. `CLAUDE.md` — wins for facts over this guide.

Surface all conflicts in the session handoff. Do not resolve silently.
