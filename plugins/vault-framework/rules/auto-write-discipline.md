# Auto-write discipline

Per operating guide P-7. Inside `99 Workspace/` Claude writes without
per-file approval, **provided** every write is logged to
`99 Workspace/_auto_writes.md`. Outside requires explicit user trigger.

Same applies to `00 Inbox/` and `80 Daily/` — auto-write OK; logging required.

Format: `YYYY-MM-DD | verb | path | one-line reason`.
Verbs: write, edit, rename, note, delete. Append-only.

Before writing: confirm path is under `99 Workspace/` (or `00 Inbox/`,
`80 Daily/`); confirm frontmatter; populate `provenance:` if it's a debrief /
analysis / audit / battleplan.

After writing: append the line. If >5 files this session, propose
`kb-curator refresh-index`.

Reconciliation safety net: weekly vault-health check catches dropped
log entries.

Never auto-write: state MOC, CLAUDE.md, handoff
(only on explicit triggers), or anything outside the three auto-write zones.

## Audit-time size-breach surfacing

When any audit (write-audit, kb-audit, vault-health) runs against
`99 Workspace/_auto_writes.md`, the audit must check size at completion:

- `_auto_writes.md` >80 KB → recommend `kb-curator rotate-logs --root <vault>`
  in the same report. Do not wait for the quarterly log-rotation.
- `_cleanup_log.md` >200 KB → same recommendation.

## Bulk reconciliation pattern

When a write-audit reports **>20 unlogged files**, do NOT back-date
one entry per file (bloats the log). Instead append ONE summary line:

```
YYYY-MM-DD | note | 99 Workspace/_audit_writes_YYYY-MM-DD.md | bulk reconciliation: N unlogged files reconciled; see audit report for the full list
```

The audit report is the durable, complete record.

## OS-junk delete carve-out

OS junk files (`.~lock.*`, `~$*`, `.DS_Store`, `Thumbs.db`, `*.tmp`, `lu*.tmp`)
MAY be deleted without per-file authorisation when they block a clean audit
state, **provided** the deletion is logged with verb `delete`.

Real artefacts (`.md`, `.docx`, `.pptx`, `.xlsx`, `.pdf`, `.html`, `.skill`,
`.zip`, `.png`, `.jpg`) remain under "no deletes ever — moves only, after
approval". If ambiguous, ask.

If bash returns "Operation not permitted" on `rm`, call
`mcp__cowork__allow_cowork_file_delete` with the target path before retrying.

## Entry format — Karpathy grep-prefix header

New writes append via `scripts/audit_chain.py append` with the **`--grep-prefix`
flag**, which inserts a grep-friendly section header immediately before the
chain entry:

```
## [YYYY-MM-DD] verb | basename
YYYY-MM-DD HH:MM | verb | full/path/to/file | reason | prev_hash:... | sig:...
```

The `##` header line is skipped by the chain verifier (non-chain line). The
cryptographic hash covers only the signed entry — adding the prefix does not
invalidate prior entries.

**Why:** makes `_auto_writes.md` grep-scriptable without sacrificing the
cryptographic chain:
- `grep '## \[2026-05\]' _auto_writes.md` — all entries this month
- `grep '## .* write |' _auto_writes.md` — all write verbs across sessions
- `grep '## .* | _hot' _auto_writes.md` — all entries touching `_hot.*` files

**Standard append with prefix:**
```bash
python3 "plugins/vault-framework/scripts/audit_chain.py" \
  --vault /path/to/your/vault \
  append --verb <verb> --path "<path>" --reason "<one-line reason>" --grep-prefix
```

Use `--grep-prefix` for all new writes from the initial chain-script setup
onward.

## Entry format — hash-chained Ed25519-signed log

`_auto_writes.md` is a **hash-chained Ed25519-signed log**. All new entries
MUST be appended via the chain script, not manually:

```bash
python3 "plugins/vault-framework/scripts/audit_chain.py" \
  --vault /path/to/your/vault \
  append --verb <verb> --path "<path>" --reason "<one-line reason>"
```

Verbs: `write`, `edit`, `rename`, `note`, `delete`. See `audit_chain.py --help`.

Each entry carries `prev_hash:` (SHA-256 of the previous signed line) and
`sig:` (Ed25519 signature of the entry itself). The chain verifier confirms no
line has been silently removed or reordered.

**Fallback (chain script unavailable):** append a plain `YYYY-MM-DD | verb |
path | reason` line — the verifier treats unsigned lines as non-chain (they are
ignored by `verify-chain`), so the log remains readable. Back-fill with the
chain script at the next available opportunity and note the gap in the reason
field.

**Key files (created by `audit_chain.py keygen`):**
- Private key: `.obsidian/.audit_key` (0600 — add to `.gitignore`)
- Public key: `90 System/_audit_pubkey.txt`
- Script: `plugins/vault-framework/scripts/audit_chain.py`

The script reference (`scripts/audit_chain.py`) is shipped in S02 of the repo
sync plan. Until then, use the plain fallback format above.

## Hash chain + git coexistence

Every Claude file write produces **two parallel records**:

1. **Hash-chain entry** in `99 Workspace/_auto_writes.md`
   — *tamper-evident authorship record*. Ed25519-signed, prev_hash-linked.
   Proves *who* wrote the file and *why*, in an order that cannot be silently
   reordered or deleted.

2. **Git commit** (via a post-write hook or manual `git commit` after each
   substantive change cluster) — *reversible content record*. Threat addressed:
   a bad write corrupting a file beyond recovery; `git revert` or `git restore`
   as surgical rollback.

**Neither replaces the other.** They protect different things:

| Surface    | Proves          | Enables         | Threat addressed           |
|------------|-----------------|-----------------|----------------------------|
| Hash chain | Authorship, why | Integrity audit | Fabrication, back-dating   |
| Git commit | Content, what   | Surgical revert | Corruption, bad write      |

### Cross-verification snippet

The weekly vault-health task can compare counts as a consistency check:

```bash
# Count hash-chain entries for workspace writes
CHAIN=$(grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}' \
  "99 Workspace/_auto_writes.md" | wc -l)

# Count git commits touching 99 Workspace/
GIT=$(git log --oneline -- "99 Workspace/" | wc -l)

echo "Chain entries: $CHAIN | Git commits (99 Workspace): $GIT"
# Expect: CHAIN ≈ GIT (±5 to allow for bulk reconciliation commits)
```

A divergence >10 signals either the post-write hook was not firing, or chain
entries were added without corresponding git commits (or vice versa).

### Design notes

- In Cowork sessions, the post-write hook may not fire automatically. Run
  `git commit` manually after each substantive change cluster.
- `.smart-env/` writes should be gitignored and excluded from both records.
- Bulk reconciliation commits count as one chain entry but may correspond to
  multiple git commits — this is expected and does not invalidate the
  cross-verify check.
