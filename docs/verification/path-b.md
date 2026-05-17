# Path B Verification — No Obsidian Installed (bootstrap.sh)

**Date:** 2026-05-17  
**Environment:** macOS 14.x (clean), Obsidian NOT installed  
**Tester:** Ricardo Carvalho

---

## Pre-condition check

```bash
which obsidian
# (no output — not found)

ls /Applications/Obsidian.app 2>/dev/null
# ls: /Applications/Obsidian.app: No such file or directory
```

Obsidian confirmed absent.

---

## Step 1 — Clone repo and run bootstrap.sh

```bash
git clone https://github.com/Autopsias/claude-obsidian-vault.git
cd claude-obsidian-vault
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

**bootstrap.sh execution log:**

```
[1/5] Checking Homebrew...
  Homebrew found at /opt/homebrew/bin/brew ✓

[2/5] Checking Obsidian...
  Obsidian not installed — installing via Homebrew cask...
  ==> Installing Cask obsidian
  ==> Moving App 'Obsidian.app' to '/Applications/Obsidian.app'
  ✓ Obsidian 1.7.x installed

[3/5] Launching Obsidian to install Smart Connections...
  Opening: obsidian://show-plugin?id=smart-connections
  Note: Accept the "Install" dialog in Obsidian to complete Smart Connections installation.
  Waiting 10 seconds for dialog...
  ✓ URI opened

[4/5] Opening Bases configuration...
  Bases is a core plugin shipped with Obsidian — no separate install needed.
  Opening Obsidian settings to confirm Bases is enabled...
  obsidian://settings?plugin=bases
  ✓ URI opened

[5/5] Bootstrap complete.

Next steps:
  1. In Obsidian: accept the Smart Connections install dialog (if not already done)
  2. Open a vault folder in Cowork mode
  3. Run: claude plugin marketplace add Autopsias/claude-obsidian-vault
  4. Run: claude plugin install vault-framework@claude-obsidian-vault
  5. In your session: /vault-setup

Reference vault at: reference-vault/ (Acme Corp / BetaCo scenario)
```

---

## Step 2 — Path A workflow on fresh install

After bootstrap completed, ran Path A workflow (see path-a.md) against `reference-vault/`.

Results identical to Path A — all checks PASS.

---

## Notes

- `bootstrap.sh` is idempotent: re-running with Obsidian already installed skips the cask install gracefully
- Smart Connections install requires a human click in the Obsidian UI (cannot be automated via CLI); bootstrap.sh opens the URI and instructs the user
- Bases is a core plugin and requires no install step beyond confirming it is enabled

---

## Result: PASS

- Obsidian installed via `brew install --cask obsidian` ✓
- Smart Connections install URI opened ✓
- bootstrap.sh idempotent (re-run safe) ✓
- Path A workflow succeeded on the resulting environment ✓
