---
name: Microsoft Azure
type: company
status: vendor
last_updated: 2026-03-01
---

## Overview

Cloud infrastructure provider. Acme Corp's primary cloud platform (Azure East US for production workloads, Azure West US for DR). BetaCo was on Google Cloud (GCP) pre-acquisition. The Project Atlas data residency design requires BetaCo workloads to migrate from GCP to Azure UK South — this is the principal infrastructure migration in the Data Residency workstream.

## Relationship to Project Atlas

Critical infrastructure vendor. Acme's existing Microsoft Enterprise Agreement has been extended to cover Azure UK South for BetaCo workloads. Azure Active Directory (Azure AD) is the target identity provider for the SSO Migration (BetaCo currently on Google Workspace SSO). Azure UK South is the chosen region for UK GDPR data residency compliance — confirmed in the UK-Stay architecture design.

## Key contacts

- Acme Enterprise Account Manager (Microsoft): relationship managed by [[Mike Okafor]]
- No direct Microsoft involvement in integration design — architecture owned by [[Sigma Partners]] and [[Ryan Cho]]

## Key agreements

- Acme Microsoft Enterprise Agreement — extended to include Azure UK South (amendment executed 2026-02-01)
- Azure AD licences for BetaCo 150 employees: provisioned, pending SSO migration cutover
- Azure UK South capacity reservation: committed through 2027

## Recent mentions

- [[2026-01-27 SSO Migration Planning]]
- [[2026-02-03 Data Residency Deep Dive]]

## Cross-references

- [[SSO Federation]]
- [[Data Residency]]
- [[Mike Okafor]]
- [[Ryan Cho]]
- [[Okta]]
