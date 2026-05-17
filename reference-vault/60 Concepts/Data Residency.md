---
name: Data Residency
type: concept
last_updated: 2026-03-01
---

## Definition

Data residency refers to the physical or legal requirement that data be stored and processed within a specific geographic jurisdiction. In the UK context, UK GDPR (retained EU law, post-Brexit) imposes restrictions on the international transfer of UK personal data (Articles 44–49), requiring either an adequacy decision, standard contractual clauses, or binding corporate rules for transfers outside the UK. Data residency architecture decisions therefore have direct regulatory compliance implications, not merely operational ones.

## Relevance to Project Atlas

BetaCo holds UK customer data subject to UK GDPR. The acquisition requires a decision on where that data lives post-integration. The UK-Stay architecture (data remains in Azure UK South) was chosen to eliminate transfer restriction complexity and provide a clean compliance posture for BetaCo's regulated enterprise customers. A pre-existing compliance gap — cross-border backup copies in AWS S3 US — must be remediated before the architecture can be certified.

## Counter-arguments

UK-Stay adds infrastructure complexity: two separate Azure regions, separate data governance, and a more complex long-term analytics integration path. If Acme and BetaCo's products eventually merge, the two-region architecture will need to be redesigned. This is a known trade-off: compliance and customer trust now, architecture simplification later.

## Cross-references

- [[Data Residency Architecture — UK-Stay Confirmed]]
- [[Data Residency Compliance Analysis]]
- [[Sigma Partners Technical Due Diligence]]
- [[Ryan Cho]]
- [[Microsoft Azure]]
