---
name: Acme-BetaCo Integration
type: project
codename: Project Atlas
status: active
phase: 100-day integration
close_date: 2026-01-15
last_updated: 2026-03-01
---

# Project Atlas — State MOC

Deal closed: 2026-01-15. Current date: 2026-03-01. Day 45 of 100.
Day 90 target: 2026-04-14 (SSO cutover). Day 100 target: 2026-04-25 (full integration readiness).

---

## Workstream: SSO Migration
*Last touched: 2026-03-01*

**Owner:** [[Mike Okafor]] (Acme IT Infrastructure), coordinating with [[Tom Bradley]] (BetaCo Engineering)
**Target date:** Day 90 — 2026-04-14
**Current status:** Phase 1 complete (Azure AD tenant extension + Okta licence provisioning). Phase 2 in progress (BetaCo employee directory sync — 150 accounts). Phase 3 (customer SSO federation — 847 accounts) not yet started; depends on Phase 2 completion.

**Phase summary:**
- Phase 1 (Days 1–30): Azure AD extension, Okta licence provisioning. **COMPLETE.**
- Phase 2 (Days 30–60): BetaCo employee directory sync, MFA enforcement rollout. **IN PROGRESS.** Target: 2026-03-15. 4 of 6 open blockers are BetaCo-side (Tom Bradley's team).
- Phase 3 (Days 60–90): Customer SSO federation (SAML for 847 BetaCo customer accounts). **NOT STARTED.** Depends on Phase 2 sign-off.

**Blockers:**
1. BetaCo Google Workspace admin access — provisioning delayed; [[Tom Bradley]] team capacity constrained.
2. 3 BetaCo customer accounts using custom OAuth implementation — require bespoke migration path, not covered in Phase 3 plan. [[Mike Okafor]] to scope by 2026-03-15.

**Risk:** Tom Bradley retention cliff (2026-04-15 — one day after cutover). If Bradley leaves pre-cutover, Phase 3 knowledge gap is significant. Contingency: document BetaCo-side runbook now, not after cutover.

---

## Workstream: Data Residency
*Last touched: 2026-03-01*

**Owner:** [[Ryan Cho]] (Acme Security), with [[Priya Singh]] / [[James Whitfield]] (Sigma Partners)
**Target date:** Architecture sign-off — Day 75 (2026-03-31); full migration — Day 120 (post-100-day phase)
**Current status:** UK-Stay architecture confirmed ([[Data Residency Architecture — UK-Stay Confirmed]]). Azure UK South region provisioned. BetaCo data platform assessment complete (Sigma Partners). Active blockers: historical backup remediation.

**Architecture:** Two-region strategy. BetaCo UK customer data → Azure UK South. Acme US data → Azure East US. No cross-border data flows for UK customer PII. Data processed in-region; analytics layer replicated in aggregate only (no PII replication).

**Blockers:**
1. **Historical backup issue:** Pre-acquisition BetaCo had cross-border backup copies of UK customer data in an AWS S3 US bucket. Legal remediation path being designed by [[Ryan Cho]] + [[Anna Fischer]]. Target: deletion + audit log by 2026-03-20. This is the GDPR certification gate.
2. BetaCo → Azure UK South data migration timeline not yet estimated. Raj Patel needs to provide platform dependency map first.

---

## Workstream: Customer Comms
*Last touched: 2026-03-01*

**Owner:** [[Emma Walsh]] (SVP Product, strategic), [[Claire Dubois]] (Head of Customer Success, operational)
**Decision status:** Timing decision made — post-close announcement confirmed ([[Customer Comms Timing — Post-Close Announcement]]). Announcement targeted for 2026-03-15 (Day 59).
**Current status:** Announcement draft in progress. Customer segmentation complete ([[BetaCo Customer Segmentation Report]]). Tiered outreach: Tier 1 (top 50 accounts) — personal call from [[Emma Walsh]] + account manager. Tier 2 (next 200) — personalised email + FAQ. Tier 3 (remaining 597) — mass email.

**Open items:**
1. 3 change-of-control accounts (Nordex Retail, Brightway Financial, ClearPath Logistics) require pre-announcement legal outreach — [[Anna Fischer]] + [[Sophie Andreou]] coordinating. Must land before general announcement.
2. Announcement messaging alignment with [[Linda Park]]'s earnings call narrative (Q2 earnings: April). Morgan to review draft by 2026-03-08.
3. [[Claire Dubois]] flagging elevated churn risk for 12 mid-tier accounts — recommend proactive CS outreach ahead of announcement.

---

## Workstream: Contract Novation
*Last touched: 2026-03-01*

**Owner:** [[Anna Fischer]] (BetaCo Legal), [[Sophie Andreou]] (Acme M&A Legal)
**Target date:** All 847 customer contracts novated — Day 120 (post-100-day phase). 23 vendor contracts — Day 90.
**Current status:** Novation template drafted by Freshfields (external counsel). [[Anna Fischer]] reviewing against BetaCo's original contract terms. 3 change-of-control contracts (Nordex, Brightway, ClearPath) require customer consent — outreach strategy not yet finalised.

**Complexity:**
- 847 customer contracts: varied terms, some bespoke. Segmented into 4 tiers by complexity. Tiers 3–4 (simple standard-form): bulk novation via counter-signature. Tiers 1–2 (bespoke): individual review required.
- 3 change-of-control clauses: Nordex Retail (annual revenue £800K), Brightway Financial (£420K), ClearPath Logistics (£290K). If any of these do not consent, Acme loses the contract. Combined risk exposure: £1.51M ARR.
- 23 vendor contracts: 18 straightforward novation; 5 require renegotiation (key supplier dependencies that BetaCo negotiated as a small company — terms likely to change under Acme).

---

## Counterparty: BetaCo
*Last touched: 2026-03-01*

Relationship status: cooperative but protective. [[Raj Patel]] and [[Emma Walsh]] are engaged and constructive in steerco settings. The underlying tension is cultural — BetaCo team is accustomed to startup speed and autonomy; Acme's governance structure is heavier. Signs of friction: Raj's "the Acme way vs the right way" framing in technical meetings; Tom Bradley's disengagement since late January; Claire Dubois's persistent advocacy for the pre-close announcement approach (after being overruled).

Key open tensions:
- **Tom Bradley retention:** The most material people risk in the integration. Raj Patel is aware and concerned; Morgan has one more conversation planned before the earn-out cliff. See Open Questions.
- **BetaCo engineering org home:** If BetaCo engineers are absorbed under [[Lisa Chen]] (Acme VP Engineering), cultural fit risk is high. If they remain a separate unit under Raj, the synergy case weakens. No decision yet.
- **Product roadmap sovereignty:** Emma Walsh has not publicly contested Acme product leadership decisions, but Raj has privately expressed concern about BetaCo's roadmap being "subsumed." This is a 6-month risk, not a 100-day risk, but worth tracking.

---

## Counterparty: Alpha Advisory
*Last touched: 2026-03-01*

Engagement status: active, contracted through Day 100 (2026-04-25). [[Sarah Torres]] running the IMO effectively — governance is tight, steerco preparation is good. The extension question is the live issue: [[David Kim]] is skeptical of extending at $280K/month post-Day 100. Morgan's view: a 30-day extension at reduced scope (transition-out support) is worth it; full extension is not. Decision due by 2026-04-10.

Current focus: Day 1 Readiness Review outputs (midpoint) → Day 90 readiness checklist.

---

## Counterparty: Sigma Partners
*Last touched: 2026-03-01*

Engagement status: active, fixed-fee SOW through 2026-03-31. [[James Whitfield]] + [[Priya Singh]] delivering to plan. Final deliverable: GDPR compliance validation report — due 2026-03-31 (contingent on historical backup remediation closing). No scope creep; no commercial issues. Relationship with [[Raj Patel]] is the best cross-party technical relationship in the integration — productive and direct.

---

## Open Questions
*Last touched: 2026-03-01*

1. **Tom Bradley retention:** Will he commit to staying post-earn-out cliff (2026-04-15)? What is Acme willing to offer? Morgan to have a direct conversation with Tom before 2026-03-15 — needs CFO approval for any retention package above standard renewal terms.

2. **BetaCo engineering org design:** Does the BetaCo 40-person engineering team roll up under [[Lisa Chen]] (Acme VP Engineering) or remain as a separate unit under [[Raj Patel]]? CFO and CEO decision required. Morgan's recommendation: separate unit for 12 months, then integration. Pending David Kim's headcount stance.

3. **Alpha Advisory extension:** 30-day extension at reduced scope vs clean exit at Day 100? Decision due 2026-04-10. Morgan leaning toward 30-day transition-out at ~50% fee.

4. **Change-of-control contract outreach sequencing:** Should legal outreach to Nordex, Brightway, and ClearPath happen before or after the general customer announcement (2026-03-15)? Sophie Andreou's view: before. Claire Dubois's view: simultaneously, to avoid those customers feeling "special-cased." Anna Fischer: before, from a legal risk standpoint. Morgan agrees with legal — pre-announcement outreach to the 3 accounts. Awaiting Linda Park confirmation.

---

## Recent Decisions

- [[SSO Migration Approach — Phase-Gated Adopted]] — 2026-01-27
- [[Data Residency Architecture — UK-Stay Confirmed]] — 2026-02-03
- [[Customer Comms Timing — Post-Close Announcement]] — 2026-02-10

---

## Key Risks
*Last touched: 2026-03-01*

| Risk | Probability | Impact | Owner | Mitigation |
|------|-------------|--------|-------|------------|
| Tom Bradley exits post-earn-out cliff (2026-04-15) | High | High — SSO migration knowledge gap; BetaCo engineering team morale | [[Morgan Chen]] | Direct retention conversation by 2026-03-15; document BetaCo runbook now |
| Change-of-control contracts (Nordex, Brightway, ClearPath) withhold consent | Medium | High — £1.51M ARR at risk | [[Sophie Andreou]] / [[Anna Fischer]] | Pre-announcement outreach; account relationship assessment by [[Claire Dubois]] |
| Historical backup cross-border issue delays GDPR cert | Medium | Medium — Data Residency sign-off slips past Day 75 | [[Ryan Cho]] | Legal remediation plan by 2026-03-20; parallel-path architecture certification where possible |
