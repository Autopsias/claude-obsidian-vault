---
name: Sigma Partners Technical Due Diligence
type: source
document_date: 2026-01-30
is_latest_version: true
provenance: James Whitfield + Priya Singh (Sigma Partners)
workstream: Data Residency
last_updated: 2026-03-01
---

## Summary

Technical due diligence report on BetaCo's data platform, produced by [[Sigma Partners]] ([[James Whitfield]] and [[Priya Singh]]) in the first two weeks post-close. Covers BetaCo's data architecture, GCP infrastructure footprint, UK GDPR data handling practices, and the feasibility of the UK-Stay migration to Azure UK South. Commissioned by [[Morgan Chen]]; reviewed by [[Raj Patel]] and [[Ryan Cho]].

## Key findings

- **Architecture quality:** BetaCo's event-stream data platform is well-designed for its scale. Custom architecture (not off-the-shelf); built on GCP (Pub/Sub, Dataflow, Firestore, BigQuery). Raj Patel's team built it with strong data locality discipline — most UK customer data was already UK-region in GCP (europe-west2), which simplifies the Azure UK South migration.
- **GCP → Azure migration feasibility:** Tractable but non-trivial. Three GCP services without direct Azure equivalents: Cloud Dataflow → Azure Data Factory (migration path exists but requires pipeline rewrites); Firestore → Cosmos DB (data model compatible; migration tooling available); Cloud Composer → Azure Data Factory managed pipelines. Estimated migration effort: 8–10 engineering weeks at full capacity.
- **UK GDPR posture:** Generally good, with one pre-existing gap (cross-border backup to AWS S3 US). BetaCo team has strong data-by-design instincts; field-level PII encryption in place.
- **Scalability:** BetaCo's platform can scale to Acme's US customer volumes with architectural extensions, but this is a future-state question, not a 100-day integration question.
- **Integration risk:** The primary technical risk is capacity — BetaCo's engineering team is small relative to the integration workload. Any parallel SSO migration workload materially constrains the data migration timeline.

## Implications for Project Atlas

The data platform is an asset, not a liability. Raj Patel's architecture is better than the pre-acquisition technical due diligence suggested. The constraint is capacity, not quality. The 8–10 week migration estimate under full capacity becomes 12–16 weeks if BetaCo engineering is split across SSO migration. This is why the data migration is now a post-Day-100 workstream.

## Cross-references

- [[Data Residency Architecture — UK-Stay Confirmed]]
- [[Data Residency Compliance Analysis]]
- [[James Whitfield]]
- [[Priya Singh]]
- [[Raj Patel]]
- [[2026-02-26 Sigma Partners Data Assessment]]
- [[2026-02-03 Data Residency Deep Dive]]
