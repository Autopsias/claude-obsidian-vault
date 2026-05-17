---
name: vault-eval
description: Run the retrieval-eval harness against the vault — 33-question template scoring S (supersession-correct) + X (retrieval-complete) + T (temporal-correct) + MH (multi-hop) + CAL (calibration / refusal). Use monthly; also as the go-live gate (M2) after any structural change. Triggers on "run the eval", "vault eval", "retrieval eval", "monthly eval", "go-live gate", "score the cascade", "eval recency check". Outputs a dated baseline file with per-question scores and an aggregate. Do NOT use for ad-hoc retrieval probes — this is the scored cadence; one-off probes go in 99 Workspace/.
---

# Vault Retrieval Eval

The monthly falsifiable check on vault behaviour. Three baseline dimensions
(S / X / T), two extended dimensions (MH / CAL). Pass bar: ≥80% on each.

## When to run

- **Monthly cadence** — `vault-eval-recency` task surfaces overdue evals at
  session bootstrap.
- **M2 go-live gate** — first run is the launch gate. `<80% on any dimension
  reverts the launch.`
- **Post-structural-change** — after retrieval cascade edits, plugin
  updates, substrate changes, ingestion-pipeline contract changes. Eval
  before declaring stable.
- **Pre-promotion** — before merging any autoresearch-loop run that
  modified retrieval cascade text.

## What it scores

| Dim | Name | What it checks |
|---|---|---|
| **S** | Supersession-correct | Answer reflects latest state, not a stale version |
| **X** | Retrieval-complete | Answer pulls from all relevant zones (≥2 where appropriate) |
| **T** | Temporal-correct | Answer drawn from the version current as of the question's implied date |
| **MH** | Multi-hop | Two-or-more-entity bridge probes (Q31–Q33) traced correctly |
| **CAL** | Calibration / refusal | Confidence tier applied; vault-absent questions refused not fabricated |

**Aggregate** = `(S + X + T + MH + CAL) / 5` (mean of dimension pass-rates).

## How to run

1. **Read the template.** `templates/eval-retrieval-template.md` — 33-Q
   structure, scoring contract, route-letter tagging (A/B/C/D), per-question
   reasoning trace requirement.

2. **Customise.** Replace the example questions with project-specific ones
   sourced via the anti-cherry-pick rule (questions written BEFORE running;
   no editing after the run sees them). Minimum 10 questions at launch;
   target 25 by month 4. Distribution: L≥2, S≥2, B≥2, W≥2, D≥2 primaries.

3. **Run.** For each question:
   - Declare the route (A/B/C/D) at top of reasoning trace
   - Walk the cascade per `retrieval-cascade-discipline.md`
   - Apply Step 1.5 rerank if EN substantive + ≥2 Step-1 candidates
   - Note step-fired and confidence tier
   - Score S, X, T, MH (if applicable), CAL

4. **Record.** Append a dated baseline at
   `99 Workspace/_eval_baseline_YYYY-MM-DD.md` with: per-question row,
   per-dimension pass-rate, aggregate, regression summary against last
   baseline.

5. **Act.** If any dimension <80%, surface immediately as a vault-behaviour
   integrity flag. T3-tier closed-loop entry. Banner at next session
   bootstrap.

## Smoke test (sub-second mode)

```
python scripts/smoke_test_retrieval.py --health --root <vault>
```

Validates `.smart-env/multi/*.ajson` shape, source count, embedding
dimension. Runs on every weekly `vault-health` task. Full smoke test
(programmatic 7-fixture pass with the actual cascade) runs only on detected
substrate drift to avoid the ~10s sentence-transformers load on every
weekly run.

## Rerank

```
python scripts/rerank.py \
    --query "<your query>" \
    --candidates '<json array from Step 1>' \
    --top-k 5
```

Cross-encoder rerank via `BAAI/bge-reranker-v2-m3` (~70 MB, Apple Silicon
MPS, cached after first load). EN substantive queries with ≥2 Step-1
candidates only. Skipped on M9 fall-through.

## Faithfulness

```
python scripts/eval_faithfulness.py --baseline <eval-baseline-file>
```

Audits the per-question reasoning trace for claim/source faithfulness —
every claim must be traceable to a cited source paragraph. Catches the
case where the right file was retrieved but the answer drew on the wrong
section. Surfaces as a separate F-score adjacent to S/X/T.

## What lives where

- `templates/eval-retrieval-template.md` — the 33-Q template (15 KB; carries
  the scoring contract, cascade-step tagging, per-question fixture, anti-
  cherry-pick rule)
- `scripts/smoke_test_retrieval.py` — the runner with `--health` mode (38 KB)
- `scripts/rerank.py` — cross-encoder Step 1.5 rerank (8 KB)
- `scripts/eval_faithfulness.py` — per-question claim/source audit (28 KB)

## Pass-bar rationale

80% per dimension, not aggregate, because aggregate hides single-dimension
collapse. A vault that scores T=40% but S=100% X=100% has a temporal-
retrieval bug masked by the easy dimensions. The per-dimension bar surfaces
this. The aggregate is the executive-summary number; the per-dimension
breakdown is where the operational signal lives.

## Re-baselining triggers

After an eval, set the next:
- **Routine monthly:** first business day of the next month
- **After substrate change:** within 7 days of the change going live
- **After cascade edit:** before the edit is declared stable; before merging
  any autoresearch-loop run
- **After plugin update:** weekly hash check fires → smoke test → if drift,
  full eval before the operationally-trusted flag returns

## When NOT to use

- Ad-hoc retrieval probing — write to `99 Workspace/_probe_*.md` instead
- Single-question A/B testing — use the smoke test
- Pre-eval reasoning trace exercises — those go to lessons / reflections,
  not scored evals (anti-cherry-pick rule: scored questions are written
  before the eval runs, not adjusted during)
