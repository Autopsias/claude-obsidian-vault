---
paths:
  - ".obsidian/**/*"
  - "90 System/_plugin_security.md"
---

# Plugin security discipline

**[PROJECT-SPECIFIC: Substitute your vault's plugin whitelist, hash baseline,
and pinned version. The three load-bearing rules below are universal kernel.]**

## Three load-bearing rules (universal kernel)

1. **No plugin install without explicit user trigger.** The community-plugins
   whitelist for this vault is `[PROJECT_PLUGIN_WHITELIST]`. Adding a new
   plugin requires (a) running a security audit on that plugin covering purpose,
   permissions, vendor, licence, last-update, and hash, (b) user decision to
   accept, (c) hash baseline refresh in `90 System/_plugin_security.md` and
   `99 Workspace/_plugin_hash_baseline.txt`. Obsidian CORE plugins (Bases,
   Templates, etc.) are exempt — their trust posture is the same as Obsidian.

2. **Plugin updates are gated by the M11 retrieval smoke-test.** Before any
   update: tarball the existing plugin directory. After any update: run
   `python3 90 System/_smoke_test_retrieval.py`. Pass → update accepted, log
   in `_plugin_security.md`. Fail → restore from tarball, log the failure.
   The smoke-test is the gate from "provisional" to "accepted".

3. **Weekly hash-check is a tripwire.** A scheduled health check computes the
   SHA-256 of `.obsidian/plugins/` and compares against the baseline at
   `99 Workspace/_plugin_hash_baseline.txt`. Any drift not preceded by a logged
   manual update triggers an audit file and surfaces on next session start.
   Drift automatically chains into rule 2's smoke-test gate.

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
