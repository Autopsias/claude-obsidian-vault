---
name: Vault Retrieval Eval
description: Retrieval-eval question set for {{PROJECT_NAME}} vault. Three binary dimensions (S supersession-correct, X retrieval-complete, T temporal-correct), ≥80% pass bar each. First run is the M2 move-time / go-live gate; monthly cadence thereafter.
type: eval
cadence: monthly
last_updated: "{{DATE}}"
runs_to_date: 0 (no runs yet — first run is the M2 gate at go-live)
---

<!-- PROJECT-SPECIFIC: This is the eval framework template.
     Replace the question table entries with project-specific questions.
     Keep the scoring machinery, cascade-step tagging system, and pass bar
     exactly as documented here — those are kernel. The questions themselves
     are project-specific and must be sourced via the anti-cherry-pick rule.
     Minimum viable: 10 questions at launch; grow to ~25 by month 4.
     Target distribution: L≥2, S≥2, B≥2, W≥2, D≥2 as primaries. -->

# Vault Retrieval Eval

The first run of this question set is the **M2 go-live gate** — run immediately
after the vault is live and indexed, before the migration or launch is declared
successful. **<80% on any dimension reverts the launch.** Monthly cadence
thereafter via the vault's `eval-recency` health task.

## Scoring

Three binary dimensions per question:

- **Supersession-correct (S):** the answer reflects the **latest** state, not a stale
  earlier version. `1` = yes, `0` = no, `N/A` = no supersession risk in the question.

- **Retrieval-complete (X):** the answer pulls from **all** relevant zones / sources,
  not just one. `1` = yes (≥2 zones cross-referenced where appropriate, or
  single-source if that is genuinely all there is), `0` = no (single-source where
  multiple were needed), `N/A` = single-source by design.

- **Temporal-correct (T):** the answer is drawn from the version that was **current
  as of the question's implied date** — not from a superseded version, and not from
  the always-latest version when the question asked for a past state.
  `1` = yes (cited version matches the question's temporal anchor: "current" →
  `is_latest_version: true`; "as of <date>" → max `document_date ≤ <date>` with
  `superseded_date` absent or `> <date>`; "how did X evolve" → version chain ordered
  by `document_date`); `0` = no; `N/A` = no temporal angle.

  **T is distinct from S:** S asks "is the answer up-to-date" (always against now);
  T asks "is the answer drawn from the version current as of the question's implied
  date" (which may be a past date, correctly returning a now-superseded version).

**Pass bar (D1):** ≥80% on **each** dimension (S, X, T) across the applicable subset
(questions where the dimension is not N/A). Any dimension below 80%:
- At M2 gate: **reverts the launch / migration**.
- In steady state: triggers an immediate root-cause sweep.

## Cascade-step tagging

Each question carries a tag identifying the cascade step it **preferentially exercises**.
The tag is diagnostic — it lets the scorecard surface step-level gaps, not just
aggregate pass/fail. The cascade is documented in CLAUDE.md and `_operating_guide.md` P-3.

- **L (lexical, step 0)** — answers turn on identifiers, version strings, exact phrases,
  frontmatter values; `grep` / Obsidian search is the right primary.
- **S (semantic, step 1)** — answers turn on paraphrase / fuzzy recall; Smart Connections
  is the right primary. Note M9 fall-through caveat if applicable.
- **B (structural, step 2)** — answers turn on shaped queries over frontmatter; a Base
  view is the right primary.
- **W (wikilink-walk, step 3)** — answers turn on traversing the graph from a top hit;
  depth-1/depth-2 BFS is the right primary.
- **D (deep-read, step 4)** — answers turn on opening one specific file and reading
  anchored sections.

Multiple tags allowed (`L+B`, `S→L` for fall-through). Tags are not load-bearing for
the score; the score is on S, X, and T.

## Per-run row format

One row per question per run. Required columns:

| # | S | X | T | route | step-fired | notes |
|---|---|---|---|-------|------------|-------|

- **route**: A (current → Latest Only.base), B (as-of date → As Of.base),
  C (history/evolution → Version Chain.base), D (default full cascade).
  Questions without a specific route default to D.
- **step-fired**: the cascade step(s) actually exercised in the run
  (may differ from the tagged expected step — document the deviation).
- **notes**: what the runner found, supersession reasoning, paths cited.

## Question Set v1

<!-- PROJECT-SPECIFIC: Replace these placeholder entries with real questions
     sourced via the anti-cherry-pick rule. Minimum 10 for M2 gate.
     Each entry must include: question text, cascade-step tag, dimensions (S/X/T),
     anti-cherry-pick source method, and the expected cascade route. -->

| # | Question | Cascade step | Tests |
|---|----------|--------------|-------|
| 1 | [PLACEHOLDER — L+D probe: exact identifier that resolves lexically to a key document; ask what the current version/state is.] | **L+D** | S |
| 2 | [PLACEHOLDER — L+B probe: exact term resolving to state MOC; cross-check against Bases view to confirm current vs stale count/value.] | **L+B** | S+X |
| 3 | [PLACEHOLDER — M9 fall-through probe, if applicable: Portuguese/Spanish-heavy content requiring lexical fallback.] | **L (M9 fall-through from S)** | X |
| 4 | [PLACEHOLDER — L+W probe: lexical hit on a versioned document; wikilink-walk to a related change-note or delta.] | **L+W** | S |
| 5 | [PLACEHOLDER — B+W+D probe: Bases query for a decision record; wikilink-walk to supporting context; deep-read anchored section.] | **B+W+D** | S+X |
| 6 | [PLACEHOLDER — L+W probe: lexical hit on a named concept/entity; wikilink-walk to supporting context.] | **L+W** | X |
| 7 | [PLACEHOLDER — S→L+B probe: semantic recall of a concept; Bases cross-check for supporting sources.] | **S→L+B** | S+X |
| 8 | [PLACEHOLDER — L+W probe: named person + ruling/event; pure recency probe.] | **L+W** | S |
| 9 | [PLACEHOLDER — B+D probe: Bases query returns supporting source; deep-read for specific finding.] | **B+D** | X |
| 10 | [PLACEHOLDER — S→D methodological probe: no greppable identifier; forces step 1 semantic; deep-read confirms finding. Must guarantee step 1 is exercised every run.] | **S→D** | S+X |

<!-- Add Route A/B/C temporal probes (Q18/Q19/Q20 pattern) when the vault has
     bitemporal frontmatter in place (is_latest_version, document_date, superseded_date).
     At minimum, add one probe per route:
     - Route A: query with "current" token → Latest Only.base
     - Route B: query with "as of <date>" → As Of.base  
     - Route C: query with "evolved/changed/history" → Version Chain.base -->

## What "the answer" looks like for the runner

For each question, the runner (Claude in a cold session, no prior turns; or a
sub-agent dispatched from a session) is expected to:

1. **Walk the cascade in order** — start at the tagged step's predicted entry point;
   document fall-through if any. The runner's own reasoning trace is part of the audit.
2. **Cite ≥1 vault path** for the answer's load-bearing claim.
3. **Cross-reference** when the X dimension is in scope — at least two distinct
   sources / zones for a 1-score on X.
4. **Surface supersession explicitly** — name what the earlier version said, then the
   current version, and how the runner determined which was current. Required for S=1.
5. **Stop walking and report** when the answer is complete or when all five steps return
   dead ends. Don't fabricate beyond what the cascade returned.

## How to score

Compute four percentages per run:

- **S percentage** = sum(S=1) / count(S in {0,1}). N/A excluded.
- **X percentage** = sum(X=1) / count(X in {0,1}). N/A excluded.
- **T percentage** = sum(T=1) / count(T in {0,1}). N/A excluded.
- **Aggregate** = mean(S%, X%, T%). All three individual percentages must clear ≥80%;
  any one below 80% triggers an immediate root-cause sweep (or reverts the M2 gate).

## Question Set Maintenance

- Replace any question whose answer has been uncontested for 3 consecutive runs
  (no supersession churn) with a fresh recently-superseded fact.
- **Target size: ~25 by month 4, then stabilise.** Growth cadence: +5 questions/month
  for first 3 months, taper to +3 in month 4 to reach ~25.
- Add a question when a major new workstream or topic area lands.
- Multilingual probes (if applicable) should remain as long as the model handles that
  language via cascade fall-through rather than native embedding — revisit at
  6-month substrate review.
- The step-1 semantic probes (Q10 pattern) must remain as long as the cascade has a
  semantic step. If retired, replacement must also force step 1.

## Question Growth Framework

### Growth cadence

| Month | Batch | Target Q count after batch |
|-------|-------|---------------------------|
| Launch (M2) | Q1–Q10 | 10 |
| Month 2 | Q11–Q15 | 15 |
| Month 3 | Q16–Q20 | 20 |
| Month 4 | Q21–Q25 (taper) | 25 |
| Month 5+ | Retire 1–2/quarter, replace 1–2/quarter | stable ~25 |

### Balance floors (check before drafting each batch)

**Cascade steps (L / S / B / W / D):** each step must appear as the primary or
co-primary in ≥2 questions. Maintain ≥2 genuine-S questions (Smart Connections
must succeed — M9 fall-throughs count as L for floor purposes).

**Languages:** if the vault has non-English content, maintain ≥3 non-English
probes by Q20. Each batch adds ≥1 non-English question until floor is met.

**Supersession (S dimension):** ≥40% of the full set should have S dimension = non-N/A.

**Typed-zone coverage:** all typed zones represented by ≥1 question by Q25.

### Anti-cherry-pick rule

Candidates must originate from actual vault content via one of three mechanical methods:

1. **Base-list method:** query an underrepresented typed zone's Base → pick a real
   entry → build the question around that entry's content.
2. **Recency-grep method:** `find <zone> -newer <date>` for files modified in the
   last 30 days → prioritise as supersession-sensitive candidates.
3. **Low-link method:** files with few inbound wikilinks → test coverage breadth,
   not just the most-linked content.

Log which method sourced each candidate question in the question's table entry.

### Per-question validation checklist

Before adding any question to the set:
- [ ] Not a paraphrase of an existing question
- [ ] Cascade step tagged and justified
- [ ] S and X dimensions assigned with explicit justification (not defaulted to N/A)
- [ ] Vault source(s) that should answer the question identified
- [ ] If non-English: M9 fall-through flag set correctly if applicable
- [ ] Anti-cherry-pick source method logged
- [ ] Explicit approval logged (session reference)

## Karpathy lint-system probes (added 2026-05-14)

Once the vault has adopted the Karpathy lint pattern (3 scripts in
`scripts/` + 3 reference specs in `references/`), reserve 3–4 questions in the
eval set as **lint-system probes**. These differ from cascade probes — they
test whether the lint scripts catch synthetic degradation seeded into the vault,
not whether retrieval can find existing content.

### Probe pattern

For each lint mode, add one probe question with this shape:

```
Q<N>. Lint-<mode> recall on seeded degradation.

Setup: Seed a synthetic [contradiction pair | typeless orphan | superseded source
citation] into 99 Workspace/. Run the corresponding lint script.

Pass: The script's proposal output flags the seeded item with the documented
confidence/severity. Recall ≥1 on the seeded item; false-positive rate on the
rest of the vault below the published threshold.

S dimension: N/A (lint, not retrieval).
X dimension: lint recall (1 if seeded item flagged, else 0).
T dimension: N/A unless the mode is temporally sensitive (Rule B/C of stale).
Cascade step: N/A.
```

### Three canonical probes (recommended naming)

| Probe | Mode | Threshold (FP) | Notes |
|-------|------|----------------|-------|
| Q-LC | Contradictions (semantic + LLM-adjudicator) | varies by adjudicator | Skip-with-PENDING if API key absent in run env |
| Q-LO | Orphans (reachability) | ≤5–10% FP | Seed a typeless note with no incoming wikilinks |
| Q-LS | Stale propagation (3 rules) | ≤5% FP | Seed a citation to a superseded source; run after manifest is non-empty |

### Calibration cadence

- **At-adoption baseline:** record FP rate of each lint script against the
  unseeded vault. This is the "noise floor". A real catch is anything above the
  noise floor.
- **6-month falsifiable check:** the substrate review (P-13) scores whether the
  lint suite caught ≥3 real degradations in the 6-month window. 0 catches →
  retire scripts; 3+ → keep + extend. The probes feed this check by maintaining
  recall confidence.

### When to add the probes

Add lint probes only **after** the corresponding script is live and has produced
a baseline run on the actual vault (i.e. has a `99 Workspace/_lint_*.md`
proposal file you can point to). Probes added before the script is live are
fictional — they will pass or fail based on stub behaviour, not actual lint
quality.

## Monthly random spot-check ritual

**Purpose:** The retrieval eval tests whether Claude can *find* content; it does not
test whether the content it finds is *true*. This ritual is the only systematic check
on fabrication / confabulation in the typed zones. Runs alongside the monthly eval
session. Target duration: 15 minutes.

**How it works:**

At the start of each monthly eval session, Claude:

1. **Draws 5 random typed-zone entries** — one from each of the primary typed zones.
2. **Surfaces each entry with its cited source.** For each entry, Claude presents:
   (a) the entry's load-bearing claim, and (b) the vault path(s) cited as provenance.
3. **The user verifies** by opening the cited source and confirming the claim is an
   accurate representation of what the source says.

**Outcomes:**

- **Hit:** claim matches source. No action required.
- **Miss (minor):** claim overstates or paraphrases inaccurately but is recoverable.
  Edit the typed-zone entry inline; log to `99 Workspace/_reflection_log.md`.
- **Miss (significant):** claim cannot be traced to any source, or directly contradicts
  it. Log to `99 Workspace/_reflection_log.md`; if ≥2 misses in same zone across
  3 consecutive runs, promote to `99 Workspace/_lessons.md` as a fabrication-pattern.

**Sampling:** Use deterministic shuffle seeded on `YYYY-MM` (same month → same 5
entries — reproducible). Exclude `00 Inbox/` and `99 Workspace/` entries.

**Reporting:** Append to `99 Workspace/_reflection_log.md`:
```
YYYY-MM-DD | spot-check | <zone>/<filename> | HIT / MISS-minor / MISS-significant | one-line description
```

## Cross-references

- Cascade documented in `CLAUDE.md` and `_operating_guide.md` P-3
- M11 retrieval smoke-test (fast post-update gate): `90 System/_smoke_test_retrieval.py`
- Retrieval contract (pinned substrate values): `90 System/_retrieval_contract.md`
- M2 gate decision logic: `_operating_guide.md` P-8
