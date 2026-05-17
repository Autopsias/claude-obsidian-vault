# Contributing to claude-obsidian-vault

Thanks for picking this up. The framework was extracted from a working CTO's
vault, so most opinions in here come from real operational pressure — but the
extraction is recent and rough edges remain.

## Three principles before you open a PR

1. **Templates over examples.** If a doc references a specific company, project,
   or person from the source vault, that's a leak. Replace with `[EXAMPLE:]`
   placeholders or `{{PROJECT_*}}` variables. The de-Galpify map in the source
   project lists known leaks; new contributions must not add more.

2. **Falsifiability is load-bearing.** Anything that touches retrieval, eval,
   or ingestion must come with an assertion that can fail. Adding a heuristic
   without a test that proves it improves a numeric score is a regression even
   if the code is clean.

3. **Kernel rules are universal; project rules are local.** The 9 P-rules in
   `operating-guide-template.md` are stable across any project. Anything
   project-specific belongs in an extension slot (`EXT-*`), not in the kernel.

## How to develop locally

```bash
# Clone
git clone https://github.com/Autopsias/claude-obsidian-vault.git
cd claude-obsidian-vault

# Install one plugin into a test vault
/plugin marketplace add file://$(pwd)
/plugin install vault-framework@claude-obsidian-vault

# Validate the marketplace
claude plugin validate-marketplace
```

Each sub-plugin has its own `plugin.json` and is installable independently.
The `vault-framework` plugin is the foundation — the other four assume it is
installed.

## What lives where

- `plugins/vault-framework/` — operating-guide kernel, CLAUDE.md template,
  8 .claude/rules, `/vault-setup`, `/hot`, `/promote`. The bootstrap layer.
- `plugins/vault-skills/` — active-maintenance skills (kb-curator,
  plan-builder, save-conversation, autoresearch-loop). Day-to-day tools.
- `plugins/vault-eval/` — retrieval-eval harness. Monthly cadence.
- `plugins/vault-ingestion/` — multi-format pipeline + classifier.
- `plugins/vault-voice/` — voice profile template + auto-load rule + extractor.

## What's out of scope

- LLM-side opinions about specific models, prompts, or providers — keep it
  substrate-agnostic; the framework is Claude-shaped but not Claude-bound.
- Branded presentation skills (galpify, BlackRock style, etc.) — those belong
  in private extensions, not this open-source kernel.
- Anything that requires private credentials or proprietary data to test.

## PR process

1. Fork + branch from `main`.
2. Run `claude plugin validate-marketplace` and confirm a clean install on a
   fresh test vault.
3. Open a PR with: motivation, what changed, how you tested.
4. For changes that touch retrieval-cascade behaviour or the operating-guide
   kernel: include a before/after eval delta from `vault-eval`.

## Questions?

Open an issue. The framework's strongest feature is that it surfaces drift
fast — so does the project itself.
