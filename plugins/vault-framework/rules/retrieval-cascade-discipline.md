<!-- KERNEL: Enforces P-3 (retrieval cascade) from the operating guide as an
     always-on pre-answer reminder. Auto-loads every session — no path gate.
     The "substantive query" threshold is universal; the cascade steps
     (Step 0 content-catalog, Step 1 Sources/Blocks, Step 1.5 rerank,
     Step 3.5 PPR, confidence/refusal tiers) are framework-standard.
     Trigger phrases and counterparty examples in the PROJECT-SPECIFIC
     section adapt per project. -->

# Retrieval cascade discipline

P-3 (`90 System/_operating_guide.md`) is the load-bearing retrieval rule
of this vault. Documented but commonly under-enforced — the typical
failure mode is stopping at Step 0 (lexical grep) when the query would
have benefited from Step 1 (semantic), Step 2 (Bases), or Step 3
(wikilink expansion).

## Step 0 — content-catalog first

**Step 0 of P-3 starts with `_index.md`, not grep.** Before any
`grep` / `ripgrep` / `Glob` / `bash+yq` invocation on the vault, Claude
reads `_index.md` at vault root and scans it for a stem or summary
match. Only if `_index.md` returns nothing useful does Step 0 fall
through to the lexical tools.

Rationale: `_index.md` is one file, deterministically sorted by zone and
recency. A grep that hits a multi-hundred-note vault rarely beats a
single-file scan that already groups by zone and shows the last-touched
date inline. The central design choice — *the LLM reads the index first
to find relevant pages, then drills*.

Concretely, Step 0 is now:

```
Step 0.0  Read _index.md (full file). Note matching stems and their
          summaries.
Step 0.1  If 0.0 returns a clean hit, jump to the matching note(s).
Step 0.2  Else fall through to lexical tools (grep / Glob / yq / jq)
          over the broader vault — including 99 Workspace/ when the
          query is about session state and 50 Sources/ subdirs when
          the target is extraction-output content excluded from the
          catalog.
```

**Step 0.2 lexical toolkit — choose the right tool:**

| Tool | When to use | Why not plain grep |
|---|---|---|
| `Grep` (with `multiline: true`) | Cross-paragraph patterns spanning line breaks | Plain `rg` requires `-U`; the Grep tool's `multiline: true` sets it automatically |
| `Glob` | Path-pattern matching (e.g. `30 Projects/**/*<name>*.md`) | Cleaner than `find` + `grep -l`; returns sorted paths directly |
| `bash` + `yq` | Frontmatter queries (`yq '. \| select(.type == "decision" and .workstream == "<name>")'`) | grep cannot reason about YAML structure |
| `bash` + `jq` | JSON files (graph health `_graph_health_latest.json`, manifest `_manifest.jsonl`, recommendations `_recommendations_open.jsonl`) | grep mangles JSON |

**Freshness gate.** If `_index.md` `last_updated:` is more than 1 day
old, regenerate first (see `session-bootstrap-discipline.md`).

The full 5-step cascade downstream of Step 0 is unchanged. This is a
*reshape of Step 0 only*; Steps 1–4 keep their numbering and ordering.

## Step 1 — Sources-vs-Blocks granularity

**Default to Sources** (whole-note retrieval). Switch to **Blocks**
(heading/paragraph chunks) when **both** conditions hold:

**(a)** The top-scoring source is a long mixed-topic note **>20 KB.**
Examples: `90 System/_operating_guide.md` (P-rules across many topics);
`30 Projects/{{KEY_PROJECT_PAGE}}.md` (a state MOC — dense anchored
sections covering workstreams, counterparties, decisions).

**(b)** The query targets a **specific anchored section** within that note
rather than the note as a whole (e.g. "what does P-3 say about Step 1",
"the X workstream status", "the Y counterparty section").

When both hold, Blocks mode returns the relevant passage directly.
At Sources granularity, a large guide competes in the embedding space
against a 2 KB concept note — the long note scores broadly even when only
a small section is relevant.

**When to stay on Sources:** short notes, when the whole note is the
target (e.g. "find the person note for X"), or when the query is broad
and any section is equally relevant.

**M9 caveat applies here too:** if the query is in
{{NON_ENGLISH_LANGUAGE}}, skip Step 1 entirely (both Sources and Blocks)
per P-3 M9 fall-through.

## Step 1.5 — Cross-encoder rerank

After Step 1 returns candidates, invoke `90 System/_rerank.py` to re-score
them with a cross-encoder before they enter Step 2:

```
python3 "90 System/_rerank.py" \
    --query "<your query>" \
    --candidates '<json array from Step 1>' \
    --top-k 5
```

Model: `BAAI/bge-reranker-v2-m3` (~70 MB, cached after first load;
GPU/MPS-accelerated where available).

**Key invariant:** Step 1.5 fires *after* route declaration (Step −1) and
*after* Step 1 retrieval. It never touches the routing matrix —
route-declaration scoring is therefore unaffected. (This is what
differentiates rerank-at-1.5 from a fusion approach that fires at entry
and eliminates route declaration: rerank at 1.5 preserves it.)

**When to invoke.** Step 1.5 fires on English substantive queries where
Step 1 returned ≥2 candidates. Pass the Step 1 JSON through `_rerank.py`
and use the returned `rerank_rank` ordering.

**M9 rule.** When Step 1 is skipped ({{NON_ENGLISH_LANGUAGE}} M9
fall-through), Step 1.5 is automatically skipped — no candidates to
rerank. Use `--skip-rerank` in any pipeline that may have gone through M9
to make the skip explicit in the audit trail.

**Graceful fall-through.** If `sentence-transformers` is unavailable (CI,
sandbox, first run before install), note `rerank skipped: sentence-
transformers unavailable` in the reasoning trace and proceed to Step 2
with the original Step 1 ordering. Install via:
```
pip install sentence-transformers --break-system-packages
```

For Route D (EN substantive), the cascade walks
Step 0 → 1 → **1.5** → 2 → 3 → 4.

## Pre-answer checklist (substantive queries)

A **substantive query** = anything that informs a decision, meeting,
document, stakeholder communication, or any output {{USER_FIRST_NAME}}
will act on. Quick factual lookups (e.g. "when is X scheduled?") are
exempt and may stop at Step 0 — and may stop at Step 0.0 alone if
`_index.md` returns the answer.

Before drafting the **final** answer on a substantive query, Claude MUST
have:

1. **Routed** via the Step −1 temporal-intent matrix (Route A / B / C / D)
2. **Scanned `_index.md`** (Step 0.0). On a clean hit, jump straight to
   the matching notes; on a miss, fall through to lexical tools as
   Step 0.1
3. **Walked the steps the route prescribes** — at minimum Step 0; for
   Route D (the default, no temporal signal), also Step 1 (semantic via
   `mcp__smart-connections__lookup`, unless query is in
   {{NON_ENGLISH_LANGUAGE}} → skip per M9 caveat),
   **Step 1.5** (cross-encoder rerank via `90 System/_rerank.py`, EN only,
   ≥2 Step 1 candidates required — skip if M9 fell through or
   sentence-transformers unavailable),
   Step 2 (Bases), and at least one Step 3 wikilink expansion from a
   top hit
4. **Considered Step 4 deep-reads** of the highest-signal anchored
   sections in the state MOC or other long files

If any step is skipped, the answer must **explicitly state which steps
were skipped and why**. Do not silently truncate the cascade.

<!-- PROJECT-SPECIFIC: Trigger phrases below are universal English; the
     counterparty examples should be replaced with the project's named
     counterparties (set {{COUNTERPARTY_EXAMPLES}} per project). -->

## Trigger phrases that auto-classify as substantive

- "battleplan", "prep", "briefing", "meeting prep"
- "what's our position on", "what do we think about"
- "summarise", "analyse", "draft", "write up"
- Anything involving named counterparties — examples in this project:
  {{COUNTERPARTY_EXAMPLES}}
- Anything involving named workstreams, decisions, or open questions

## Quick lookups (exempt — may stop at Step 0)

- "When did X happen?"
- "Who owns Y?"
- "What's the file path for Z?"
- "Show me the latest version of N"

## Reasoning-trace opener

State the route at the top of the trace **before** retrieving. Example:

> Route D (no temporal signal). Walking Step 0 → 1 → 2 → 4. Skipping
> Step 3 — no need to expand from a single anchor for this query.

This makes the cascade legible and reviewable. It also forces
classification before action.

## Why

Lexical grep alone systematically under-recalls on Obsidian vaults that
invest in frontmatter typing, wikilink graphs, and semantic substrate —
those layers were built specifically to compensate for grep's blind
spots. Stopping at Step 0 is the dominant Claude failure mode (a common
retrospective finding: a battleplan produced from grep + targeted reads
alone, with Steps 1, 2, and 3 all skipped). The pre-answer checklist
forces the cascade to be considered, not deferred to "next time".

## Confidence signalling

After the cascade resolves, apply the three-tier confidence rule from P-3
before drafting the final answer:

1. **Normal (no marker)** — 2+ cascade steps independently returned
   signal for the same claim. Proceed.
2. **Thin retrieval — prepend `Confidence: low — [reason]`** — only one
   step fired, or a single file with no cross-zone corroboration, or the
   target file exists but lacks the specific section. Do **not** suppress
   the marker to soften the answer.
3. **No-hit → REFUSE** — all five steps return dead ends. Use the P-3
   dead-end acceptance template and offer {{USER_FIRST_NAME}} one of:
   external search, point me to a source, or open a research item in
   `00 Inbox/`. Never invent a claim to fill a vault gap.

The refusal/calibration dimension of the retrieval eval scores this
behaviour on vault-absent questions. Keep worked traces for the
`Confidence: low` and `REFUSE` patterns in a project examples file (e.g.
`99 Workspace/_examples_calibrated_refusal.md`).

## How to apply

When a query arrives, classify it first (substantive vs lookup). For
substantive queries, walk the cascade in route order. If a step
genuinely doesn't fit the query shape, state it — do not skip silently.
After walking, apply the confidence tier before drafting. The eval at
`90 System/_eval_retrieval.md` is downstream of this discipline and will
detect concealed misses and fabrications; the route letter and confidence
tier in the reasoning trace are what make that scorable.

## Step 3.5 — PPR tie-breaker

For substantive **multi-hop** queries — those naming two or more named
entities and asking how they connect — if Step 3 single-hop BFS does not
return a clear hit, insert Step 3.5 (Personalised PageRank tie-breaker)
before falling through to Step 4 deep-read.

- Module: `90 System/_ppr/` (CLI:
  `python3 "90 System/_ppr/ppr.py" "<query>" --vault "{{VAULT_PATH}}"`)
- Seeds: regex-matched against vault note stems from the query
- Personalisation vector: uniform mass on seeds, zero elsewhere
- Output: top-N stems by PPR score (default 10)

Step 3.5 is a **tie-breaker / supplementary scorer**, not a replacement
for the cascade. Steps 0–3 retain their priority; Step 4 deep-read
remains the canonical terminal. If PPR errors out or returns no useful
signal (no seeds resolved, graph build failure, convergence failure),
the runner notes the skip with `PPR skipped: <reason>` in the reasoning
trace and continues to Step 4.

**Framing guard:** Step 3.5 is a **graph-aware reranker**, NOT a
HippoRAG implementation. The wikilink-graph PPR catches a useful subset
of multi-hop misses; it does not deliver HippoRAG 2's reported gains
(those depend on LLM-OpenIE triples + dense passage nodes + LLM
recognition filter, none of which are in scope).

**Eval coverage:** the multi-hop (MH) dimension of the retrieval eval
covers Step 3.5 with binary per-probe scoring. Suggested pass bar:
≥2/3 MH-correct.

## Cross-references

- `90 System/_rerank.py` — Step 1.5 cross-encoder rerank script
  (`BAAI/bge-reranker-v2-m3`; GPU/MPS-accelerated where available)
- `90 System/_ppr/` — Step 3.5 PPR module;
  `90 System/_graph_health/health.py` — `build_graph()` dependency that
  Step 3.5 PPR consumes
- `90 System/_operating_guide.md` — P-3 full definition, M9 multilingual
  fall-through, Step −1 temporal-intent matrix, Step 3.5 PPR tie-breaker,
  dead-end acceptance template, confidence rule
- `CLAUDE.md` — Retrieval Cascade (M1) stable-prefix pointer
- `90 System/_eval_retrieval.md` — route eval, calibration/refusal probes,
  multi-hop PPR probes
- `90 System/Bases/` — Bases the cascade routes through (primary + Open
  Items + Tier-2 Sources)
- `90 System/_retrieval_contract.md` — pinned substrate (model, source
  count, rebuild procedure)
- `_index.md` — vault content catalog scanned in Step 0.0
- `90 System/_build_index.py` — regenerator for `_index.md`; idempotent;
  also exposes `--append PATH` as the promotion hook
