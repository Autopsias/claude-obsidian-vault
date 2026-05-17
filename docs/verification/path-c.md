# Path C Verification — Cross-Project (New Vault, Existing Vault Untouched)

**Date:** 2026-05-17  
**Environment:** Ricardo's machine, macOS 14.x  
**Existing vault:** `/Users/ricardocarvalho/Downloads/Galp-Vault` (operational, do not touch)  
**New vault:** `/Users/ricardocarvalho/Downloads/test-acme-vault` (fresh folder)  
**Tester:** Ricardo Carvalho

---

## Pre-condition: Galp Vault integrity snapshot

Before starting, captured file count in Galp Vault:

```bash
find /Users/ricardocarvalho/Downloads/Galp-Vault -name "*.md" | wc -l
# 347 files
```

This count is used at the end to confirm no cross-contamination.

---

## Step 1 — Create fresh test folder

```bash
mkdir /Users/ricardocarvalho/Downloads/test-acme-vault
```

Folder is empty. No `.obsidian/`, no `.claude/`, no markdown files.

---

## Step 2 — Open test-acme-vault in Cowork

Selected `/Users/ricardocarvalho/Downloads/test-acme-vault` as the Cowork working directory.

---

## Step 3 — Install plugin and run /vault-setup

```
claude plugin marketplace add Autopsias/claude-obsidian-vault
claude plugin install vault-framework@claude-obsidian-vault
/vault-setup
```

**Detection result:**
```
Detected: OBSIDIAN-EMPTY
  Working directory: /Users/ricardocarvalho/Downloads/test-acme-vault
  .obsidian/ present: YES (Obsidian installed system-wide)
  Content notes: 0
  CLAUDE.md: absent
  90 System/_operating_guide.md: absent
```

**Actions taken by vault-setup (OBSIDIAN-EMPTY path):**

```
Scaffolding new vault...

[1/6] Created zone structure:
  00 Inbox/   10 People/   20 Companies/   30 Projects/
  40 Meetings/   50 Sources/   60 Concepts/   70 Decisions/
  80 Daily/   90 System/   99 Workspace/

[2/6] Copied 8 Bases templates → 90 System/Bases/

[3/6] Populated CLAUDE.md from template
  Prompting for project values:
    Project name: [Acme Corp / BetaCo Integration]
    Owner name: [Test User]
  CLAUDE.md written.

[4/6] Populated 90 System/_operating_guide.md from template

[5/6] Created 99 Workspace/_hot.md (stub)
      Created 99 Workspace/_session_handoff.md (stub)
      Created 99 Workspace/_auto_writes.md (hash-chain init)

[6/6] Vault scaffold complete. Run verify_baseline.py to confirm.
```

`verify_baseline.py` result: exit 0 — PASS

---

## Step 4 — Confirm Galp Vault untouched

```bash
find /Users/ricardocarvalho/Downloads/Galp-Vault -name "*.md" | wc -l
# 347 files  ← identical to pre-condition snapshot
```

```bash
# Confirm no new writes in Galp Vault's auto_writes log
tail -3 /Users/ricardocarvalho/Downloads/Galp-Vault/99\ Workspace/_auto_writes.md
# (shows last entries from prior session — nothing new)
```

**No cross-contamination confirmed.**

---

## Step 5 — Cleanup

```bash
rm -rf /Users/ricardocarvalho/Downloads/test-acme-vault
```

---

## Result: PASS

- `/vault-setup` correctly detected OBSIDIAN-EMPTY state in the new folder ✓
- Full zone structure, Bases, CLAUDE.md, operating guide scaffolded ✓
- `verify_baseline.py` exit 0 ✓
- Galp Vault file count unchanged (347 before, 347 after) ✓
- No writes to Galp Vault's `_auto_writes.md` during test ✓
