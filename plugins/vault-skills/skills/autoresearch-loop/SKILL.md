---
name: autoresearch-loop
description: >
  Autonomous Karpathy-style optimization loop for ANY scorable artifact —
  SKILL.md files, prompts, agent harnesses, classification configs, synthesis
  templates, directives, any text artifact with a measurable output. Runs the
  full autoresearch pattern: baseline, propose change, test, score, keep-or-
  revert, repeat until interrupted.
---

# Autoresearch Loop

An autonomous optimization loop modelled on Karpathy's `autoresearch` and
Third Layer's `AutoAgent`. Applied here to arbitrary text artifacts.

## The core idea

Karpathy's pattern works because of geometry, not intelligence. Three files,
three constraints, one scalar. Given those, an agent edits → runs → scores →
keeps or reverts → repeats, and overnight throughput beats human iteration
rate by 10–20×.

```
READ artifact → PROPOSE one change → RUN evals (×N) → SCORE → KEEP or REVERT → REPEAT
```

The loop depends on four things being true. **Phase 0 checks them.**

## Phase 0 — Scoping gate (ALWAYS run first)

1. **Editable surface** — bounded and file-based?
2. **Metric** — single scalar with stated correlation-to-value hypothesis?
3. **Eval cost** — fits the experiment budget?
   (`eval_time × experiments ≤ available_wall_clock`)
4. **Ground truth** — named and real (gold set / oracle / benchmark /
   binary assertions / cross-model LLM judge)?
5. **Reversibility** — every change rollback-able cleanly?

5/5 → proceed. 4/5 → proceed + flag risk. 3/5 → do not proceed; fix the
weakest prerequisite first.

## Phase 1 — Setup

```bash
WORKSPACE=<chosen-path>/autoresearch-loop-$(date +%b%d)
cp -r <target> $WORKSPACE/working-copy && cd $WORKSPACE/working-copy
git init && git add -A && git commit -m "baseline"
git checkout -b autoresearch/$(date +%b%d)
```

Write `program.md` (directive, editable surface, metric, budget, stop
conditions, CAN/CANNOT). Write `evals.json` (assertions; `runs_per_eval: 3`
default). Run unchanged baseline. Tag `baseline`.

## Phase 2 — The loop

LOOP FOREVER until a stop condition fires:

1. Read git state.
2. Analyse failures.
3. Propose ONE change.
4. Commit.
5. Run all evals (parallel subagents).
6. Grade. Median across runs, mean across evals.
7. Improved → keep + tag `best`. Neutral → keep if simpler else revert.
   Worse → revert.
8. Log to `results.tsv` + `improvement_log.json`.
9. Crashes: dumb bug → fix inline; broken idea → revert + log.

### NEVER STOP

Do NOT pause to ask the human. The loop is autonomous.

### Stop conditions (ONLY reasons to halt)

- Perfect score across 3 consecutive iterations
- 20 iterations with no improvement in last 5
- 5+ approaches tried on same stubborn assertion, all failed (only if ALL
  remaining assertions are in this state)
- Human interrupt

## Phase 3 — Promotion review

Generate HTML improvement report. Present each kept change with diff,
reasoning, overfit risk, recommendation. User decides what gets promoted.

## Overfitting trap

The loop maximises the score; it has no opinion on whether the score
measures what you wanted. Every 3-5 iterations, read actual outputs — does
the score gain reflect real quality? If not, fix the eval, not the
artifact.

## Strategy guide — what works

1. Missing rules → adding them almost always fixes the assertion
2. Conflicting rules → resolve; make the main file authoritative
3. Buried rules → promote to top
4. Vague rules → make concrete and verifiable
5. Examples → sometimes more useful than another rule paragraph
6. Deletion → every line added is attention drawn from others

Anti-patterns: all-caps MUST/NEVER everywhere, multiple simultaneous
changes, overfitting to specific test cases, making the artifact longer
than necessary.

## When NOT to use

Stateful systems without revertibility. Unclear value correlation. Live
API side effects. When the bottleneck is the eval set itself.

(Distilled from the upstream autoresearch-loop skill — see the source for
the full Phase 0 audit references and the writing-assertions deep guide.)
