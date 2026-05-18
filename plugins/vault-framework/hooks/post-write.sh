#!/usr/bin/env bash
# post-write.sh — PostToolUse auto-commit hook for Obsidian vaults.
# Fires after Write, Edit, MultiEdit, Bash tool calls in Claude Code CLI.
#
# ⚠ NOT FIRED IN COWORK (issue #45514). This hook is designed exclusively
# for the Claude Code CLI. In Cowork sessions Claude must run `git commit`
# manually after each substantive change cluster.
#
# Commit message format:
#   [<zone>] <verb> <path> — <reason>
#
# When the chain log (_auto_writes.md) is the file being written, the last
# chain entry's verb/path/reason are extracted to compose the commit message
# for both the referenced file and the chain entry itself.
# For all other files: reason defaults to the basename.
#
# Prerequisites:
#   - jq   (brew install jq  /  apt install jq)
#   - git  (vault must be a git repo — run `git init` at vault root if needed)
#   - scripts/audit_chain.py reachable (see hooks/README.md)
#
# Skip rules:
#   - .smart-env/ (gitignored embedding cache)
#   - files outside the vault root
set -euo pipefail

VAULT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
CHAIN_LOG="$VAULT/99 Workspace/_auto_writes.md"

# Guard: require jq and git
command -v jq  >/dev/null 2>&1 || exit 0
command -v git >/dev/null 2>&1 || exit 0
[ -d "$VAULT/.git" ] || exit 0

INPUT=$(cat)
TOOL=$(echo "$INPUT"     | jq -r '.tool_name // ""')
FILEPATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""')

# Skip .smart-env/ writes (gitignored anyway)
[[ "$FILEPATH" == *".smart-env"* ]] && exit 0

# Resolve relative path within vault
REL=""
if [ -n "$FILEPATH" ]; then
  case "$FILEPATH" in
    "$VAULT"/*) REL="${FILEPATH#$VAULT/}" ;;
    /*)         exit 0 ;;                  # Different directory root — skip
    *)          REL="$FILEPATH" ;;
  esac
fi

# ── Bash path: stage all unstaged vault changes (no file_path in tool_input) ──
if [ "$TOOL" = "Bash" ] && [ -z "$REL" ]; then
  cd "$VAULT"
  # Stage everything except .smart-env/
  git add -A -- ':!.smart-env' 2>/dev/null || true
  git diff --cached --quiet 2>/dev/null && exit 0
  git commit -m "[vault] write (bash) — unstaged mutations from Bash tool" \
    --no-verify 2>/dev/null || true
  exit 0
fi

[ -z "$REL" ] && exit 0

# Derive zone (first path component) and verb
ZONE=$(printf '%s' "$REL" | cut -d'/' -f1)
VERB="write"
case "$TOOL" in Edit|MultiEdit) VERB="edit" ;; esac

# Stage the written file
cd "$VAULT"
git add -- "$REL" 2>/dev/null || true

# ── When chain log is written: extract last entry for full commit context ──
if [[ "$REL" == *"_auto_writes.md" ]]; then
  LAST=$(grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}' "$CHAIN_LOG" 2>/dev/null | tail -1 || true)
  if [ -n "$LAST" ]; then
    IFS='|' read -ra PARTS <<< "$LAST"
    C_VERB=$(printf '%s' "${PARTS[1]:-write}" | sed 's/^ *//;s/ *$//')
    C_PATH=$(printf '%s' "${PARTS[2]:-}"       | sed 's/^ *//;s/ *$//')
    C_REASON=$(printf '%s' "${PARTS[3]:-}"     | sed 's/^ *//;s/ *$//' \
                | sed 's/ | prev_hash:.*//' | cut -c1-80)
    C_ZONE=$(printf '%s' "$C_PATH" | cut -d'/' -f1)
    [ -z "$C_ZONE"   ] && C_ZONE="$ZONE"
    [ -z "$C_REASON" ] && C_REASON="chain append"
    # Also stage the referenced file (should already be staged from its own write)
    [ -n "$C_PATH" ] && git add -- "$C_PATH" 2>/dev/null || true
    MSG="[$C_ZONE] $C_VERB $C_PATH — $C_REASON"
  else
    MSG="[$ZONE] $VERB $REL — chain log updated"
  fi
else
  # All other files: reason = basename (chain entry will carry the full reason)
  MSG="[$ZONE] $VERB $REL — $(basename "$REL")"
fi

# Commit if anything is staged
git diff --cached --quiet 2>/dev/null && exit 0
git commit -m "$MSG" --no-verify 2>/dev/null || true

# ── FN-09 promotion hook ────────────────────────────────────────────────────
# After a successful commit, if the written file is a .md note that landed in
# a typed zone (10 People / 20 Companies / 30 Projects / 40 Meetings /
# 50 Sources / 60 Concepts / 70 Decisions / 90 System), append/replace its
# row in _index.md atomically. The append-mode is idempotent and refuses
# skipped subdirs so it is safe to call on every typed-zone write.
#
# Requires: python3 accessible; 90 System/_build_index.py present in vault.
# Skip: _index.md itself (would loop), non-.md artefacts.
case "$REL" in
  *.md)
    case "$ZONE" in
      "10 People"|"20 Companies"|"30 Projects"|"40 Meetings"|"50 Sources"|"60 Concepts"|"70 Decisions"|"90 System")
        case "$(basename "$REL")" in
          _index.md) ;;
          *)
            python3 "$VAULT/90 System/_build_index.py" \
              --root "$VAULT" \
              --append "$VAULT/$REL" >/dev/null 2>&1 || true
            # If _index.md was rewritten, commit it as a follow-on.
            git add -- "_index.md" 2>/dev/null || true
            if ! git diff --cached --quiet 2>/dev/null; then
              git commit -m "[vault] index _index.md — append row for $REL" \
                --no-verify 2>/dev/null || true
            fi
            ;;
        esac
        ;;
    esac
    ;;
esac

exit 0
