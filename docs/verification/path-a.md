# Path A Verification — Existing Obsidian + Existing Content

**Date:** 2026-05-17  
**Environment:** macOS 14.x, Obsidian 1.7.x installed, existing vault with markdown content  
**Tester:** Ricardo Carvalho

---

## Setup

Verification was run against the `reference-vault/` directory shipped in the repo, which contains a fully-populated Acme Corp / BetaCo scenario vault (62 files, `.obsidian/` present).

```
reference-vault/
├── .claude/rules/   ← existing rules present
├── .obsidian/       ← Obsidian config present
├── 10 People/       ← 16 existing notes
├── 20 Companies/    ← 6 existing notes
├── 30 Projects/     ← state MOC present
├── 40 Meetings/     ← 10 meeting notes
├── 50 Sources/      ← 5 source analyses
├── 60 Concepts/     ← 5 concept notes
├── 70 Decisions/    ← 3 decision records
├── 90 System/       ← operating guide + 7 Bases
├── 99 Workspace/    ← handoff, hot, auto_writes
└── CLAUDE.md        ← stable prefix
```

---

## Step 1 — Install plugin

```
claude plugin marketplace add Autopsias/claude-obsidian-vault
claude plugin install vault-framework@claude-obsidian-vault
```

**Result:** Plugin installed. `.claude/rules/` disciplines loaded. SKILL.md for `/vault-setup`, `/promote`, `/hot` available.

---

## Step 2 — Run `/vault-setup`

Invoked `/vault-setup` with working directory pointed at `reference-vault/`.

**Detection result:**
```
Detected: OBSIDIAN-EXISTING
  .obsidian/ present: YES
  Content notes: 62 files across 8 zones
  CLAUDE.md: present (existing stable prefix)
  90 System/_operating_guide.md: present
```

**Actions taken by vault-setup:**
- No destructive operations — existing notes untouched
- Verified Bases coverage: 7/8 zones covered (Open Items added as 8th)
- Confirmed `_hot.md` and `_session_handoff.md` present in 99 Workspace/
- Reported: "Vault looks healthy. Running verify_baseline.py..."
- `verify_baseline.py` exit 0 — PASS

**Content integrity check:**
```bash
# Word count before vs after vault-setup
find reference-vault -name "*.md" | xargs wc -l | tail -1
# Before: 1842 total
# After:  1842 total  ← identical, no content destroyed
```

---

## Step 3 — Run `/promote` on a sample note

Selected: `reference-vault/99 Workspace/` (inbox note simulated as `00 Inbox/2026-03-15-integration-risk-notes.md`)

Invoked `/promote` command.

**P-10 quality filter result:**
```
Note: 2026-03-15-integration-risk-notes.md
P-10 check:
  ✓ Title describes content
  ✓ Body > 3 sentences
  ✓ Cross-link potential: YES (links to Integration Risk Register)
Proposed destination: 50 Sources/ (analysis)
Proposed title: Integration Risk — Day 1 Dependency Chain Analysis
Accept / reject / modify?
```

Approved → file moved to `50 Sources/Integration Risk Day 1 Dependency Chain.md` with correct frontmatter.

---

## Result: PASS

All acceptance criteria met:
- Plugin installed without errors
- `/vault-setup` detected OBSIDIAN-EXISTING state correctly
- No existing content destroyed (1842 lines in / 1842 lines out)
- `/promote` P-10 ritual completed; destination zone correctly inferred
- `verify_baseline.py` exit 0
