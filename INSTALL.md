# Installation Guide

---

## Prerequisites

| Requirement | Path A | Path B | Path C |
|---|---|---|---|
| [Obsidian](https://obsidian.md) (desktop) | Required | Installed by `bootstrap.sh` | Required |
| [Cowork](https://claude.ai) (Claude for Desktop, Cowork mode) | Required | Required | Required |
| Python 3.9+ | Required (eval + ingestion scripts) | Required | Required |
| Git | Optional | Required | Optional |

---

## Path A — Existing Obsidian + existing project folder

This is the main path. Takes about 10 minutes.

### 1. Open Cowork on your project folder

In Claude for Desktop, open Cowork and select your project folder (the folder you want to use as your vault root). This mounts the folder for Claude.

### 2. Add the marketplace

```
/plugin marketplace add https://github.com/<owner>/claude-obsidian-vault
```

### 3. Install the framework plugin

```
/plugin install vault-framework@claude-obsidian-vault
```

Install additional plugins as needed:

```
/plugin install vault-skills@claude-obsidian-vault
/plugin install vault-eval@claude-obsidian-vault
/plugin install vault-ingestion@claude-obsidian-vault
/plugin install vault-voice@claude-obsidian-vault
```

Or install everything at once:

```
/plugin install @claude-obsidian-vault
```

### 4. Install Smart Connections in Obsidian

Smart Connections is the semantic retrieval substrate. Without it, Step 1 of the retrieval cascade is unavailable (the system falls back to lexical + Bases).

1. Open Obsidian → Settings → Community plugins → Browse
2. Search "Smart Connections"
3. Install and Enable
4. In Smart Connections settings: click **Rebuild index** and wait for it to complete

### 5. Enable Bases in Obsidian

Bases is a core Obsidian plugin (no external install needed):

1. Open Obsidian → Settings → Core plugins
2. Find "Bases" and enable it

### 6. Run vault setup

```
/vault-setup
```

Claude will ask you three questions:

1. **Substrate**: `FLAT` (plain markdown, no Obsidian dependency) or `OBSIDIAN` (uses Bases, Smart Connections MCP)?
2. **Vault state**: New vault (scaffold from scratch) or existing folder (Claude inspects what's there and adapts)?
3. **Primary language**: Your main working language (affects M9 multilingual fall-through in the retrieval cascade)

Answer these and Claude scaffolds the full directory structure, populates `CLAUDE.md` from the template, writes the 11 rules files to `.claude/rules/`, and creates the 12 Bases templates.

### 7. Verify the baseline

```bash
python3 plugins/vault-framework/scripts/verify_baseline.py --vault <absolute-path-to-your-vault>
```

Exit 0 = baseline is good. Exit 1 = something is missing — the output tells you what.

What `verify_baseline.py` checks:
- All 8 Bases exist and are syntactically valid
- All 11 rules files are in `.claude/rules/`
- `CLAUDE.md` is present and has the required frontmatter keys
- Operating guide is present with all 9 P-rules
- `99 Workspace/` directory exists
- `_auto_writes.md` is present (even if empty)

---

## Path B — No Obsidian yet

### 1. Clone and bootstrap

```bash
git clone https://github.com/<owner>/claude-obsidian-vault
cd claude-obsidian-vault
./scripts/bootstrap.sh
```

`bootstrap.sh` does the following:
- Checks for Homebrew (required; exits with instructions if missing)
- Checks if Obsidian is installed; installs via `brew install --cask obsidian` if not
- Opens Obsidian
- Opens `obsidian://show-plugin?id=smart-connections` in your browser — prompts you to install Smart Connections
- Opens `obsidian://show-plugin?id=bases` — prompts you to enable Bases
- Prints next-step instructions

For authenticated registry access (higher rate limits):

```bash
GITHUB_TOKEN=<your-token> ./scripts/bootstrap.sh
```

The `--dry-run` flag prints what the script would do without doing it:

```bash
./scripts/bootstrap.sh --dry-run
```

### 2. After Obsidian and plugins are ready

Follow Path A from step 1.

---

## Path C — Cross-project (framework already installed)

If you've already installed the framework for one project and want to use it with a new folder:

### 1. Open Cowork on the new project folder

Select the new folder in Cowork.

### 2. Run vault setup

```
/vault-setup
```

`/vault-setup` detects that the framework is already installed at user scope and skips the plugin install. It just scaffolds the new folder — same 3 questions as Path A step 6, same directory structure, but no repeat install.

No `/plugin install` step needed.

---

## Post-install verification

After any path, run:

```bash
python3 plugins/vault-framework/scripts/verify_baseline.py --vault <absolute-path>
```

Expected output on success:
```
[OK] CLAUDE.md present and valid
[OK] Operating guide present (9 P-rules)
[OK] 11 rules files in .claude/rules/
[OK] 12 Bases templates present
[OK] 99 Workspace/ exists
[OK] _auto_writes.md present
Baseline verified. Exit 0.
```

---

## Troubleshooting

**Smart Connections index not built yet**

Symptoms: Step 1 of the retrieval cascade returns no results; Claude falls through to Bases immediately.

Fix: Open Obsidian → Smart Connections settings → click **Rebuild index**. Wait for completion (progress shown in the status bar). May take 1-5 minutes for a large vault.

**Bases showing empty**

Symptoms: `/vault-setup` completed but Bases views show no notes.

Fix: Bases queries on frontmatter. Check that your notes have the expected frontmatter keys (e.g., `type: source`, `type: decision`). The note templates in `plugins/vault-framework/templates/` show the required frontmatter for each type.

**`verify_baseline.py` failing on Bases**

Symptoms: Exit 1 with `[FAIL] Bases: missing Companies.base`.

Fix: Check that `/vault-setup` completed without error. If it was interrupted, re-run `/vault-setup` — it is idempotent and will only write what's missing.

**`/vault-setup` can't find the framework**

Symptoms: `/vault-setup` says "command not found" or "plugin not installed".

Fix: Confirm the plugin install completed in step 3. Run `/plugin list` to see installed plugins. If `vault-framework` is missing, re-run `/plugin install vault-framework@claude-obsidian-vault`.

**`bootstrap.sh` fails: Homebrew not found**

Symptoms: Script exits with "Homebrew is required but not installed."

Fix: Install Homebrew first: `https://brew.sh`. Then re-run `bootstrap.sh`.
