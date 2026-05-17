# Architecture Reference

---

## The 9 P-rules at a glance

P-rules are behavioural contracts loaded from the operating guide (`_operating_guide.md`). They govern how Claude reads, writes, promotes, and evaluates the vault. All 9 are present in the operating guide template; the scaffold fills in project-specific values during `/vault-setup`.

| P-rule | Name | One-line description |
|---|---|---|
| P-1 | Stable prefix discipline | `CLAUDE.md` holds stable facts only; volatile project state lives in the state MOC; the two files govern different things and should not drift into each other |
| P-3 | Five-step retrieval cascade | The full retrieval protocol: Step −1 temporal routing → Steps 0–4 → confidence tiers; the cascade is the primary intellectual contract of the framework |
| P-4 | Versioning discipline | Source and decision notes carry `document_date` + `is_latest_version` frontmatter; superseded notes get a `superseded_by:` pointer; no deletes |
| P-5 | Session bootstrap | 7-step lifecycle Claude runs at session start: mount check → hot cache → handoff → operating guide → daily note → plans index → content catalog |
| P-6 | Source ingestion | Drop zone → extract → manifest → log; every ingested source gets structured frontmatter and a manifest entry; originals preserved read-only |
| P-7 | Autonomy boundary | Auto-write OK in `99 Workspace/`, `00 Inbox/`, `80 Daily/`; all other zones require an explicit user trigger; state MOC edits require a trigger regardless of zone |
| P-8 | Freshness discipline | Cadence triggers per file type (weekly / monthly / stable); handoff target ≤15 KB; 3-strike compression rule when threshold is exceeded 3 sessions in a row |
| P-10 | Quality filter | 3-question filter before any typed-zone promotion; ensures notes are complete, correctly typed, and not duplicates before they leave the workspace |
| P-11 | Multilingual (M9) | For content in a non-primary language: skip the semantic step (Step 1) and go directly to Bases; Smart Connections embedding space is English-optimised |

---

## Retrieval cascade (P-3)

The cascade is the core of the framework. Every substantive query walks it in order, stopping at the first clean hit.

### Step −1: Temporal routing matrix

Before any retrieval, classify the query's temporal intent:

- **Route A** — "As of [date]" — retrieve the note that was current on that date (use `As Of.base`)
- **Route B** — "Latest" — retrieve the current version only (use `Latest Only.base`)
- **Route C** — "History" — retrieve the full version chain (use `Version Chain.base`)
- **Route D** — No temporal signal — proceed through the full cascade (default)

Claude states the route at the top of its reasoning trace before any retrieval. This makes the cascade scorable on the T dimension of the eval.

### Step 0: Lexical — content catalog first (Karpathy pattern)

**Step 0.0** — Read `_index.md` at vault root. This is the Karpathy move: a single ~250-line file, one line per non-ephemeral note, grouped by zone, sorted by last-touched desc. Scan for a stem or summary match. A clean hit here avoids hitting the full vault.

**Step 0.1** — If `_index.md` returns nothing useful, fall through to lexical tools: ripgrep over the vault, `yq` for frontmatter queries, `jq` for JSON files (manifest, recommendations queue). Tool selection:

| Tool | When |
|---|---|
| `Grep` with `multiline: true` | Cross-paragraph patterns |
| `Glob` | Path-pattern matching |
| `bash` + `yq` | Frontmatter queries |
| `bash` + `jq` | JSON files |

**Freshness gate:** if `_index.md` is >1 day old, regenerate before reading: `python3 _build_index.py --root <vault>`. Idempotent, runs in <2 s.

### Step 1: Semantic — Smart Connections

`mcp__smart-connections__lookup` returns semantically similar notes. Default granularity: Sources (whole notes). Switch to Blocks (heading/paragraph chunks) when: (a) the top-scoring source is a long mixed-topic note >20 KB **and** (b) the query targets a specific anchored section within it.

**M9 caveat:** for queries where the target content is in a non-primary language, skip Step 1 entirely and go directly to Step 2. Smart Connections' embedding model is English-optimised; non-English queries produce noisy rankings.

### Step 1.5: Cross-encoder rerank

After Step 1 returns ≥2 candidates, pass them through the cross-encoder reranker:

```bash
python3 plugins/vault-eval/scripts/rerank.py \
    --query "<your query>" \
    --candidates '<json array from Step 1>' \
    --top-k 5
```

Model: `BAAI/bge-reranker-v2-m3` (~70 MB, Apple Silicon MPS, cached after first load). The cross-encoder scores each (query, candidate) pair jointly, recovering precision that bi-encoder embedding similarity misses — especially important for long files where only a small section is relevant.

**Graceful fall-through:** if `sentence-transformers` is unavailable, note `rerank skipped: sentence-transformers unavailable` and continue with the Step 1 ordering.

### Step 2: Structured — Bases

Query the 12 Bases templates in `90 System/Bases/`. Bases filter by frontmatter keys and sort by last-touched, which makes them robust when the embedding index is degraded or rebuilding. `Open Items.base` is the primary at-a-glance surface for session bootstrap.

### Step 3: Link-expand — wikilink BFS

From the top candidate returned by Steps 0–2, do a breadth-first expansion of `[[wikilinks]]`. For multi-hop queries (two or more named entities — "how does X connect to Y?"), if single-hop BFS doesn't resolve it, run the PPR tie-breaker:

```bash
python3 "90 System/_ppr/ppr.py" "<query>" --vault "<vault-path>"
```

PPR seeds from entity names extracted from the query, runs personalised PageRank over the wikilink graph, returns top-N stems by score. A graph-aware reranker, not a full HippoRAG implementation — catches a useful subset of multi-hop misses.

### Step 4: Deep-read — anchored sections

For long files (operating guide, state MOC), read the specific anchored section targeted by the query rather than the full file. Anchored sections carry `## Concept:` / `## Workstream:` / `## Counterparty:` headers and `Last touched: YYYY-MM-DD` markers. If a section's `Last touched` is >14 days old, flag potential staleness before acting on it.

### Confidence tiers

After the cascade resolves, apply the confidence tier before drafting:

| Tier | Condition | Output |
|---|---|---|
| **Normal** | 2+ cascade steps independently returned signal for the same claim | No marker — proceed |
| **Low** | Only one step fired, or single file with no cross-zone corroboration | Prepend `Confidence: low — [reason]` |
| **REFUSE** | All five steps return dead ends | Use the P-3 dead-end acceptance template; offer: external search, point me to a source, or open a research item in `00 Inbox/` |

Claude never invents a claim to fill a vault gap. The CAL dimension of the eval (Q26–Q30) scores this behaviour on vault-absent questions.

---

## Eval harness

### 33-question structure

Questions are grouped into 6 scoring dimensions:

| Dimension | Questions | What it measures |
|---|---|---|
| **S** | ~8 | Semantic retrieval precision — does Smart Connections surface the right note? |
| **X** | ~6 | Cross-zone retrieval — does the cascade cross folder boundaries correctly? |
| **T** | ~6 | Temporal routing — does Step −1 classify the route correctly? Do temporal queries resolve to the right version? |
| **MH** | ~3 | Multi-hop — does PPR + link-expand resolve two-entity questions that single-step retrieval misses? |
| **CAL** | ~5 | Calibrated refusal — does Claude say `Confidence: low` or `REFUSE` for vault-absent questions? Does it avoid hallucinating? |
| **F** | ~5 | Faithfulness — are answers grounded in retrieved text, not invented? (scored separately from the aggregate) |

### Scoring

- Binary per question (PASS / FAIL)
- Aggregate score: `(S + X + T + MH + CAL) / 5` (F scored separately to isolate generation quality from retrieval quality)
- IR metrics computed from the S and X questions: Precision@1, Precision@5, MRR, Recall@10, NDCG@5
- Pass bar: ≥80% aggregate to consider the cascade operationally trusted

### Autoresearch loop

The autoresearch loop hill-climbs on the eval score by iterating over the cascade's editable surface: P-rule thresholds, rerank parameters, step-ordering heuristics, `_index.md` freshness gates. Each iteration proposes a delta, re-scores the eval, and keeps the delta if the score improves.

Stopping criterion: perfect score (100%) or 20 non-improving iterations — whichever comes first. The loop surfaces a consolidated diff for Ricardo's approval; it does not auto-apply. Trigger manually after 90 days of production use when the question history is meaningful. Full implementation: `plugins/vault-skills/skills/autoresearch-loop/SKILL.md`.

---

## Audit chain (Ed25519)

Every write to the auto-write zones (`99 Workspace/`, `00 Inbox/`, `80 Daily/`) is logged to `99 Workspace/_auto_writes.md` via a hash-chained Ed25519-signed log. Manual writes are not permitted — always use the chain script:

```bash
python3 "90 System/_audit_chain.py" \
  --vault <vault-path> \
  append --verb write --path "<path>" --reason "<one-line reason>" --grep-prefix
```

### Entry format

```
## [YYYY-MM-DD] write | filename.md
YYYY-MM-DD HH:MM | write | full/path/to/file.md | reason | prev_hash:<sha256> | sig:<ed25519-b64url>
```

The `##` grep-prefix header makes the log scriptable without touching the cryptographic chain (the hash covers the signed entry only, not the header).

### Verification

```bash
python3 "90 System/_audit_chain.py" verify --json
```

Validates the full chain: each entry's signature, each `prev_hash` pointer, and the chain's continuity. Output is JSON with per-entry results and an aggregate verdict.

### Weekly health check

The `vault-health` scheduled task re-computes the plugin directory hash and compares against the stored baseline. If drift is detected, it automatically runs `smoke_test_retrieval.py` and writes an audit report. The `verify --json` chain check runs alongside it.

### Parallel git record

Every Claude file write also produces a git commit (when the post-write hook is active). The audit chain proves *who* wrote and *why*; git proves *what* changed and enables surgical revert. Neither replaces the other.

---

## Closed-loop recommendation registry

Health tasks emit structured recommendations to `99 Workspace/_recommendations_open.jsonl` (JSONL queue). Claude reads this file at session bootstrap (step 9c) and surfaces rows before substantive work begins.

### Tier map

| Tier | Expiry window | Example |
|---|---|---|
| T1 | 7 days | Log rotation needed (auto-resolvable) |
| T2 | 14 days | Retrieval eval overdue (requires manual run) |
| T3 | 30 days | Cascade regression detected (escalation — surfaces as a banner alongside eval overdue) |

### Backpressure

When OPEN row count exceeds 20, emitters suppress new recommendations. This prevents the queue from becoming noise when a batch of health issues fires simultaneously.

### Session surfacing order

At session bootstrap, Claude surfaces recommendations in this order before any substantive work: PD-01 eval overdue banner → T3 OPEN rows → EXPIRED rows → high-count flag (>10 OPEN). T1 and T2 rows are available but not forced to the top.

---

## Plugin map

```
claude-obsidian-vault/
├── plugins/
│   ├── vault-framework/       Core kernel
│   │   ├── commands/          /vault-setup, /hot, /promote slash commands
│   │   ├── rules/             11 .claude/rules/ files (auto-loaded discipline)
│   │   ├── skills/            project-setup skill (wraps /vault-setup)
│   │   ├── templates/         CLAUDE-template.md, operating-guide-template.md,
│   │   │                      12 Bases templates, decision/meeting/source note templates
│   │   └── scripts/           populate-claude-md.py, verify_baseline.py, bases-verifier.py
│   │
│   ├── vault-skills/          Active maintenance skills
│   │   └── skills/
│   │       ├── kb-curator/    Audit, lint, promote, rotate-logs, refresh-index
│   │       ├── plan-builder/  HTML session plans with visual progress tracker
│   │       ├── save-conversation/  Save chat to vault as a source note
│   │       └── autoresearch-loop/  Nightly eval hill-climb (advanced)
│   │
│   ├── vault-eval/            Retrieval quality measurement
│   │   ├── templates/         eval-retrieval-template.md (33 questions)
│   │   ├── skills/            /vault-eval slash command
│   │   └── scripts/           smoke_test_retrieval.py, rerank.py, eval_faithfulness.py
│   │
│   ├── vault-ingestion/       Multi-format source pipeline
│   │   ├── scripts/           ingest.py, backfill_manifest.py, config.yaml
│   │   │   └── handlers/      pdf, docx, pptx, xlsx, text, image, html, semantic, links
│   │   └── templates/         ingestion-contract-template.md
│   │
│   └── vault-voice/           Audience-facing prose discipline
│       ├── voice-discipline.md        Auto-load rule (fires on document-generation paths)
│       ├── voice-profile-template.md  Fill-in template for Ricardo-style voice profile
│       ├── writing-craft-template.md  Universal craft layer (Pyramid/BLUF/SCQA/clarity)
│       └── populate-voice-profile.py  Interview script → generates populated voice profile
│
├── reference-vault/           Fully worked example (Acme Corp / BetaCo, fictional)
├── scripts/
│   └── bootstrap.sh           Path B installer (Homebrew → Obsidian → plugins → instructions)
├── README.md
├── INSTALL.md
├── USAGE.md
└── ARCHITECTURE.md            (this file)
```

---

## Key design decisions

**Why Ed25519 over HMAC?** Ed25519 is asymmetric — the private key signs but the public key verifies. Anyone with `_audit_pubkey.txt` can verify the chain without access to the private key. HMAC requires the verifier to have the secret, which breaks the audit property.

**Why a 33-question eval rather than automated metrics only?** Automated IR metrics (Precision@k, MRR, NDCG) measure retrieval quality but not *calibration* — whether Claude correctly refuses when it should. The CAL dimension requires human-designed vault-absent questions to score. The 33-question set combines both.

**Why is the autoresearch loop gated at 90 days?** The hill-climb needs a meaningful distribution of real queries to be signal. Before 90 days, the question history is too thin — the loop would overfit to a handful of queries and degrade generalisation.

**Why does `_index.md` exist if Bases already provides structured queries?** Different retrieval shapes. `_index.md` is a flat, recency-sorted, zone-grouped text file — optimised for the LLM reading it linearly in one pass (the Karpathy pattern). Bases are optimised for structured filter queries. They complement each other: `_index.md` for orientation; Bases for "show me all decisions where `workstream == Day1` and `is_latest_version == true`".
