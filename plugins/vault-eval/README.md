# vault-eval

The retrieval-eval harness for the disciplined Obsidian vault. Falsifiable
monthly cadence that turns vault behaviour into a number you can defend.

## What it ships

```
vault-eval/
├── .claude-plugin/plugin.json
├── skills/vault-eval/SKILL.md
├── templates/
│   └── eval-retrieval-template.md     # 33-question template
└── scripts/
    ├── smoke_test_retrieval.py        # Sub-second --health mode + full eval
    ├── rerank.py                      # BAAI/bge-reranker-v2-m3 cross-encoder
    └── eval_faithfulness.py           # Claim/source faithfulness audit
```

## The eval dimensions

| Dim | Scores |
|---|---|
| **S** (supersession-correct) | Latest version of the answer surface? |
| **X** (retrieval-complete) | All relevant zones cross-referenced? |
| **T** (temporal-correct) | Right version-as-of-implied-date? |
| **MH** (multi-hop) | Two-entity bridge probes traced correctly? |
| **CAL** (calibration) | Confidence tier applied, refusals where vault-absent? |

Pass bar: ≥80% on each, not aggregate. Aggregate is `(S+X+T+MH+CAL)/5` —
that's the executive-summary number, but the per-dimension breakdown is
where the operational signal lives.

## Cadence

- **Monthly** — first business day of next month. `vault-eval-recency`
  surfaces overdue evals at session bootstrap.
- **M2 go-live gate** — first run is the launch gate. <80% on any dimension
  reverts launch.
- **Post-structural change** — within 7 days of any retrieval cascade
  edit, plugin update, substrate change, or ingestion-pipeline contract
  change.

## How it composes with the other plugins

- `vault-framework` ships the rules the eval verifies (cascade, confidence,
  routing matrix).
- `vault-skills/autoresearch-loop` uses this plugin's eval as the score
  function for cascade optimisation runs.
- `vault-ingestion` triggers a smoke test on each ingestion run; failures
  cascade into the eval recency check.

## Version

`0.1.0` — initial extraction. Question content is project-specific (anti-
cherry-pick rule); only the scoring contract and step-tagging system are
universal kernel.
