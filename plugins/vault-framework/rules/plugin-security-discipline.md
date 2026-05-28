---
paths:
  - ".obsidian/**/*"
  - "90 System/_plugin_security.md"
  - "90 System/_smoke_test_retrieval.py"
---

# Plugin security discipline

**[PROJECT-SPECIFIC: Substitute your vault's plugin whitelist, hash baseline,
and pinned version. The three load-bearing rules below are universal kernel.]**

Source of truth: `90 System/_plugin_security.md` (M10 audit).

## Three load-bearing rules (universal kernel)

1. **No plugin install without explicit user trigger.** The community-plugins
   whitelist for this vault is `[PROJECT_PLUGIN_WHITELIST]`. Adding a new
   plugin requires (a) running a security audit on that plugin covering purpose,
   permissions, vendor, licence, last-update, and hash, (b) user decision to
   accept, (c) hash baseline refresh in `90 System/_plugin_security.md` and
   `99 Workspace/_plugin_hash_baseline.txt`. Obsidian CORE plugins (Bases,
   Templates, etc.) are exempt — their trust posture is the same as Obsidian.

2. **Plugin updates are gated by the M11 retrieval smoke-test, automatic on
   detected drift.** Routine path: when the weekly health check (rule 3)
   detects `.obsidian/plugins/` hash drift, the health skill automatically
   runs `python3 "90 System/_smoke_test_retrieval.py"`, captures the exit
   code, writes the verdict into
   `99 Workspace/_audit_YYYY-MM-DD_plugin_drift.md`, and surfaces a HARD
   ALERT on next session start if the smoke-test exits non-zero. Manual run
   is the **fallback** — run the smoke-test directly only if (a) the weekly
   health check has not yet fired since the plugin change, (b) the skill is
   unavailable, or (c) you want to gate-check before applying a planned
   manual update.

   Before any manual update: tarball the existing plugin directory (keep one
   pre-update tarball). On smoke-test failure (exit 1 — fixture miss, or
   exit 2 — substrate / dependency error), downgrade by `git restore` on the
   affected plugin directory (or restore the most recent pre-update tarball).
   The smoke-test must subsequently pass before retrieval is operationally
   trusted again. The smoke-test is the gate from "provisional" to "accepted".

   The `--health` sub-second mode runs on EVERY weekly health check as cheap
   substrate-shape insurance (validates `.smart-env/multi/*.ajson`, source
   count, embedding dimension); the full smoke-test runs only on drift to
   avoid the ~10 s + ~50 MB sentence-transformers load on every weekly run.

3. **Weekly hash-check is a tripwire.** The weekly health check re-computes
   the `.obsidian/plugins/` directory hash and compares against the baseline
   at `99 Workspace/_plugin_hash_baseline.txt`. The directory-hash algorithm,
   run from `.obsidian/`, is:
   ```
   find plugins -type f -exec sha256sum {} \; | sort -k2 | sha256sum
   ```
   Any drift not preceded by a logged manual update triggers
   `99 Workspace/_audit_YYYY-MM-DD_plugin_drift.md` and surfaces on next
   session start. Drift automatically chains into rule 2's smoke-test gate.

## Project-specific values to fill

```
Plugin whitelist:    [PROJECT_PLUGIN_WHITELIST]   # e.g. ["smart-connections"]
Pinned version:      [e.g. "smart-connections@4.5.0"]
Hash baseline file:  99 Workspace/_plugin_hash_baseline.txt
Current baseline:    [SHA-256 of .obsidian/plugins/ at scaffold time — compute at first use]
```

## Auto-update posture

Obsidian does NOT auto-update community plugins by default — confirmed via
Obsidian Forum thread 78071. The "auto-updates disabled" requirement is
satisfied by Obsidian's native behaviour, not by an explicit setting.

## License consideration

Any community plugin's license should be reviewed at install time and at the
6-month substrate review (P-13 / EXT-13). Source-available with noncompete
clauses (like Smart Plugins License post-Dec-2025) are acceptable for end-user
use but require re-evaluation when building on top of the plugin.
