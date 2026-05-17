# kb-curator audit mode

Read-only mechanical health check of a Cowork project knowledge base. Writes a single audit report; touches nothing else.

## Invocation

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/kb-curator/scripts/curator.py audit
```

Project root auto-detects via cwd → CLAUDE.md. Override with `--root /path/to/project` or `COWORK_ROOT` env var.

## Substrate dispatch (automatic)

The orchestrator calls `detect_substrate.py` after resolving the root and
dispatches automatically:

- **FLAT** (cowork-preparation) — writes
  `cowork_outputs/_audit_YYYY-MM-DD_kb_health.md` with the 8 FLAT probes
  (index freshness, orphans, frontmatter lint, file-size flags, log-rotation,
  archive-in-working-zone, superseded versions, promotion candidates).
  Requires `cowork_outputs/` to be present.

- **OBSIDIAN** (Johnny-Decimal vault) — chains four scripts in sequence
  (all always run so all findings are surfaced):
  1. `audit_obsidian.py` — 6 structural checks (Bases, verifier, P-rules, rules files, plans index, retrieval contract)
  2. `audit_bitemporal.py` — P-4 frontmatter conformance across typed zones
  3. `audit_rules.py` — `.claude/rules/` drift against canonical references layer
  4. `audit_plans_index.py` — `_plans_index.md` consistency vs plan HTML files

  Output is printed to stdout by each script; nothing is written to the vault
  (OBSIDIAN mode is fully read-only). Exit 0 if all scripts ran without crash;
  exit 2 if any script errored.

## What it probes (8 signals)

1. **Index freshness** — age of `cowork_outputs/_index.md`. Flag if >7 days.
2. **Orphan files** — markdown in `cowork_outputs/` not referenced by `_index.md` or any per-zone shard.
3. **Frontmatter compliance** — runs the project's own `_lint_frontmatter.py --scope cowork` and counts errors/warnings.
4. **File-size flags (P-1.2)** — `_session_handoff.md` >15 KB, `CLAUDE.md` >12 KB, state file (discovered by `type: state` frontmatter or `_*_current_state.md` filename) >120 KB.
5. **Log-rotation flags** — `_cleanup_log.md` >200 KB, `_auto_writes.md` >80 KB.
6. **Archive files in working zone** — files matching `_*_archive_*.md` directly under `cowork_outputs/` (these belong under `_archive/`).
7. **Superseded version pairs** — files matching `*_v\d+\.md` where a higher version exists with the same stem.
8. **Promotion candidates (P-10 routing)** — files in `cowork_outputs/` that pass the doneness gate, broken down by destination: `05_Knowledge_Base/*` (markdown with recognised `type:` or done-pattern filename), `02_Final_Deliverables/` (binary deliverables `.docx/.pptx/.xlsx/.pdf/.html`), and `06_Templates/` (any extension whose filename starts with `template_`, `master_`, or `brand_`). Doneness = age ≥ `COWORK_PROMOTE_AGE_DAYS` (default 14) AND cadence is in lint's KNOWN_CADENCES minus the operational ones (`per-session, continuous, append-only`).

## Output

`cowork_outputs/_audit_YYYY-MM-DD_kb_health.md` — numbered drift signals only.

## What to report to the user

Summarise the audit ranked by severity. For each non-zero probe, suggest the appropriate next mode:

- Orphans found → suggest `kb-curator refresh-index` (or `/kb-refresh-index`)
- Archive in working zone, superseded versions, or **promotion candidates** → suggest `kb-curator propose-cleanup`
- Log-size flags → suggest `kb-curator rotate-logs`
- File-size flags → recommend manual compression (state file) or session compression (handoff)
- Lint errors → recommend running `_retrofit_frontmatter.py --apply` for legacy files

## Hard guardrails

- READ-ONLY. Only the audit report itself is written. Never edit any other file.
- Never delete anything.
- Never propose changes inline — surface the appropriate sibling mode instead.
