# Changelog

All notable changes to `claude-obsidian-vault` will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-05-17

### Added

**Marketplace structure**
- `marketplace.json` listing 5 plugins under `.claude-plugin/`
- MIT `LICENSE`

**vault-framework** (the kernel plugin)
- `CLAUDE.md` template with stable-prefix discipline
- Operating-guide kernel — 9 universal P-rules covering bootstrap, retrieval cascade, write autonomy, versioning, ingestion, and maintenance
- 5-step retrieval cascade: lexical → semantic → Bases → link-expand → deep-read
- 9 `.claude/rules/` disciplines: session-bootstrap, retrieval-cascade, auto-write, freshness, inbox, daily-notes, mount, state-moc-edit, plugin-security
- `/vault-setup` scaffolder — detects 4 install states (new/existing × Obsidian/flat) and acts accordingly
- `/hot` orientation surface (≤2 KB always-fresh session primer)
- `/promote` workspace→typed-zone ritual with P-10 quality filter
- 8 Bases templates (People, Companies, Projects, Meetings, Sources, Decisions, Open Items, Version Chain)
- 4 note templates (decision, meeting, source, operating-guide)
- `scripts/populate-claude-md.py` — interpolates `values.yaml` into the CLAUDE.md template
- `scripts/bases-verifier.py` — validates Bases coverage against vault zones

**vault-skills** (maintenance skill bundle)
- `kb-curator` — audit / lint / refresh-index / rotate-logs / upgrade-flat-to-obsidian
- `plan-builder` — self-contained HTML session-tracker dashboards with donuts, arc, and infographic
- `save-conversation` — promotes chat analysis to typed vault note with P-10 quality filter
- `autoresearch-loop` — Karpathy-style scored optimisation loop for any text artefact

**vault-eval** (retrieval eval harness)
- 33-question eval template (5 dimensions: S / X / T / MH / CAL)
- Sub-second smoke test (`smoke_test_retrieval.py`)
- Cross-encoder rerank at Step 1.5 (`rerank.py`, `BAAI/bge-reranker-v2-m3`)
- Faithfulness eval (`eval_faithfulness.py`)

**vault-ingestion** (multi-format ingestion pipeline)
- 8-format handlers: PDF / DOCX / PPTX / XLSX / HTML / MD / TXT / image
- `purpose.md` classifier
- Frontmatter contract with `pipeline:` namespace
- Three-tier dedup: binary SHA / text-hash / semantic soft-warning
- `backfill_manifest.py` for retro-ingestion

**vault-voice** (personal voice layer)
- Voice-profile template (Layer A — author-specific durable voice)
- Writing-craft template (Layer B — universal Pyramid / BLUF / SCQA frameworks)
- `/voice` skill: DRAFT / REWRITE / CHECK modes with 25-item pre-ship checklist
- `scripts/populate-voice-profile.py` — distils a corpus of authored prose into a calibrated profile
- `rules/voice-discipline.md` — auto-loads both layers on document-generation paths

**Docs and scripts**
- `README.md` with Karpathy-anchor philosophy and quick-start
- `INSTALL.md` — three install paths (A: existing Obsidian, B: fresh install, C: cross-project)
- `USAGE.md` — 10 task-oriented sections
- `ARCHITECTURE.md` — 9 P-rules, cascade, eval, audit-chain
- `scripts/bootstrap.sh` — idempotent Path B installer (Homebrew, Obsidian cask, plugin URIs)
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.gitignore`
- `.github/ISSUE_TEMPLATE/` — bug, feature, rule-change templates
- `.github/workflows/ci.yml` — PR validation (JSON schema + smoke test)
- `docs/verification/` — Path A, B, C clean-room transcripts

**Reference vault** (`reference-vault/`)
- 62 files — fictional Acme Corp / BetaCo / Project Atlas scenario
- 16 People, 6 Companies, 1 state MOC, 10 Meetings, 5 Sources, 3 Decisions, 5 Concepts
- Operating guide, 7 Bases, `_hot.md`, session handoff, autoresearch baseline

[0.1.0]: https://github.com/Autopsias/claude-obsidian-vault/releases/tag/v0.1.0
