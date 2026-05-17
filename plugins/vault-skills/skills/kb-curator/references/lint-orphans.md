# lint-orphans — design spec (KP-03)

Karpathy LLM-Wiki Lint Mode 2. Surface notes nobody links to and no
Base surfaces — "is this page reachable from anywhere a human would
actually start reading?" If the answer is no, the note is either
(a) underused (needs a link from an MOC), (b) misfiled (wrong zone or
wrong type), or (c) ready for archive. Proposal-only output, never
auto-moves. Wires into kb-curator as a standalone mode
(`audit-orphans`) and — once the FP rate is characterised — the 5th or
6th chained script in OBSIDIAN audit mode (after lint-contradictions).

Authored: 2026-05-14 (Framework Remediation S03 / KP-03).
Status: design + reference impl shipped at
`.claude/skills/kb-curator/scripts/audit_orphans.py`.

## Why this mode exists

A vault accumulates notes faster than humans can hand-curate the
wikilink graph. Once the typed-zone count crosses ~500 .md files (Galp
Vault is at 769 .md / 484 in `50 Sources/` alone as of 2026-05-14),
some notes are reachable from the MOC, some are reachable only via
Bases (which list every note matching a type filter), and some are
reachable from neither. The third bucket is the orphan list.

Note: "orphan" here is the *retrieval-graph* sense — invisible to
both wikilink expansion (cascade Step 3) and Bases (cascade Step 2).
A note that is type-bound and Base-surfaced is NEVER an orphan even if
no wikilink points to it; Bases is a first-class retrieval surface in
this vault (`90 System/Bases/`, cascade P-3 step 2).

The lint runs as a P-8 measurement: orphan counts are recorded so
graph-disconnect debt can be tracked over time, the same way
`audit_bitemporal.py` tracks P-4 conformance and `audit_contradictions.py`
tracks contradiction debt.

## Reachability model

A note is **reachable** iff at least one of:

1. **Wikilink-reachable.** BFS over the wikilink graph from the
   entry-point set terminates at the note.
2. **Base-reachable.** The note's `type:` (after closed-vocabulary
   filtering per `_bases_verifier.py` KNOWN_TYPES) binds to at least
   one primary `.base` filter, so it would surface in that Base's
   default view.
3. **Allow-listed by type.** Its type is in the Bases-unbound
   allow-list (lifted from `_bases_verifier.py` BASES_UNBOUND_TYPES);
   these types are valid but never bound to a Base by design
   (inbox / daily / log / handoff / handoff_archive / system / contract /
   guide / eval / template / base / concept). Notes of these types
   are NEVER orphans.

Anything else is an **orphan candidate**.

## Entry-point set (BFS seeds)

The wikilink BFS starts from these seeds. The set is intentionally
small — orphan detection is sharp only if the seeds are exactly the
notes a human would treat as a "front door" to the vault.

| Seed                                          | Why                                                                                          |
|-----------------------------------------------|----------------------------------------------------------------------------------------------|
| `CLAUDE.md`                                   | Stable prefix — top of every session bootstrap. Includes wikilinks to roster / glossary / state MOC. |
| `30 Projects/Peninsula.md` (state MOC)        | Canonical project state file. Wikilinks out to every active counterparty / workstream / decision. |
| `30 Projects/*.md` (all project notes)        | Every typed `project` note is a per-project MOC (e.g. RemainCo IT Strategy).                 |
| `_plans_index.md` (vault root)                | Plans registry — wikilinks to every active and archived plan dashboard HTML.                 |
| `99 Workspace/_session_handoff.md` (live)     | Live handoff — wikilinks to currently-active archive arcs and decision pointers.             |
| `60 Concepts/*.md` (every concept page)       | Concept pages are mini-MOCs by convention; e.g. `Ulysses.md`, `shERPa.md` resolve domain vocabulary. |
| `20 Companies/*.md` (every company page)      | Company pages link out to all their people and to project pages. Treating them as seeds rather than expanded-only nodes avoids one-link-distance fragility. |

Why these and no others:

- The handoff archive is NOT a seed (only the live handoff). Old
  archive arcs are append-only forensic records; they should not
  rescue stale notes by mere historical mention.
- `40 Meetings/` and `50 Sources/` and `70 Decisions/` are NOT seeds.
  Meetings/sources/decisions need to be *linked from* an MOC or
  concept page to count as reachable — that's exactly the test.
- `10 People/` is NOT a seed. People are linked from project,
  meeting, and company pages. A person nobody mentions anywhere is
  legitimately orphan (e.g. a person added speculatively and never
  used).
- `00 Inbox/` is NOT a seed. Inbox notes are by definition transient.
  They are reached from nothing and reach nothing.

## BFS expansion rules

From each seed, follow every `[[Target]]` (or `[[Target|Alias]]`,
`[[Path/Target]]`, `[[Target#Section]]`) in:

- The note's frontmatter (any field — be permissive, the orphan check
  is the OPPOSITE problem from the Bases verifier's "free-form fields
  shouldn't be scanned for outbound links").
- The note's body (every `[[...]]`).

Resolution rules (mirror `_bases_verifier.py` `resolve_wikilink`):

1. Strip `|alias` and `#section` suffixes.
2. If `/` is present, take the basename (last path component).
3. Match against:
   - filename stems (basename match), vault-wide;
   - aliases declared in any note's `aliases:` frontmatter list.
4. Case-sensitive (Obsidian's default). Unresolved links are silently
   dropped from the BFS (the wikilink-orphan check is a separate
   audit, owned by `_bases_verifier.py`).

The BFS terminates when the queue empties — typical termination is
fast (the vault is small enough that the entire reachable set
materialises in seconds).

## Reachable-via-Base rule

After the BFS terminates, mark every note as **also reachable** if its
`type:` value binds to a primary Base (not view-only). The primary
Bases as of 2026-05-14:

- `People.base` -> type:person
- `Companies.base` -> type:company
- `Projects.base` -> type:project
- `Meetings.base` -> type:meeting
- `Sources.base` -> type:source
- `Decisions.base` -> type:decision

View-only Bases (`Open Items.base`, `Tier-2 Sources.base`,
`Latest Only.base`, `As Of.base`, `Version Chain.base`,
`Ingested Sources.base`) do NOT contribute to base-reachability —
they filter or span a subset, never define a type's home.

The script reads the live Bases via the existing `_bases_verifier.py`
classifier (`_is_view_only_filter`) so any new primary Base is picked
up automatically — no hardcoded list.

## Expected-empty allow-list

Lifted verbatim from `_bases_verifier.py` `BASES_UNBOUND_TYPES`:

```
inbox / daily / log / handoff / handoff_archive / system /
contract / guide / eval / template / base / concept
```

A note typed with any of these is never orphan-flagged. Rationale: by
design these types are not surfaced via a `.base` and are not expected
to be wikilinked into. They have other lifecycles (rotation, archive,
schedule, etc.). The single source-of-truth is the Bases verifier
constant; if it is updated to add or remove an entry the orphan lint
inherits the change.

`concept` is on the allow-list because concept pages serve as MOCs and
are themselves seeds (above). A concept page that no other note links
*to* is still useful as a reference page.

## Exclusion paths

Even before reachability is computed, the following paths are removed
from the candidate set entirely:

| Path glob                              | Why                                                                                          |
|----------------------------------------|----------------------------------------------------------------------------------------------|
| `_archive/` (any depth)                | Archived material — orphanhood is expected. Lifting it back is a different ritual (P-10).    |
| `_archives/`                           | Alias of `_archive/` used in some subtrees.                                                  |
| `archive/`, `archives/`                | Same as `_archive/` but without the leading underscore — used in `50 Sources/archive/` for version-chain superseded copies. |
| `00 Inbox/_drop/`                      | Ingestion-pipeline binary drop zone — mid-transit, not vault content.                        |
| `80 Daily/`                            | Daily notes are temporal, not graph nodes. They exist to anchor calendar discovery, not as link targets. |
| `99 Workspace/_session_handoff_archive/` | Append-only forensic archive of past handoffs. Orphanhood is expected once compressed.     |
| `99 Workspace/_auto_writes_archive/`   | Same as above — rotated log archive.                                                         |
| `99 Workspace/_log_archive/`           | Generic log-rotation archive.                                                                |
| `99 Workspace/_skill_packages/`        | Staged `.skill` zip packages — opaque blobs, not graph nodes.                                |
| `90 System/_skill_resources/`          | Skill source trees (canonical templates) — not vault content.                                |
| `90 System/Templates/`                 | Type templates with empty placeholder values by design.                                      |
| `.obsidian/`, `.smart-env/`, `.git/`, `.claude/`, `__pycache__/`, `node_modules/` | Plumbing, never vault content.                                                |
| `_galp_vault_scheduled_tasks_staging/` | Staging folder for scheduled-task SKILL.md files (different schema, not P-4).                |

These dovetail with the Bases verifier's `SKIP_DIRS` plus three vault-
specific extras (`80 Daily/`, `_session_handoff_archive/`,
`_galp_vault_scheduled_tasks_staging/`).

## Output — proposal file

Single Markdown file at:

```
99 Workspace/_lint_orphans_YYYY-MM-DD.md
```

`99 Workspace/` is an auto-write zone — `auto-write-discipline.md`
applies. Proposal-only — never edits or moves the orphan notes.

### Frontmatter

```yaml
---
type: audit
provenance: kb-curator lint-orphans (KP-04 — Karpathy Lint Mode 2)
generated: YYYY-MM-DD
candidates_total: N            # all scanned typed-zone .md files
reached_wikilink: R_wikilink   # number reached via BFS
reached_base: R_base           # number reached via Base type-binding
reached_allowlist: R_allow     # type is in expected-empty allow-list
orphans_total: O               # candidates_total - any-reach - excluded
runtime_seconds: T
entry_points: [CLAUDE.md, 30 Projects/Peninsula.md, _plans_index.md, ...]
allowlist_types: [inbox, daily, log, ...]
---
```

### Body sections

1. **Summary** — totals + runtime breakdown. The same numbers as
   frontmatter for human eyes.
2. **Orphans by type** — grouped table of orphan paths under each
   `type:` value. Within each group, sorted by `last_updated` /
   `document_date` / file mtime ascending (oldest first). Each row
   carries: path / type / last-touched date / suggested action.
3. **Typeless orphans** — notes with no `type:` frontmatter at all
   that fell through to the orphan bucket. Almost always a missing-
   frontmatter bug, not a true orphan; suggested action: triage.
4. **Telemetry** — counts of excluded paths and allow-listed-type
   notes, for the eval to spot-check.

### Suggested action heuristics

The script attaches a one-word suggestion per orphan based on
type + age. The user makes the final call; this is a hint.

| Type            | Age (now - last-touched) | Suggested action                                            |
|-----------------|--------------------------|-------------------------------------------------------------|
| meeting         | >60 days                 | `archive` — meetings are point-in-time; cite where needed.  |
| meeting         | <=60 days                | `link-from-moc` — add a backlink from the relevant project. |
| source          | >120 days                | `archive` — sources stale enough that retrieval is unlikely.|
| source          | <=120 days               | `link-from-moc` — promote the citation into the project page. |
| decision        | any                      | `link-from-moc` — every decision should be reachable from a project. |
| person          | >180 days, no recent meetings | `archive` — speculative person never referenced.       |
| person          | otherwise                | `link-from-moc` — link from at least one project/company/meeting. |
| company         | any                      | `link-from-moc` — companies anchor counterparty pages; should not be orphan. |
| project         | any                      | `review` — project orphan is structurally weird; check seed list. |
| (no type)       | any                      | `triage` — missing or malformed frontmatter; fix the `type:` first. |

The "last-touched" signal is, in order of preference:

1. `last_updated:` frontmatter value (ISO date)
2. `document_date:` frontmatter value (for type:source / type:decision)
3. file mtime via `os.path.getmtime`

## Wiring into kb-curator

**Phase 1 (this session):** standalone script invocable as
`python3 audit_orphans.py --root <vault>`. Not chained into
`audit` mode yet — KP-04 ships the script + first proposal;
integration into the OBSIDIAN audit chain is deferred to a later
session once the false-positive rate is characterised on real-world
re-runs.

**Phase 2 (after 2-3 successful runs):** add to `SKILL.md` Section
"OBSIDIAN audit checks" as check #5 or #6 (alongside lint-
contradictions), running after `audit_plans_index.py`. The audit
chain stays read-only / proposal-only — orphans surface as
proposals, never blocking moves.

## Autonomy boundary (P-7 conformance)

- **Writes to** `99 Workspace/_lint_orphans_YYYY-MM-DD.md` only.
  Auto-write zone; logged per `auto-write-discipline.md`.
- **Reads** all `.md` files outside the exclusion path list.
- **Reads** `90 System/Bases/*.base` to determine primary-Base type
  bindings.
- **Never edits** any orphan note.
- **Never deletes** anything.
- **Never auto-archives** an orphan — proposal-only, Ricardo decides.

## Failure modes

| Mode                                  | Behaviour                                                     |
|---------------------------------------|---------------------------------------------------------------|
| `90 System/Bases/` missing or empty   | Warn + continue — orphan check still runs without base-reach. |
| Malformed `.base` YAML                | Warn + skip that Base — do not crash.                         |
| Cyclic wikilink graph                 | BFS uses a visited set — no infinite loops.                   |
| Unresolved wikilinks in seeds         | Silently dropped from BFS — the wikilink-orphan audit (Bases verifier) is the right tool for that. |
| Very large vault (>10k notes)         | Time complexity is O(N + E) — linear in notes + links. Still seconds. |
| Frontmatter parse failure on a note   | Treat as `type: None` (typeless orphan candidate). Surfaces in the typeless bucket — operator fixes the frontmatter then re-runs. |

## Implementation choice: markdown regex vs Obsidian CLI

**Decision: markdown regex.** Rationale:

- **Obsidian CLI doesn't ship on this machine** without a separate
  install + license activation; the script must be runnable from a
  Cowork session shell or any maintenance task with zero external
  state.
- **The wikilink pattern is well-defined** by Obsidian's syntax;
  the regex used by `_bases_verifier.py` (`WIKILINK_RE`) is already
  battle-tested over the live vault and handles `[[A]]`, `[[A|B]]`,
  `[[A#S]]`, `[[A/B|C]]`. We reuse it verbatim.
- **The Bases verifier already implements** vault-wide basename +
  alias resolution (`build_link_index` + `resolve_wikilink`). The
  orphan lint reuses the same resolver — single source of truth on
  what "resolved" means.
- **Performance** — Python regex over ~770 markdown files is
  ~hundreds of milliseconds, not seconds. Linear walk; no rebuild
  cost on re-run.
- **No dependency on the live Obsidian app** — the lint can run
  headless from a scheduled task, exactly like `audit_bitemporal.py`
  and `audit_contradictions.py`.

The cost is that we do not catch "exotic" link syntax like Obsidian's
embeds (`![[Target]]`) — but those resolve to the same target and the
regex captures them (the `!` is outside the capture group).

## Re-run cadence

Monthly, bundled with the retrieval eval (P-8). Or ad-hoc after any
session that promoted >10 notes into typed zones, or after the
ingestion pipeline goes live (post-S06). Not weekly — orphan churn is
slow.

## Cross-references

- `90 System/_operating_guide.md` — P-3 (cascade), P-4 (typed zones),
  P-7 (autonomy), P-8 (eval).
- `90 System/_bases_verifier.py` — source of truth for KNOWN_TYPES,
  BASES_UNBOUND_TYPES, SKIP_DIRS, wikilink regex, resolver, and
  primary-vs-view-only Base classifier.
- `.claude/rules/auto-write-discipline.md` — logging contract.
- `.claude/skills/kb-curator/SKILL.md` — Phase 0 substrate detection,
  audit chain.
- `.claude/skills/kb-curator/scripts/audit_bitemporal.py` — pattern
  for typed-zone walk, frontmatter parsing.
- `.claude/skills/kb-curator/references/lint-contradictions.md` —
  sibling lint (Mode 1).
- `90 System/Bases/` — 12 Bases (6 primary + 6 view-only).
