---
name: Data Residency Compliance Analysis
type: source
document_date: 2026-02-10
is_latest_version: true
provenance: Ryan Cho (Acme Security) + Priya Singh (Sigma Partners)
workstream: Data Residency
last_updated: 2026-03-01
---

## Summary

Joint analysis by [[Ryan Cho]] and [[Priya Singh]] of BetaCo's data handling practices against UK GDPR requirements (UK GDPR Articles 44–49 on international data transfers, Article 5 data minimisation, Article 25 data protection by design). Produced to validate the UK-Stay architecture selection. Identifies one pre-existing compliance gap: cross-border backup copies in AWS S3 US.

## Key findings

- **UK GDPR transfer restriction compliance:** UK-Stay architecture (Azure UK South) is compliant with Articles 44–49. No adequacy decision required for UK-to-UK data flows; no standard contractual clauses needed for the primary data path.
- **Pre-acquisition compliance gap:** BetaCo maintained backup copies of UK customer data in an AWS S3 bucket (us-east-1) without a transfer mechanism in place. This is a pre-existing violation of Article 46. Not material to the acquisition SPA (disclosed as a known risk), but must be remediated before architecture certification.
- **Data minimisation:** BetaCo's event-stream data model collects behavioural data at high granularity. Recommend a data minimisation review post-Day 100 — not blocking for current integration.
- **Data protection by design:** BetaCo's platform has field-level encryption for PII fields. This is above minimum UK GDPR requirement and should be preserved in the Azure migration.
- **GDPR certification gate:** Architecture can be certified clean once (a) backup deletion is complete and (b) audit log demonstrates no ongoing cross-border transfers.

## Implications for Project Atlas

The historical backup issue is the only blocking item for GDPR certification. Target remediation: 2026-03-20 (deletion) + 2026-03-25 (legal certification). Architecture sign-off then follows by Day 75 (2026-03-31).

## Cross-references

- [[Data Residency Architecture — UK-Stay Confirmed]]
- [[Data Residency]]
- [[Ryan Cho]]
- [[Priya Singh]]
- [[Sigma Partners Technical Due Diligence]]
- [[2026-02-03 Data Residency Deep Dive]]
