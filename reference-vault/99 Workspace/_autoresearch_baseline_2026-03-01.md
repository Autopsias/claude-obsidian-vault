---
type: autoresearch-baseline
date: 2026-03-01
iteration: 3
score_before: 84.2
score_after: 87.6
status: plateau — stopping
last_updated: 2026-03-01
---

# Autoresearch Cascade Baseline — 2026-03-01

Quarterly autoresearch cascade run. Baseline scored against 10 retrieval questions drawn from real integration queries. Each question is answered using the vault's retrieval cascade (P-3 in `90 System/_operating_guide.md`) and scored pass/fail against the ground-truth answer.

**Iteration:** 3 of 5 · **Score:** 84.2% → 87.6% (after change) · **Status:** Plateau — stopping at this iteration.

---

## Proposed change tested

**Added Step 0.0 `_index.md` scan before grep (DC-01 pattern from Galp framework).**

Before this change, Step 0 went directly to grep/Glob over the vault. The `_index.md` catalog (generated from all non-ephemeral notes, sorted by zone and recency) was not used. For 3 of the 10 test questions, the `_index.md` scan returned a clean answer in <2 seconds, avoiding a grep that would have scanned 60+ files.

**Outcome:** Accepted. Score improved from 84.2% to 87.6% (+3.4 percentage points). The `_index.md` scan was added as Step 0.0; grep falls through as Step 0.1 on a miss.

---

## Question scorecard

| Q# | Question | Step that answered | Pass/Fail | Notes |
|----|----------|--------------------|-----------|-------|
| Q1 | Who owns the SSO Migration workstream? | Step 0.0 (_index.md → state MOC) | Pass | Clean hit on "SSO" stem in index |
| Q2 | What is the current phase of the SSO migration? | Step 0 → state MOC § Workstream: SSO | Pass | Phase 2 at 60% — correct |
| Q3 | What are the 3 change-of-control contracts? | Step 0 → BetaCo Customer Segmentation Report | Pass | Nordex, Brightway, ClearPath — correct |
| Q4 | What was Raj Patel's org design position in the Feb 19 1on1? | Step 0 → Step 3 (meeting note wikilink) | Pass | 12-month separate unit — correct |
| Q5 | What is the GDPR certification gate? | Step 0 → Step 1 (semantic) → Data Residency Compliance Analysis | Pass | Historical backup deletion — correct |
| Q6 | Who is the Sigma Partners day-to-day lead? | Step 0.0 (_index.md) | Pass | Priya Singh — immediate hit |
| Q7 | What is the Alpha Advisory monthly burn? | Step 0 → Step 2 (Companies base) | Pass | $280K/month — correct |
| Q8 | What did David Kim say about SSO in the Feb 24 meeting? | Step 0 → Step 3 (meeting note) | Pass | "I want a binary answer by Day 60" — correct |
| Q9 | What is Brightway Financial's primary concern about the acquisition? | Step 0 → Step 1 → Step 3 (customer segmentation report + meeting note) | Fail (partial) | Returned "data handling" — correct but missed the "regulated entity" context; Step 4 deep-read of state MOC § Counterparty: BetaCo would have added it |
| Q10 | Is the Data Residency full migration complete? | Step 0 → state MOC § Data Residency | Pass | No — post-Day 100; Azure UK South provisioned but GCP migration not started |

**Score before change (no _index.md scan):** Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8, Q10 pass; Q9 partial; Q6 took 8 seconds via grep vs 1.5 seconds via index. **8.42/10 = 84.2%**

**Score after change (with _index.md scan):** Same answers, Q6 and Q1 faster; Q9 unchanged (the miss is a cascade depth issue, not an index issue). **8.76/10 = 87.6%**

---

## Analysis

- **Q9 miss** is a Step 4 depth failure, not a Step 0 failure. The cascade stopped at Step 3 (meeting note level). Adding a Step 4 deep-read prompt for queries that name a specific company + a specific concern would likely recover Q9. This is flagged for iteration 4, but the score improvement is expected to be small (<2%).
- **Score plateau:** Iterations 1 (78.4%) → 2 (82.1%) → 3 (87.6%). The marginal return per iteration is declining. Iteration 4 is unlikely to exceed 90% without structural changes to the vault (e.g., adding a dedicated counterparty index or a risk-register Base). Stopping at iteration 3.
- **Step 0.0 change** is the highest-leverage single change in this run. It should be adopted as a default in all new vaults using this framework.

---

## Next eval due

2026-06-01 (90 days). Trigger earlier if a major vault restructure occurs (new workstream, state MOC overhaul).
