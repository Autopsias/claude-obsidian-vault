# lint-contradictions — design spec (KP-01)

Karpathy LLM-Wiki Lint Mode 1. Surface pairs of typed notes that look like
they're saying contradictory things about the same subject ("Page A says X,
page B says ¬X"). Proposal-only output, never auto-edit. Wires into
kb-curator as either a standalone mode (`audit-contradictions`) or — once
the false-positive rate is characterised — the 5th chained script in
OBSIDIAN audit mode.

Authored: 2026-05-14 (Framework Remediation S02 / KP-01).
Status: design + reference impl shipped at
`.claude/skills/kb-curator/scripts/audit_contradictions.py`.

## Why this mode exists

Karpathy's April 2026 "LLM-Wiki" pattern: once a knowledge base crosses
~200 notes, hand-spotting contradictions across the typed-zone graph
stops being feasible. The existing kb-curator audit checks are all
structural — bitemporal frontmatter, Bases coverage, rules drift,
plans-index consistency. None look at **content-level disagreements**
between notes that both claim authority on the same subject.

The lint runs as a P-8 measurement: the count and adjudication results
are recorded so the vault's contradiction debt can be tracked over time,
the same way `audit_bitemporal.py` tracks P-4 conformance violations.

## Pool — what we actually scan

We scan **typed `source` and `decision` notes only**, inside the typed
zones (10-70), excluding archives and skill resources.

| Type        | Included | Rationale                                                      |
|-------------|----------|----------------------------------------------------------------|
| `source`    | yes      | Debriefs, battleplans, analyses — primary contradiction risk   |
| `decision`  | yes      | Two decisions on the same topic can disagree across time       |
| `meeting`   | no       | Point-in-time records; "disagreement" within a meeting is data |
| `person`    | no       | Single-fact bios; no factual claims to contradict              |
| `company`   | no       | Same                                                           |
| `project`   | no       | Project pages link out; the state MOC is the canonical claim   |
| `concept`   | no       | Reference material; tangential to live operating claims        |

Bitemporal versioning (P-4) is **respected**: only notes with
`is_latest_version: true` OR no `is_latest_version` field are scanned.
Superseded versions (`is_latest_version: false`) are skipped — a v23 of
the 6-pager disagreeing with v27 is bitemporal succession, not
contradiction.

Galp Vault counts as of 2026-05-14: 249 `type:source` + 16 `type:decision`
= **265 candidate documents** in scope. Pair count C(265, 2) = 34,980 —
trivially tractable, no top-K *pair-generation* cap needed. (The 30,499
figure in the plan prompt is Smart Connections' total indexed sources,
which includes every `.md` in the vault — transcripts, daily notes,
archives, system files, etc. The typed-zone audit pool is two orders of
magnitude smaller.)

## Pipeline

### Step 1 — load embeddings from Smart Connections

Smart Connections stores per-file embeddings in
`.smart-env/multi/<flat-path>.ajson`. Each `.ajson` is a sequence of JSON
fragments, one per line, keyed by:

- `smart_sources:<vault-relative-path>` — the file-level embedding.
- `smart_blocks:<path>#<heading>` — block-level embeddings.

We use **file-level embeddings only** (`smart_sources:` keys). Rationale:

- **Coarse-grained is right for first-pass contradiction.** Block-level
  blows up the pair space (~10x), and most contradictions worth catching
  appear in the headline framing — not in deep sub-sections.
- **Block embeddings duplicate signal.** Two sibling blocks of the same
  doc are near-identical to each other; the resulting top-K would be
  saturated with intra-document pairs.
- **The Haiku adjudication step reads the full file text** when scoring a
  candidate pair — we don't lose section-level detail at judgement time,
  only at candidate-generation time.

Model: `TaylorAI/bge-micro-v2`, 384-dim. Smart Connections normally
emits L2-normalized vectors; we re-normalize defensively. Model is
pinned in `90 System/_retrieval_contract.md`.

### Step 2 — cosine similarity, top-K

For each pair of typed notes (i, j) with i < j, compute cosine
similarity. With L2-normalized vectors, this is a single numpy matmul.

- **Similarity threshold:** `>= 0.85`.
- **Top-K cap:** `200` pairs (configurable via `--top-k`). Even if the
  threshold sweep returns more, only the highest-similarity 200 are
  emitted as candidates. Keeps Haiku spend bounded and the proposal
  file reviewable.
- **Per-document fan-out cap:** `5` (configurable via `--per-doc-cap`).
  If a single document appears in >5 candidate pairs, only the 5 highest
  are kept. Prevents one prolific doc (like the 6-pager) from saturating
  the proposal.

### Step 3 — Claude-Haiku adjudication

For each surviving candidate pair, send both notes' full text to
`claude-haiku-4-5-20251001` with a strict JSON-output prompt (template
below). Parse the JSON:

```json
{
  "contradiction": true,
  "confidence":    0.82,
  "evidence":      "A: 'Day 1 readiness is the binding constraint' ↔ B: 'Day 1 readiness deferred to D+90'"
}
```

**Pair is flagged** iff `contradiction == true` AND `confidence >= 0.7`.
Pairs that fail to parse, time out, or return malformed JSON are
reported as `adjudication_error` with the raw response captured — never
silently dropped.

If the Anthropic SDK is not installed or `ANTHROPIC_API_KEY` is not set,
the script **skips Step 3** and emits candidate pairs as
`adjudication: PENDING` with the prompt template embedded so an
interactive Claude session can adjudicate without re-running the
script. This mirrors the ingestion pipeline's cloud-OCR guard pattern.

### Step 4 — proposal output

Single Markdown file at:

```
99 Workspace/_lint_contradictions_YYYY-MM-DD.md
```

Per `auto-write-discipline.md`: in `99 Workspace/` (auto-write zone),
logged in `_auto_writes.md`. Proposal-only — never edits the source
notes.

## Threshold rationale

| Knob              | Value | Why                                                                            |
|-------------------|-------|--------------------------------------------------------------------------------|
| Similarity ≥0.85  | 0.85  | bge-micro on short-form English: ≥0.85 means "same topic, near-duplicate framing". Below 0.80 the noise floor swallows real contradictions; 0.85 is the operating point used in the Karpathy reference setup and corroborated by spot-checks on the Galp 6-pager version chain (v27 ↔ v28 file-level sim typically ≥0.90; v27 ↔ a random transcript ≈ 0.40-0.50). |
| Top-K = 200       | 200   | Even a saturated proposal at 200 pairs takes Ricardo ≤30 minutes to review.    |
| Per-doc cap = 5   | 5     | Stops the 6-pager (or any hub doc) from owning the proposal.                   |
| Haiku conf ≥0.7   | 0.7   | Tuned to favour precision over recall — false positives are the failure mode that destroys trust in the lint. A conf≥0.7 contradiction the user disagrees with is rare; a flood of conf-0.5 weak signals is what gets the report ignored. |
| Bitemporal skip   | —     | Superseded versions are point-in-time records of past disagreement, not live contradictions. Auditing them turns every doc-evolution into noise. |

Knobs are CLI flags so the operator can re-run with different settings
without code changes. Spec is the source of truth for the *defaults*;
the script's `--help` documents the live overrides.

## Haiku prompt template

System prompt (concise — Haiku is paid per-token):

```
You are an expert knowledge-base auditor. You compare two notes from a
knowledge vault and decide whether they make CONTRADICTORY factual claims
about the same subject. A contradiction means one note asserts X while
the other asserts not-X about the SAME entity, decision, fact, or
commitment. Two notes covering different aspects of the same topic, or
evolving over time within bitemporal versioning, are NOT contradictions.
Return ONLY a JSON object — no preamble, no markdown fences. Schema:
{"contradiction": boolean, "confidence": number between 0 and 1, "evidence": string or null}
- contradiction: true only if both notes are currently authoritative and disagree.
- confidence: your calibrated certainty in the contradiction call.
- evidence: a single short quote pair (max 240 chars total) anchoring the
  contradiction, or null.
```

User prompt (per pair):

```
# Note A
Path: {path_a}
Type: {type_a}
Last updated: {document_date_a}

{content_a_truncated_to_8000_chars}

# Note B
Path: {path_b}
Type: {type_b}
Last updated: {document_date_b}

{content_b_truncated_to_8000_chars}

Are these contradictory? Respond with the JSON object only.
```

Notes:

- Content is truncated to **8000 chars per side**. Haiku's context can
  handle more, but most contradictions surface in the headline framing
  / decision paragraphs — a tighter window forces the model to anchor on
  the load-bearing claims.
- `max_tokens` on the response is capped at **200**. The expected JSON
  is ~80-150 tokens; 200 is the safety margin before truncation risk.
- **Temperature 0.0** — adjudication should be deterministic for a
  given pair.

## Output format — proposal file

YAML frontmatter (per `auto-write-discipline.md` provenance pattern):

```yaml
---
type: audit
provenance: kb-curator lint-contradictions (KP-02 — Karpathy Lint Mode 1)
generated: YYYY-MM-DD
candidates_total: N
flagged_contradictions: M
adjudicated: yes|pending
similarity_threshold: 0.85
top_k_cap: 200
per_doc_cap: 5
haiku_model: claude-haiku-4-5-20251001
embedding_model: TaylorAI/bge-micro-v2
runtime_seconds: T
---
```

Body sections (in order):

1. **Summary** — N candidates passed similarity threshold; M flagged by
   Haiku; runtime breakdown.
2. **Flagged contradictions** (emitted only when adjudication ran) —
   one block per flagged pair: file A + B paths, similarity, Haiku
   confidence, Haiku evidence quote, suggested action ("Ricardo to
   reconcile / supersede one / mark both as bitemporal versions").
3. **Pending adjudication** (emitted only when the Haiku step was
   skipped) — one block per candidate, including the rendered Haiku
   prompt so a downstream Claude session can adjudicate without
   re-running the script.
4. **Below threshold** — count only, for telemetry.
5. **Errors** — adjudication errors with the raw Haiku response, never
   silent.

## Wiring into kb-curator

**Phase 1 (this session):** standalone script invocable as
`python3 audit_contradictions.py --root <vault>`. Not chained into
`audit` mode yet — KP-02 ships the script + first proposal;
integration into the OBSIDIAN audit chain is deferred to a later
session once the false-positive rate is characterised on real-world
re-runs.

**Phase 2 (after 2-3 successful runs with manageable false-positive
rate):** add to `SKILL.md` Section "OBSIDIAN audit checks" as check
#5, running after `audit_plans_index.py`. The audit chain stays
read-only / proposal-only — contradictions surface as proposals,
never blocking moves.

## Autonomy boundary (P-7 conformance)

- **Writes to** `99 Workspace/_lint_contradictions_YYYY-MM-DD.md` only.
  Auto-write zone; logged per `auto-write-discipline.md`.
- **Reads** typed-zone `.md` files + `.smart-env/multi/*.ajson`.
- **Never edits** any `source`, `decision`, or other typed note.
- **Never deletes** anything.
- **Never auto-resolves** a contradiction — proposal-only, Ricardo
  decides.

## Failure modes

| Mode                                  | Behaviour                                                     |
|---------------------------------------|---------------------------------------------------------------|
| `.smart-env/` missing or empty        | Hard-exit 2, point to plugin-security-discipline rule.        |
| Embedding model drift                 | Warn + continue; record the model found in proposal frontmatter. |
| Anthropic SDK / API key missing       | Skip Step 3; emit `adjudication: PENDING` block per pair.     |
| Haiku rate limit / 429                | Backoff with 3 retries; if exhausted, mark pair as `adjudication_error`. |
| Malformed JSON from Haiku             | Capture raw response in `Errors` section; do not flag pair.   |
| Single doc dominates top-K            | Per-doc fan-out cap; surplus listed in `Below threshold`.     |
| Zero candidates                       | Emit proposal with `flagged_contradictions: 0` and runtime — proves the lint ran. |

## Re-run cadence

Monthly, bundled with the retrieval eval (P-8). Or ad-hoc after any
session that promoted >10 notes into typed zones. Not weekly — the
lint signal is slow-moving and weekly runs would just regenerate the
same proposal.

## Cross-references

- `90 System/_operating_guide.md` — P-3 (cascade), P-7 (autonomy), P-8 (eval).
- `.claude/rules/auto-write-discipline.md` — logging contract.
- `.claude/skills/kb-curator/SKILL.md` — Phase 0 substrate detection, audit chain.
- `.claude/skills/kb-curator/scripts/audit_bitemporal.py` — pattern for typed-zone walk.
- `90 System/_retrieval_contract.md` — pinned embedding model.
