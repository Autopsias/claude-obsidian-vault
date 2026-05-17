---
name: SSO Federation
type: concept
last_updated: 2026-03-01
---

## Definition

Single Sign-On (SSO) Federation is an identity architecture pattern in which two independent identity providers (IdPs) establish a trust relationship, allowing users authenticated by one IdP to access resources managed by the other without re-entering credentials. Federation is commonly implemented via SAML 2.0 or OpenID Connect (OIDC). In a post-acquisition context, SSO federation is typically the first technical integration step — it allows the acquired company's users to authenticate against the acquirer's IdP, enabling unified access management and the eventual deprecation of the acquired entity's standalone IdP.

## Relevance to Project Atlas

BetaCo uses Google Workspace as its SSO provider. Acme uses Okta (brokering to Azure AD). The SSO Migration workstream establishes federation by migrating BetaCo employees to Acme's Okta → Azure AD chain, and migrating BetaCo's customer-facing OAuth applications to SAML federation under Okta. The result: a single identity plane across both entities, enabling MFA policy enforcement, audit logging, and eventual Google Workspace licence deprecation ($340K/year saving).

## Counter-arguments

SSO federation adds complexity for users during the transition period — particularly BetaCo customers who have built integrations against BetaCo's Google OAuth endpoints. A poorly executed federation migration can break customer integrations and create support ticket volume. The phase-gated approach addresses this by testing the migration on employees before rolling out to customers.

## Cross-references

- [[SSO Migration Approach — Phase-Gated Adopted]]
- [[SSO Architecture Assessment v1]]
- [[Mike Okafor]]
- [[Okta]]
- [[Microsoft Azure]]
