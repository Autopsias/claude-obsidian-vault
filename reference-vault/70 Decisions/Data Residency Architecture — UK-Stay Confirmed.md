---
name: Data Residency Architecture — UK-Stay Confirmed
type: decision
status: decided
date: 2026-02-03
decision_maker: Morgan Chen
workstream: Data Residency
last_updated: 2026-02-03
---

## Decision

Adopt the UK-Stay architecture for BetaCo's UK customer data: all BetaCo UK customer PII and operational data to remain in Azure UK South. Acme US data remains in Azure East US. No cross-border PII data flows in the primary data path. Analytics layer replication permitted in aggregate (non-PII) form only. Architecture sign-off target: Day 75 (2026-03-31).

## Rationale

UK GDPR Articles 44–49 restrict international transfers of UK personal data without an appropriate transfer mechanism. The UK-Stay architecture eliminates transfer risk entirely by keeping UK customer data in-region. This is the cleanest compliance posture and removes ongoing legal uncertainty about the adequacy framework between the UK and US (currently under UK ICO review). The two-region architecture also aligns with Acme's existing multi-region Azure strategy.

## Alternatives considered

1. **US-centralised architecture:** Migrate all BetaCo data to Azure East US under a UK-to-US Standard Contractual Clause (SCC) mechanism. Rejected — SCC compliance adds ongoing legal overhead; adequacy framework uncertainty creates future risk; BetaCo enterprise customers (especially Brightway Financial, regulated entity) would likely object.
2. **Hybrid with selective replication:** Some BetaCo UK customer data migrated to US for analytics integration with Acme's US data platform. Rejected — PII boundary management becomes complex and audit-unfriendly; [[Ryan Cho]]'s view was that this approach "creates legal risk for marginal technical benefit."
3. **Delay decision to Day 60:** Deferring the architecture decision to allow more due diligence time. Rejected — the Azure UK South provisioning has a lead time; delaying the decision delays the architecture sign-off and GDPR certification.

## Implications

- BetaCo's GCP infrastructure migrates to Azure UK South — 8–10 engineering weeks under full capacity, extending to Day 120 post the 100-day integration phase.
- Pre-existing backup cross-border issue (AWS S3 US) must be remediated before GDPR certification. Target: deletion by 2026-03-20.
- Brightway Financial's data handling concern (change-of-control account) can be directly addressed with the UK-Stay architecture — this is a selling point in the novation outreach.

## Counter-arguments

The US-centralised architecture would simplify the analytics integration path and reduce infrastructure complexity. If BetaCo's product eventually merges into Acme's platform (a longer-term question), a cross-border architecture will need to be designed anyway. However, the current 100-day priority is compliance and customer trust, not long-term product architecture.

## Cross-references

- [[Data Residency Compliance Analysis]]
- [[Sigma Partners Technical Due Diligence]]
- [[Data Residency]]
- [[Ryan Cho]]
- [[2026-02-03 Data Residency Deep Dive]]
