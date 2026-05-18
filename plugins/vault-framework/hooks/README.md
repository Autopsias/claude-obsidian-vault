# vault-framework — hooks/

This directory contains Claude Code CLI hooks that pair every Claude file write
with a git commit and a hash-chain audit entry.

---

## post-write.sh

Fires after `Write`, `Edit`, `MultiEdit`, and `Bash` tool calls and immediately
commits the written file with a structured message:

```
[<zone>] <verb> <path> — <reason>
```

Full format documented in `rules/git-commit-discipline.md`.

### ⚠ Cowork caveat (issue #45514)

**This hook does NOT fire in Cowork mode.** Cowork uses a different tool
execution path that does not invoke `PostToolUse` hooks.

In Cowork sessions Claude must run `git commit` manually after each substantive
change cluster:

```bash
cd /path/to/vault
git add -A -- ':!.smart-env'
git diff --cached --quiet || git commit -m "[<zone>] <verb> <path> — <reason>"
```

The hash-chain audit log (`99 Workspace/_auto_writes.md`) is maintained
independently of git and works the same way in both environments.

### Dependencies

| Dependency | Required for | Install |
|---|---|---|
| `git` | All commits | `brew install git` / `apt install git` |
| `jq` | Parsing tool-input JSON from stdin | `brew install jq` / `apt install jq` |
| `python3` | FN-09 index append (optional) | System Python ≥ 3.9 |
| `scripts/audit_chain.py` | Hash-chain context in commit messages | Shipped in this repo |

The hook exits 0 silently if `jq` or `git` are not found, or if the vault
has no `.git` directory — it degrades gracefully rather than blocking writes.

### Install instructions

1. **Copy the hook** into your vault's Claude hooks directory:

   ```bash
   cp post-write.sh /path/to/your/vault/.claude/hooks/post-write.sh
   chmod +x /path/to/your/vault/.claude/hooks/post-write.sh
   ```

2. **Register the hook** in `.claude/settings.json`:

   ```json
   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Write|Edit|MultiEdit|Bash",
           "hooks": [
             {
               "type": "command",
               "command": "bash .claude/hooks/post-write.sh"
             }
           ]
         }
       ]
     }
   }
   ```

3. **Initialise git** at the vault root if you haven't already:

   ```bash
   cd /path/to/your/vault
   git init
   echo ".smart-env/" >> .gitignore
   echo ".obsidian/.audit_key" >> .gitignore   # private key — never commit
   git add -A
   git commit -m "[vault] init — initial vault commit"
   ```

4. **Verify** by writing a test file via Claude Code CLI and checking
   `git log --oneline -5` — you should see a structured commit message.

### FN-09 index promotion (optional)

If your vault uses `90 System/_build_index.py` (the Karpathy-pattern content
catalog), the hook automatically appends/updates the written note's row in
`_index.md` whenever a `.md` file lands in a typed zone
(`10 People/`, `20 Companies/`, `30 Projects/`, etc.).

This is a no-op if `_build_index.py` is absent — the hook catches the error
silently and continues.

---

## Cross-references

- `rules/git-commit-discipline.md` — commit message format, zone table, verb table
- `rules/auto-write-discipline.md` — hash-chain audit discipline (parallel authorship record)
- `scripts/audit_chain.py` — append/verify CLI for the hash-chain log
