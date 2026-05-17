---
name: Data Residency Deep Dive
type: meeting
date: 2026-02-03
participants: [Morgan Chen, Ryan Cho, Raj Patel, James Whitfield, Priya Singh]
workstream: Data Residency
last_updated: 2026-02-03
---

## Key discussion points

- [[James Whitfield]] presented the UK-Stay architecture recommendation: BetaCo UK customer data stays in Azure UK South; Acme US data in Azure East US. No cross-border PII flows. Analytics layer replication in aggregate only.
- [[Ryan Cho]] confirmed UK GDPR Article 44–49 compliance: "The UK-Stay design is clean on transfer restrictions. My concern is the pre-acquisition backup posture."
- [[Raj Patel]] confirmed BetaCo's data platform is architecturally separable from GCP: "We can lift the data layer to Azure UK South. The question is sequencing — we need the GCP-to-Azure migration before we can deprecate the old backup paths."
- [[Priya Singh]] flagged the historical backup issue: pre-acquisition BetaCo had cross-border backup copies in AWS S3 US. This was not known at SPA signing. Ryan Cho confirmed this needs legal remediation before GDPR certification.
- Raj estimated GCP → Azure UK South data migration at 6–8 weeks. Morgan: "That puts full migration at Day 90 at the earliest — which means the Data Residency workstream is a post-100-day item for migration completion, but architecture sign-off can land at Day 75."

## Decisions made

- UK-Stay architecture adopted: [[Data Residency Architecture — UK-Stay Confirmed]].
- Architecture sign-off target: Day 75 (2026-03-31).
- Full data migration: post-100-day, target Day 120.

## Action items

- [[Ryan Cho]]: design historical backup remediation plan with [[Anna Fischer]] by 2026-02-20.
- [[Raj Patel]]: provide GCP dependency map for migration sequencing by 2026-02-17.
- [[Priya Singh]]: deliver GDPR compliance validation report by 2026-03-31.

## Tensions / concerns

- The historical backup issue is a live legal risk. Ryan Cho was direct: "This needs to be cleaned up, not papered over." Morgan agrees.
- Raj's 6–8 week migration estimate is optimistic if BetaCo-side engineering capacity is constrained (which it is, given SSO migration parallel workstream).

## Cross-references

- [[Data Residency Architecture — UK-Stay Confirmed]]
- [[Data Residency Compliance Analysis]]
- [[Sigma Partners Technical Due Diligence]]
- [[Ryan Cho]]
- [[Raj Patel]]
- [[Microsoft Azure]]
