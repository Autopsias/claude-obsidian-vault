---
name: Okta
type: company
status: vendor
last_updated: 2026-03-01
---

## Overview

Identity and access management platform. Acme Corp's SSO and MFA provider — Okta sits in front of Azure AD as the identity broker for Acme's SaaS application layer. All Acme employees authenticate via Okta. The SSO Migration workstream will extend Okta to cover BetaCo's 150 employees and configure Okta federation for BetaCo's customer-facing SSO (847 customer accounts).

## Relationship to Project Atlas

Critical identity infrastructure vendor. BetaCo currently uses Google Workspace SSO directly — no Okta layer. The migration path: BetaCo employees → Okta → Azure AD. BetaCo customer SSO: customers currently authenticate via BetaCo's Google Workspace OAuth; post-migration, they will authenticate via Okta with SAML federation. [[Mike Okafor]]'s team owns the Okta configuration.

## Key contacts

- Acme Okta account managed by [[Mike Okafor]]
- Okta Customer Success Manager engaged for migration support (name not material)

## Key agreements

- Acme Okta Enterprise agreement — 3-year, expires 2027-06
- BetaCo employee licences: 150 seats provisioned under existing agreement (no incremental cost)
- BetaCo customer SAML federation: configuration work only; no licence cost for federation

## Recent mentions

- [[2026-01-27 SSO Migration Planning]]
- [[SSO Architecture Assessment v1]]

## Cross-references

- [[SSO Federation]]
- [[SSO Migration Approach — Phase-Gated Adopted]]
- [[Microsoft Azure]]
- [[Mike Okafor]]
