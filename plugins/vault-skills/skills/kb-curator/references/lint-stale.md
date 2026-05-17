# lint-stale — design spec (KP-05)

Karpathy LLM-Wiki Lint Mode 3. Detect notes whose *upstream truth has
moved* and surface them as `stale: pending` proposals — never auto-edit
the citing note. Sources of staleness: (a) **hash drift** — the binary
original a note was extracted from now hashes to a different value than
when the note was written, and (b) **bitemporal supersession** — a
`type:source` (or `type:decision`) the note cites has been marked
`is_latest_version: false` or has a populated `superseded_date`.

Authored: 2026-05-14 (Framework Remediation S04 / KP-05).
Status: design + reference impl shipped at
`.claude/skills/kb-curator/scripts/propagate_stale.py`.

## Why this mode exists

Galp Vault has two mechanisms that move truth out from under a citing
note without rewriting the citing note:

1. **The v2 ingestion pipeline** writes per-file SHA-256 into
   `pipeline.sha256` on every ingested `.md`, plus an append-only
   record into `99 Workspace/_ingestion_pipeline/_manifest.jsonl`. When
   a newer version of the same upstream artefact is dropped into
   `00 Inbox/_drop/`, the pipeline emits a new manifest entry, links
   the prior entry via `pipeline.supersedes`, and queues the prior
   `.md` for `is_latest_version: false`. Anything that *cited* the
   prior `.md` does not get notified — that's the gap this lint
   closes.
2. **Bitemporal supersession** (P-4) — manual or pipeline-driven —
   demotes a `type:source` / `type:decision` from `is_latest_version:
   true` to `false` and populates `superseded_date:`. Same
   notification gap.

Without lint-stale, citing notes silently drift: a battleplan that
quotes "the 6-pager v23" reads coherently long after v27 is in force.
The retrieval cascade still returns the battleplan, the citation is
still resolvable, but the underlying claim has moved.

The lint runs as a P-8 measurement — stale-citation count is recorded
the same way `audit_bitemporal.py` records P-4 conformance and
`audit_contradictions.py` records contradiction debt.

## Sources of truth — what we read

### `_manifest.jsonl` (canonical hash -> original-path map)

Per `90 System/_ingestion_contract.md` §9, the manifest is the
authoritative dedup record. Schema (one JSON object per line):

```jsonc
{
  "run_id": "20260513T142233Z-7af9",
  "sha256": "3f2a8b1c.full64hex",           // full SHA-256, not 8-char prefix
  "source_file": "260417_PNSL_Shareholders_Pres_vPreread01.pdf",
  "original_path": "99 Workspace/_originals/a1b2c3d4_<name>",
  "supersession_stem": "pnsl_shareholders_pres",
  "supersedes": ["a1b2c3d4.hashA", "9f8e7d6c.hashB"],
  "extracted_at": "2026-05-13T14:22:33Z",
  "ingested_md_path": "00 Inbox/2026-05-13-pnsl-shareholders-pres.md",
  "extractor": "pdfplumber@0.11.0"
}
```

Operational note (2026-05-14): the manifest at this point in S04 is
**empty** — the v2 pipeline is in dry-run mode, no production ingests
yet. lint-stale must therefore handle an empty manifest gracefully
(return 0 stale candidates and a clear "manifest empty" telemetry
note); it must NOT crash. Real propagation kicks in once go-live (S06,
earliest 2026-05-21) starts producing manifest entries.

### Bitemporal frontmatter (already populated on existing typed notes)

Per P-4 (`90 System/_operating_guide.md`) and §6.2 of the ingestion
contract:

- `document_date: YYYY-MM-DD` — when the document was authored.
- `is_latest_version: true|false` — flips to `false` on supersession.
- `superseded_date: YYYY-MM-DD` — populated on supersession.
- `superseded_by: <basename>` or `pipeline.superseded_by: <sha>` —
  optional pointer.

Source files for the audit pool: every `.md` with `type:source` OR
`type:decision` in the typed zones (10–70), excluding `_archive/`.

## Citation conventions — what we scan in citing notes

The propagation algorithm needs to know how a note "cites" an
upstream source. Galp Vault has multiple co-existing conventions; the
lint must catch all of them.

| Convention | Where | Shape | Notes |
|---|---|---|---|
| **`sources:` list** | frontmatter | `sources: ["[[X]]", "[[Y]]"]` or block-list of `- "[[X]]"` | Forward-looking; the canonical citation field once pipeline goes live. Each entry is a wikilink-shaped basename. |
| **`source_file:` scalar** | frontmatter | `source_file: "<original_filename>"` | Legacy v1 ingest convention — the ingested .md's *own* upstream. Used for self-staleness (this .md is downstream of its own original). |
| **`original_path:` scalar** | frontmatter | `original_path: "<vault-relative-or-absolute>"` | Legacy v1 ingest convention — same role as `source_file`. v2 makes this vault-relative; v1 is absolute. |
| **`pipeline.sha256:` namespaced** | frontmatter | `pipeline.sha256: <64-hex>` | v2 contract. The canonical hash of *this* note's upstream binary. Compared against manifest. |
| **`pipeline.supersedes:` namespaced** | frontmatter | `pipeline.supersedes: [<hash>, ...]` | Set when this note supersedes prior versions. Used as a hint, not a staleness driver. |
| **Body wikilink `[[<basename>]]`** | body | Resolved by basename match | Catches inline citations in battleplans / debriefs that don't use a frontmatter `sources:` field. Lower-precision signal — flag only when paired with a stronger one (see §"Confidence levels"). |

The lint reads all of these. `sources:` is the canonical field going
forward; the rest are bridge support for the existing 277 ingested
files + the ~30 hand-written debriefs and battleplans that cite by
wikilink.

## Algorithm

### Inputs

- Vault root.
- `_manifest.jsonl` (may be empty — graceful no-op).
- All `.md` files outside `_archive/`, `_session_handoff_archive/`,
  `_skill_packages/`, plumbing dirs (same SKIP_DIRS as
  `audit_orphans.py`).

### Step 1 — build the **hash -> state** map from the manifest

Walk the manifest. For each entry record:

```
hash_state[sha256] = {
    "run_id": ...,
    "source_file": ...,
    "original_path": ...,            # vault-relative per v2 contract
    "supersession_stem": ...,
    "extracted_at": ...,
    "ingested_md_path": ...,
    "supersedes": [...prior shas...],
    "is_superseded": False,           # set in step 1b
    "superseded_by_sha": None,        # set in step 1b
}
```

#### 1b — derive `is_superseded`

For each manifest entry with a non-empty `supersedes:` list, mark
every listed prior sha as `is_superseded=True` and back-fill
`superseded_by_sha` with the current entry's sha. This makes the
manifest's supersession graph queryable by hash in O(1).

#### 1c — build the **stem -> latest-hash** map

For supersession-by-stem queries (used when a citing note holds an
`original_path` but no `pipeline.sha256`), build a secondary map:

```
latest_by_stem[stem] = sha256_of_newest_entry_with_that_stem
```

Newest = highest `extracted_at` per the manifest. Used in step 3.b.

### Step 2 — walk the vault, build the citing-note index

For each `.md` under the SKIP_DIRS-filtered walk:

1. Parse frontmatter (top-level scalars + the `sources:` list +
   `pipeline:` namespace).
2. Capture wikilinks from the body.
3. Build a `Citation` record per note:

```
Citation = {
    "path": <vault-relative>,
    "type": <type value or None>,
    "is_latest_version": <bool or None>,
    "last_updated": <date>,
    "frontmatter_sources":     [list of basenames from sources:[]],
    "self_source_file":        <legacy source_file scalar or None>,
    "self_original_path":      <legacy original_path scalar or None>,
    "self_pipeline_sha":       <pipeline.sha256 or None>,
    "self_supersession_stem":  <derived from self_source_file or None>,
    "body_wikilinks":          [list of basenames found in body],
}
```

### Step 3 — apply the three staleness rules

For each citing note, evaluate three independent rules and union the
results.

#### Rule A — **hash drift** on self (the note is itself derived from a binary)

Applies when the note has any of `self_pipeline_sha`,
`self_source_file`, `self_original_path`.

- **Rule A.1 (strong):** `self_pipeline_sha` is set AND that sha
  appears in `hash_state` AND `hash_state[self_pipeline_sha]
  ["is_superseded"]` is True. -> **stale, confidence HIGH**, reason
  `"upstream binary superseded by sha={...}"`.
- **Rule A.2 (medium):** `self_pipeline_sha` is set BUT does NOT
  appear in the manifest. -> **stale, confidence MEDIUM**, reason
  `"sha not in manifest (re-ingested without supersession link, or
  manifest corrupted)"`. Sub-case: manifest is empty -> suppress, this
  is the dry-run state, not a real flag.
- **Rule A.3 (medium):** `self_pipeline_sha` is absent but
  `self_supersession_stem` resolves and `latest_by_stem[stem]` exists
  AND the latest sha for that stem is not the one this note refers to
  (we don't know what sha this note refers to without
  `pipeline.sha256`; so the rule fires only when the citing note has
  a *different* `extracted_at` than the latest manifest entry for that
  stem). -> **stale, confidence MEDIUM**, reason
  `"newer version of stem ingested at {date}"`. This catches the
  legacy 277 ingested files when their stems get re-ingested under v2.

#### Rule B — **bitemporal supersession** on cited sources

For each entry in `frontmatter_sources` (forward-looking field) AND
each `body_wikilinks` entry that resolves to a `type:source` /
`type:decision` note:

- **Rule B.1 (strong):** the cited note has `is_latest_version:
  false`. -> **stale, confidence HIGH**, reason
  `"cited source {basename} is no longer latest"`.
- **Rule B.2 (strong):** the cited note has `superseded_date:` set
  (any value). -> same as B.1.
- **Rule B.3 (low):** the cited note has `is_latest_version:
  true` BUT was last_updated *after* the citing note's
  `last_updated`. -> **stale, confidence LOW**, reason
  `"cited source updated since this note (cite={citing date},
  source={source date})"`. This is a hint, not a hard flag — the
  source may have been amended cosmetically. Default behaviour:
  emit but mark `confidence: low`.

#### Rule C — **transitive supersession** via the manifest's `supersedes:` chain

When a manifest entry is superseded by a newer entry, the
`ingested_md_path` of the OLD entry becomes the upstream of any note
that wikilinks to that `.md`'s basename in its body.

For each citing note, for each body wikilink that resolves to a
basename whose canonical path matches an `ingested_md_path` whose
sha is `is_superseded`:

- **Rule C.1 (medium):** -> **stale, confidence MEDIUM**, reason
  `"body cites {basename}; that file's upstream binary is superseded
  by sha={...}"`.

### Step 4 — confidence levels & dedup

Confidence labels:

- **HIGH** — direct supersession signal (manifest `is_superseded`,
  frontmatter `is_latest_version: false`, frontmatter
  `superseded_date` set).
- **MEDIUM** — indirect signal (sha not in manifest; stem updated;
  transitive supersession via body wikilink).
- **LOW** — temporal hint (cited source updated after citing note,
  but still latest).

Dedup: if the same note matches under multiple rules, retain the
**highest confidence** reason. If two rules tie at HIGH, emit both as
joined reasons.

## Proposal output

Single Markdown file at:

```
99 Workspace/_lint_stale_YYYY-MM-DD.md
```

`99 Workspace/` is auto-write — `auto-write-discipline.md` applies.
Proposal-only — never edits or moves citing notes.

### Frontmatter

```yaml
---
type: audit
provenance: kb-curator lint-stale (KP-06 — Karpathy Lint Mode 3)
generated: YYYY-MM-DD
candidates_total: N             # all citing notes scanned
flagged_high: NH                # confidence HIGH
flagged_medium: NM              # confidence MEDIUM
flagged_low: NL                 # confidence LOW
flagged_total: NT               # NH + NM + NL
manifest_entries: ME            # total manifest lines read
manifest_superseded: MS         # entries marked superseded
runtime_seconds: T
---
```

### Body sections

1. **Summary** — totals + runtime breakdown.
2. **Manifest snapshot** — how many entries, how many superseded,
   how many distinct stems. Read by Ricardo to sanity-check the
   manifest's own health.
3. **Stale by confidence** — three subsections (HIGH / MEDIUM /
   LOW), each a table of `path | rule | reason | suggested
   action`. Sorted within each by `last_updated` ascending.
4. **Stale by rule** — counts per rule (A.1, A.2, A.3, B.1, B.2,
   B.3, C.1) — diagnostic for tuning.
5. **Telemetry** — counts of: notes without frontmatter, notes
   with no citations at all (excluded from candidate count), cited
   basenames unresolved (no matching note in vault), manifest
   empty (true/false).

### Suggested action heuristic

| Confidence | Suggested action |
|---|---|
| HIGH | `update-citation` — refresh the note to point at the new version. |
| MEDIUM | `review` — check whether the upstream actually changed materially or just got re-ingested. |
| LOW | `monitor` — flagged for awareness, no immediate action needed. |

## Wiring into kb-curator

**Phase 1 (this session, KP-06):** standalone script invocable as
`python3 propagate_stale.py --root <vault>`. KP-07 adds the mode to
`SKILL.md` mode table but it stays OUTSIDE the default OBSIDIAN audit
chain — same posture as lint-contradictions and lint-orphans. The
default chain remains the four-script structural audit
(`audit_obsidian.py` -> `audit_bitemporal.py` -> `audit_rules.py` ->
`audit_plans_index.py`). Lint scripts are slower (orphan ~0.5s,
stale similar, contradictions ~10s with Haiku adjudication); chaining
them by default would push every audit into ~12s and trigger
auto-suggest fatigue.

**Phase 2 (after 2-3 successful runs once manifest is live):**
optionally chain lint-stale + lint-orphans after `audit_plans_index.py`
when invoked as `kb-curator audit --with-lint`. The flag is the
auto-suggest gate; default audit stays at 4 scripts. lint-contradictions
stays separate due to Haiku cost.

## Auto-suggest threshold (KP-07)

Trip the auto-suggest when:

- `flagged_high >= 5` — material drift from manifest or supersession
  state; Ricardo should refresh affected citations.
- `flagged_medium >= 20` — substantive review queue; suggests a
  re-ingest cycle or supersession-chain audit.

LOW flags do not trigger auto-suggest. They surface on demand only.

## Autonomy boundary (P-7 conformance)

- **Writes to** `99 Workspace/_lint_stale_YYYY-MM-DD.md` only.
  Auto-write zone; logged per `auto-write-discipline.md`.
- **Reads** `_manifest.jsonl` (read-only — see §9.4 of the ingestion
  contract; manifest is append-only by the pipeline, never edited).
- **Reads** every `.md` outside exclusion paths.
- **Never edits** any citing note. Never updates `stale: pending` in
  a citing note's frontmatter automatically — that's a P-10 typed-
  zone edit, trigger-only.
- **Never deletes** anything.
- **Never resolves the proposal** — Ricardo decides update / review /
  monitor.

## Failure modes

| Mode | Behaviour |
|---|---|
| `_manifest.jsonl` missing | WARN to stderr; treat as empty manifest; rules A & C return 0 candidates; Rule B still runs on bitemporal frontmatter alone. Exit 0. |
| `_manifest.jsonl` empty (0 lines) | INFO to stderr ("manifest empty — pipeline pre-go-live"). All rules run; only Rule B can fire. Exit 0. |
| `_manifest.jsonl` line not JSON-parseable | WARN + skip that line; continue. Telemetry counts malformed lines. |
| Citing note has unparseable frontmatter | Treat as "no citations" — skip from candidate set. Surface count in telemetry. |
| Cited basename resolves to multiple notes (collision) | First-wins per `audit_orphans.py` convention. Telemetry counts collisions. |
| Cited basename does not resolve | Counted in telemetry as "unresolved citation" — that's a separate concern (wikilink integrity), not a staleness flag. Do not emit. |
| Vault has 0 typed-source notes | Rule B returns 0 candidates; rules A and C still run. Exit 0 with "no source pool". |

## Implementation choices

### Manifest read — streaming JSON lines

```python
with open(manifest_path) as f:
    for line_no, raw in enumerate(f, 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError as e:
            warn(f"manifest line {line_no} malformed: {e}")
            telemetry["manifest_malformed"] += 1
            continue
        ...
```

No `jq`, no `pandas`. The manifest is bounded by vault size (~300
entries at end-state).

### Frontmatter parse — reuse `audit_orphans.py` patterns

Same `FRONTMATTER_RE` + `SIMPLE_FIELD_RE` regex set. Additions: a
`sources:` block-list parser (adapt `parse_aliases`) and a
`pipeline:` namespace parser (3-line indented-mapping reader).
No PyYAML dependency.

### Wikilink resolution — reuse `audit_orphans.py`

Same `WIKILINK_RE`, same `resolve_link()`, same `build_indexes()`.

### SKIP_DIRS — same as audit_orphans plus `_originals/`

`99 Workspace/_originals/` holds only binaries; explicit skip keeps
the walk tight.

## Performance

- Vault size: ~730 .md files.
- Manifest size at end-state: ~300 entries.
- Pair work: O(N citing notes × C citations per note); C is small.
- Expected runtime: <1 second. Comparable to `audit_orphans.py` (0.49s).

## Re-run cadence

Same as lint-orphans: monthly, bundled with the retrieval eval
(P-8), or ad-hoc after a new manifest entry lands, a typed-source
demotion, or a large promotion run. NOT weekly — staleness drift is
slow.

## Cross-references

- `90 System/_operating_guide.md` — P-3, P-4, P-7, P-8, P-14.
- `90 System/_ingestion_contract.md` — manifest schema (§5–§9),
  supersession algorithm (§7), retrieval pattern (§8).
- `.claude/rules/ingestion-pipeline-discipline.md` — operational
  rules for the manifest.
- `.claude/rules/auto-write-discipline.md` — logging contract.
- `.claude/skills/kb-curator/scripts/audit_orphans.py` — pattern
  source for walk, frontmatter parse, wikilink resolution.
- `.claude/skills/kb-curator/scripts/audit_bitemporal.py` — pattern
  source for `is_latest_version` / `superseded_date` parse.
- `.claude/skills/kb-curator/references/lint-orphans.md` — sibling
  lint (Mode 2).
- `.claude/skills/kb-curator/references/lint-contradictions.md` —
  sibling lint (Mode 1).
- `99 Workspace/_ingestion_pipeline/_manifest.jsonl` — the canonical
  manifest. Empty at S04 ship time.
