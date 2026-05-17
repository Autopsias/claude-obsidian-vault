---
name: Tech Separation
type: concept
last_updated: 2026-03-01
---

## Definition

Tech separation (or technology carve-out) refers to the process of separating the technology infrastructure, systems, and data of two previously integrated entities — typically in divestiture or joint venture contexts. In an acquisition context, the term is sometimes used to describe the reverse: the process of integrating the acquired entity's technology into the acquirer's technology estate, which requires first separating the acquired entity's systems from its prior owner's or from shared SaaS dependencies.

## Relevance to Project Atlas

BetaCo's technology estate (GCP infrastructure, Google Workspace, BetaCo's SaaS product) must be separated from its prior shared-services dependencies (Google Workspace SSO, GCP billing, BetaCo's own vendor contracts) and integrated into Acme's technology estate (Azure AD, Okta, Azure cloud). This is not a divestiture tech separation, but the operational discipline is the same: identify shared dependencies, establish a clean break point, and migrate in phases. The three-phase SSO migration and the UK-Stay data residency migration are the two main tech separation workstreams.

## Counter-arguments

Full tech separation is expensive and time-consuming. A lighter-touch integration (BetaCo retains its own infrastructure under Acme ownership, with only identity and billing integration) would be faster and cheaper. This was not chosen because Acme's synergy case depends on infrastructure consolidation — the Google Workspace licence deprecation alone is $340K/year, and the long-term product integration requires a shared Azure foundation.

## Cross-references

- [[SSO Federation]]
- [[Data Residency]]
- [[SSO Migration Approach — Phase-Gated Adopted]]
- [[Data Residency Architecture — UK-Stay Confirmed]]
- [[Raj Patel]]
