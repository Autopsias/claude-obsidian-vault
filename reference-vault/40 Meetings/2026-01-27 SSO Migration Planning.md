---
name: SSO Migration Planning
type: meeting
date: 2026-01-27
participants: [Morgan Chen, Mike Okafor, Tom Bradley, Raj Patel]
workstream: SSO Migration
last_updated: 2026-01-27
---

## Key discussion points

- [[Mike Okafor]] walked through the phase-gated SSO migration plan: 3 phases over 90 days. [[Tom Bradley]] confirmed BetaCo-side feasibility for Phases 1 and 2 but flagged Phase 3 (customer SSO) as "aggressive."
- [[Raj Patel]] pushed back on Day 90 customer SSO cutover: "847 accounts, some with custom OAuth — we need a proper assessment before committing to that date." Morgan held the date but agreed to add a contingency review at Day 60.
- [[Mike Okafor]] confirmed Azure AD tenant extension is in progress; Okta licences provisioned. Phase 1 completion target: 2026-02-15.
- Tom Bradley presented a BetaCo Google Workspace admin access issue — provisioning request submitted but stuck in Acme IT queue. Mike to resolve.
- 3 BetaCo customers identified with custom OAuth implementations — require bespoke migration paths not in the standard plan.

## Decisions made

- Phase-gated SSO migration plan adopted: [[SSO Migration Approach — Phase-Gated Adopted]].
- Day 60 contingency review added: 2026-03-15.
- Tom Bradley to provide BetaCo-side runbook draft for Phases 1–2 by 2026-02-10.

## Action items

- [[Mike Okafor]]: resolve BetaCo Google Workspace admin access by 2026-02-01.
- [[Tom Bradley]]: BetaCo-side runbook draft by 2026-02-10.
- [[Mike Okafor]]: scope custom OAuth migration paths by 2026-02-15.

## Tensions / concerns

- Raj's pushback on Day 90 is technically credible. Morgan flagged: "If Raj is right, we need to know by Day 60, not Day 85."
- Tom Bradley was engaged in this meeting — more than he has been in cross-company settings. Positive signal.

## Cross-references

- [[SSO Architecture Assessment v1]]
- [[SSO Migration Approach — Phase-Gated Adopted]]
- [[Mike Okafor]]
- [[Tom Bradley]]
- [[Raj Patel]]
- [[Okta]]
- [[Microsoft Azure]]
