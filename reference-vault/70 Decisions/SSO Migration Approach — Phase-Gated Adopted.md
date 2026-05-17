---
name: SSO Migration Approach — Phase-Gated Adopted
type: decision
status: decided
date: 2026-01-27
decision_maker: Morgan Chen
workstream: SSO Migration
last_updated: 2026-01-27
---

## Decision

Adopt a three-phase gated SSO migration approach, targeting full cutover on Day 90 (2026-04-14). Phase 1: Azure AD extension + Okta provisioning (Days 1–30). Phase 2: BetaCo employee directory sync + MFA enforcement (Days 30–60). Phase 3: Customer SSO federation for 847 BetaCo accounts (Days 60–90). Day 60 contingency review (2026-03-15) added as an explicit go/no-go gate before committing to Phase 3 execution.

## Rationale

A phased approach was chosen over a single big-bang cutover to reduce operational risk. Each phase has a defined scope and a verification gate before the next phase begins. The Day 60 gate provides a structured escalation point if Phase 2 is delayed — rather than discovering a Day 90 failure at Day 85. The Google Workspace licence deprecation ($340K/year) creates a hard financial incentive to hold the Day 90 date.

## Alternatives considered

1. **Big-bang cutover (Day 90):** Single cutover of all 850 accounts (150 employees + 847 customers) simultaneously. Rejected — operational risk is too high; a failure mid-cutover affects BetaCo's customer-facing product.
2. **Extended timeline (Day 120):** More conservative phasing, reducing schedule risk. Rejected — the $340K/year Google Workspace licence cost savings begin Day 91; a 30-day slip costs $28K and erodes the synergy model.
3. **Customer SSO as a separate workstream (post-Day 100):** Migrate employee SSO by Day 90; defer customer SSO. Considered — would reduce Day 90 scope significantly. Not adopted because the customer SSO migration is required for the contract novation to be technically complete.

## Implications

- [[Mike Okafor]] is accountable for Phase 1 and Phase 3. [[Tom Bradley]] is accountable for BetaCo-side delivery in Phase 2.
- Tom Bradley's retention cliff (2026-04-15) is one day after Day 90 — this is the dominant people risk to this decision.
- Day 60 review must include a binary go/no-go, not just a status update.

## Counter-arguments

The extended timeline alternative remains valid if Phase 2 runs significantly behind. If the Day 60 review shows Phase 2 is less than 80% complete, [[Morgan Chen]] should revisit the Day 90 commitment rather than force a risky Phase 3 execution.

## Cross-references

- [[SSO Architecture Assessment v1]]
- [[SSO Federation]]
- [[Mike Okafor]]
- [[Tom Bradley]]
- [[2026-01-27 SSO Migration Planning]]
- [[Integration Risk Register]]
