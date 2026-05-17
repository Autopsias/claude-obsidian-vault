---
name: SSO Architecture Assessment v1
type: source
document_date: 2026-01-27
is_latest_version: true
provenance: Mike Okafor (Acme IT Infrastructure)
workstream: SSO Migration
last_updated: 2026-03-01
---

## Summary

Internal assessment produced by [[Mike Okafor]] following the SSO Migration Planning meeting (2026-01-27). Documents the current-state BetaCo SSO architecture (Google Workspace OAuth, no Okta layer), the target-state architecture (Okta → Azure AD, SAML federation for customer accounts), and the three-phase migration plan. Identifies 3 BetaCo customer accounts with custom OAuth implementations requiring bespoke migration paths.

## Key findings

- **Current state:** BetaCo employees authenticate via Google Workspace SSO. BetaCo customers authenticate via BetaCo-managed Google OAuth apps (one per major customer integration). No MFA enforcement on BetaCo's customer-facing SSO.
- **Target state:** All BetaCo employees provisioned in Acme's Okta → Azure AD chain. Customer SSO migrated to SAML federation under Okta. MFA enforced for all accounts post-cutover.
- **Phase 1 scope:** Azure AD tenant extension + Okta licence provisioning for 150 BetaCo employees. Estimated effort: 3 weeks. Dependencies: BetaCo Google Workspace admin access.
- **Phase 2 scope:** Employee directory sync, group policy alignment, MFA rollout. Estimated effort: 4 weeks. Dependencies: Phase 1 complete; [[Tom Bradley]] team availability.
- **Phase 3 scope:** Customer SSO federation — 847 accounts. Standard path: SAML. Bespoke path: 3 custom OAuth accounts (Nordex Retail, Brightway Financial, ClearPath Logistics). Estimated effort: 6 weeks. Dependencies: Phase 2 complete.
- **Risk:** Custom OAuth accounts are the same 3 accounts with change-of-control clauses. Coordination between SSO migration and customer novation outreach is required.

## Implications for Project Atlas

Phase 3 is the critical path for Day 90. The 6-week estimate for Phase 3 means Phase 2 must complete no later than 2026-03-01 to preserve the Day 90 date. Current Phase 2 status (Day 45): 60% complete. The Day 60 review is the go/no-go gate.

## Cross-references

- [[SSO Migration Approach — Phase-Gated Adopted]]
- [[SSO Federation]]
- [[Mike Okafor]]
- [[Tom Bradley]]
- [[Okta]]
- [[Microsoft Azure]]
- [[2026-01-27 SSO Migration Planning]]
