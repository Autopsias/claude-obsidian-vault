<!-- KERNEL: Enforces P-3 (retrieval cascade) from the operating guide as an
     always-on pre-answer reminder. Auto-loads every session — no path gate.
     The "substantive query" threshold is universal; trigger phrases and
     counterparty examples in the PROJECT-SPECIFIC section adapt per project. -->

# Retrieval cascade discipline

P-3 (`90 System/_operating_guide.md`) is the load-bearing retrieval rule
of this vault. Documented but commonly under-enforced — the typical
failure mode is stopping at Step 0 (lexical grep) when the query would
have benefited from Step 1 (semantic), Step 2 (Bases), or Step 3
(wikilink expansion).

## Pre-answer checklist (substantive queries)

A **substantive query** = anything that informs a decision, meeting,
document, stakeholder communication, or any output {{USER_FIRST_NAME}}
will act on. Quick factual lookups (e.g. "when is X scheduled?") are
exempt and may stop at Step 0.

Before drafting the **final** answer on a substantive query, Claude MUST
have:

1. **Routed** via the Step −1 temporal-intent matrix (Route A / B / C / D)
2. **Walked the steps the route prescribes** — at minimum Step 0; for
   Route D (the default, no temporal signal), also Step 1 (semantic via
   `mcp__smart-connections__lookup`, unless query is in
   {{NON_ENGLISH_LANGUAGE}} → skip per M9 caveat), Step 2 (Bases), and
   at least one Step 3 wikilink expansion from a top hit
3. **Considered Step 4 deep-reads** of the highest-signal anchored
   sections in the state MOC or other long files

If any step is skipped, the answer must **explicitly state which steps
were skipped and why**. Do not silently truncate the cascade.

<!-- PROJECT-SPECIFIC: Trigger phrases below are universal English; the
     counterparty examples should be replaced with the project's named
     counterparties (e.g. "Moeve, PwC, McKinsey" in Galp Vault). -->

## Trigger phrases that auto-classify as substantive

- "battleplan", "prep", "briefing", "meeting prep"
- "what's our position on", "what do we think about"
- "summarise", "analyse", "draft", "write up"
- Anything involving named counterparties — examples in this project:
  {{COUNTERPARTY_EXAMPLES}}
- Anything involving named workstreams, decisions, or open questions

## Quick lookups (exempt — may stop at Step 0)

- "When did X happen?"
- "Who owns Y?"
- "What's the file path for Z?"
- "Show me the latest version of N"

## Reasoning-trace opener

State the route at the top of the trace **before** retrieving. Example:

> Route D (no temporal signal). Walking Step 0 → 1 → 2 → 4. Skipping
> Step 3 — no need to expand from a single anchor for this query.

This makes the cascade legible and reviewable. It also forces
classification before action.

## Why

Lexical grep alone systematically under-recalls on Obsidian vaults that
invest in frontmatter typing, wikilink graphs, and semantic substrate —
those layers were built specifically to compensate for grep's blind
spots. Stopping at Step 0 is the dominant Claude failure mode.

## How to apply

When a query arrives, classify it first (substantive vs lookup). For
substantive queries, walk the cascade in route order. If a step
genuinely doesn't fit the query shape, state it — do not skip silently.
The eval at `90 System/_eval_retrieval.md` is downstream of this
discipline and will detect concealed misses; the route letter in the
reasoning trace is what makes that scorable.

## Cross-references

- `90 System/_operating_guide.md` — P-3 full definition, M9 multilingual
  fall-through, Step −1 temporal-intent matrix, dead-end acceptance
  template
- `CLAUDE.md` — Retrieval Cascade (M1) stable-prefix pointer
- `90 System/_eval_retrieval.md` — Q18 / Q19 / Q20 route eval
- `90 System/Bases/` — Bases the cascade routes through
- `90 System/_retrieval_contract.md` — pinned substrate (model, source
  count, rebuild procedure)
