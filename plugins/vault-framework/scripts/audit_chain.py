#!/usr/bin/env python3
"""
audit_chain.py
==============
Hash-chained Ed25519-signed audit log for Obsidian vault _auto_writes.md.

Motivation: engineering hygiene — forensic trust + optionality if the vault is later
embedded in a regulated workflow.

DESIGN
------
Every chain entry appended to the log is a single line of the form:

  YYYY-MM-DD HH:MM | verb | path | reason | prev_hash:<sha256-hex> | sig:<base64url-ed25519>

where:
  - prev_hash  = sha256(full text of the immediately preceding chain entry)
  - First entry uses prev_hash = 64 × '0' (null sentinel)
  - sig         = Ed25519 signature over the entry text WITHOUT the "| sig:…" suffix
                  (i.e. the "pre-sig payload" is everything up to and including prev_hash)

This makes each entry:
  - Independently verifiable (signature covers content + its link to the prior entry)
  - Chain-bound (prev_hash detects insertion, deletion, or reordering)

NON-CHAIN LINES in the log (frontmatter, blank lines, headers starting with '#' or '##')
are preserved verbatim and are NOT included in the chain. Only lines that begin with a
date pattern (YYYY-MM-DD) — legacy pipe entries — OR a '{' — JSONL entries — are chain
entries.

JSONL TRANSITION (2026-05-23)
-----------------------------
The legacy pipe format ``ts | verb | path | reason | prev_hash:… | sig:…`` corrupts any
pipe ('|') inside verb/path/reason (a filename like "Kick off | Project.m4a" was silently
rewritten with '-'). NEW appends are therefore emitted as one JSON object per line:

  {"format":"audit-chain-jsonl-v1","path":…,"prev_hash":…,"reason":…,"sig":…,"ts":…,"verb":…}

  - ALL fields are STRINGS — no numeric fields — sidestepping the IEEE-754
    reproducibility trap (RFC 8785 §3.2.2.3). Keys are ASCII, so codepoint-vs-UTF-16
    key ordering is moot.
  - reason/path/verb carry pipes (and any other character) VERBATIM.
  - sig = Ed25519 over ``_canonical_payload(obj_without_sig)`` where the single helper
    ``_canonical_payload`` = ``json.dumps(obj, sort_keys=True, separators=(",",":"),
    ensure_ascii=False)`` — used by BOTH append and verify.
  - DOMAIN SEPARATION: the signed payload includes a literal
    ``"format":"audit-chain-jsonl-v1"`` field so one Ed25519 key signing two
    serialization schemes cannot be cross-format replayed.
  - BYTE-AUTHENTICATION (fail-closed): verify reconstructs the full canonical line
    ``_canonical_payload(obj_with_sig)`` and asserts it byte-equals the stored line.
    This protects even the LAST entry's raw bytes (no successor hashes them), so
    re-ordered keys / extra whitespace / alternate escapes are rejected as tamper.
  - FAIL-HARD on malformed brace lines: a line that lstrip-starts with '{' MUST be
    valid JSONL (parses, exactly the 7 required keys, correct format, all-string
    values) — any failure is a hard verify error, NEVER a fallback to the pipe parser.

NO BULK MIGRATION: existing pipe entries are left untouched and remain verifiable. Only
*new* appends are JSONL. The reader is dual-format.

prev_hash BYTE-RULE (compatibility boundary — match legacy EXACTLY)
------------------------------------------------------------------
The chain links by ``prev_hash = sha256(previous chain entry's STRIPPED raw line)``,
regardless of that line's format. Legacy code is authoritative here:
``_last_chain_entry_line`` returns ``line.strip()`` and the verify walk advances with
``_sha256(stripped_line)``. So a JSONL append computes its boundary ``prev_hash`` as
``sha256(<previous pipe line>.strip())`` and the JSONL line's OWN successor (if any)
hashes ``sha256(<that JSONL line>.strip())``. Stripped, full signed line INCLUDING the
trailing ``| sig:`` (pipe) or ``"sig":`` (JSONL) field.

OPERATIONAL RECOVERY (first JSONL append)
-----------------------------------------
``cmd_append`` automatically, on the FIRST JSONL append (no JSONL line yet in the log):
(1) verifies the existing chain and ABORTS if it does not already verify — so a later
red verify is attributable to the boundary, not pre-existing tamper; (2) writes a
timestamped ``_auto_writes.md.pre-jsonl-backup-<UTCstamp>`` snapshot. Runbook: if verify
goes red right after the refactor, diff against that backup and inspect the boundary
entry's prev_hash (= sha256 of the prior STRIPPED pipe line) before assuming tamper.

KEY FILES
---------
  Private key : <vault>/.obsidian/.audit_key     (PEM, chmod 0600)
  Public  key : <vault>/90 System/_audit_pubkey.txt (PEM)

  Note: vault is not a git repo yet. The private key location (.obsidian/) is a
  forward-compat assertion — .obsidian/ will be in .gitignore when git-init lands.
  For now, file-permission 0600 is the protection mechanism.

KEY ROTATION
------------
  1. Run: python3 audit_chain.py keygen --vault /path/to/vault --rotate
     Generates a new keypair. Old public key is archived in _audit_pubkey_archive/
     with a date suffix. New keys written to the standard paths.
  2. Rotation does NOT re-sign old entries. Old entries remain verifiable with the
     archived public key. New entries use the new key.
  3. Document in 90 System/_audit_chain_keylog.md (auto-created by keygen).
  4. Re-run: python3 audit_chain.py verify --vault /path/to/vault   — should show split-key report.

  SINGLE-KEY ASSUMPTION [HARDENED:claude]: `cmd_verify` loads ONLY the current public
  key (`_audit_pubkey.txt`). The "split-key report" above is aspirational. This JSONL
  refactor assumes NO key rotation across the pipe->JSONL boundary; split-key
  verification (loading archived keys for pre-rotation entries) is a separate,
  pre-existing limitation and is OUT OF SCOPE here. A rotation-induced verify failure
  must therefore NOT be misattributed to the format change.

USAGE
-----
  # --vault is REQUIRED for all subcommands (no hard-coded default).
  # Set VAULT=/path/to/your/vault for convenience.

  # Generate keypair (first-time setup or rotation):
  python3 audit_chain.py keygen --vault /path/to/vault

  # Migrate existing pre-chain entries (one-time, run after keygen):
  python3 audit_chain.py migrate --vault /path/to/vault

  # Append a new entry:
  python3 audit_chain.py append --vault /path/to/vault \
      --verb write --path "99 Workspace/foo.md" --reason "added x"

  # Append with Karpathy grep-prefix header:
  python3 audit_chain.py append --vault /path/to/vault \
      --verb write --path "99 Workspace/foo.md" --reason "added x" --grep-prefix
  # → writes:  ## [2026-05-17] write | foo.md
  #             2026-05-17 HH:MM | write | 99 Workspace/foo.md | added x | prev_hash:… | sig:…
  # grep '## \[2026' _auto_writes.md   — lists all entries this year
  # grep '## .* write |' _auto_writes.md — lists all write verbs

  # Verify the full chain:
  python3 audit_chain.py verify --vault /path/to/vault

  # Verify and emit a machine-readable JSON exit-code report (for weekly task):
  python3 audit_chain.py verify --vault /path/to/vault --json

Exit codes:
  0  — success (append OK, or chain fully valid)
  1  — chain integrity failure (tamper detected or key mismatch)
  2  — setup error (key missing, log missing, bad args, --vault not provided)
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Crypto helpers (requires: pip install cryptography)
# ---------------------------------------------------------------------------

def _require_cryptography() -> None:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: F401
            Ed25519PrivateKey, Ed25519PublicKey,
        )
    except ImportError:
        _die("'cryptography' package not found. Install with: pip install cryptography", 2)


def _load_private_key(key_path: Path):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    if not key_path.exists():
        _die(f"Private key not found: {key_path}\nRun: python3 audit_chain.py keygen", 2)
    data = key_path.read_bytes()
    return load_pem_private_key(data, password=None)


def _load_public_key(pub_path: Path):
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    if not pub_path.exists():
        _die(f"Public key not found: {pub_path}", 2)
    data = pub_path.read_bytes()
    return load_pem_public_key(data)


def _sign(payload: str, private_key) -> str:
    """Return base64url-encoded Ed25519 signature over UTF-8 payload."""
    raw_sig = private_key.sign(payload.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_sig).decode("ascii")


def _verify_sig(payload: str, sig_b64: str, public_key) -> bool:
    from cryptography.exceptions import InvalidSignature
    try:
        raw_sig = base64.urlsafe_b64decode(sig_b64 + "==")
        public_key.verify(raw_sig, payload.encode("utf-8"))
        return True
    except (InvalidSignature, Exception):
        return False


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


NULL_PREV_HASH = "0" * 64  # sentinel for first entry

# ---------------------------------------------------------------------------
# JSONL format (new appends) — dual-format reader, JSONL writer
# ---------------------------------------------------------------------------

JSONL_FORMAT = "audit-chain-jsonl-v1"
# Exactly these keys, no more, no fewer. `sig` is excluded from the signed payload.
_REQUIRED_JSONL_KEYS = frozenset({"format", "ts", "verb", "path", "reason", "prev_hash", "sig"})


def _canonical_payload(obj: dict) -> str:
    """Deterministic JSON serialization used for BOTH signing and byte-auth.

    sort_keys + compact separators; ensure_ascii=False. Keys are ASCII (so the
    codepoint-vs-UTF-16 key-ordering question is moot) and ALL values are strings
    (so the IEEE-754 number-reproducibility trap does not apply). The SAME helper
    is used by cmd_append (to emit) and cmd_verify (to re-derive), so the two can
    never silently disagree on the canonical bytes.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _looks_like_jsonl(line: str) -> bool:
    """A line is a JSONL chain-entry candidate iff it lstrip-starts with '{'.

    Legacy pipe lines start with a date (YYYY-MM-DD); the two are unambiguous.
    """
    return line.lstrip().startswith("{")


def _validate_jsonl_line(line: str) -> tuple[Optional[dict], Optional[str]]:
    """Strict JSONL validation. Returns (obj, None) on success or (None, error).

    [HARDENED:codex] A brace-prefixed line MUST satisfy this — there is NO legacy
    fallback for a malformed brace line; the caller treats any error as a hard
    integrity failure.
    """
    s = line.strip()
    try:
        obj = json.loads(s)
    except (json.JSONDecodeError, ValueError):
        return None, "jsonl_parse_failure"
    if not isinstance(obj, dict):
        return None, "jsonl_not_object"
    if set(obj.keys()) != set(_REQUIRED_JSONL_KEYS):
        return None, f"jsonl_unexpected_keys:{sorted(set(obj.keys()) ^ set(_REQUIRED_JSONL_KEYS))}"
    if obj.get("format") != JSONL_FORMAT:
        return None, f"jsonl_bad_format:{obj.get('format')!r}"
    if not all(isinstance(v, str) for v in obj.values()):
        return None, "jsonl_nonstring_value"
    return obj, None

# ---------------------------------------------------------------------------
# Log file helpers
# ---------------------------------------------------------------------------

LOG_REL        = Path("99 Workspace/_auto_writes.md")
PRIVKEY_REL    = Path(".obsidian/.audit_key")
PUBKEY_REL     = Path("90 System/_audit_pubkey.txt")
PUBKEY_ARCH    = Path("90 System/_audit_pubkey_archive")
KEYLOG_REL     = Path("90 System/_audit_chain_keylog.md")

CHAIN_ENTRY_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})"           # date (required)
    r"(?:\s+(\d{2}:\d{2}))?"           # optional HH:MM
    r"\s*\|"                            # first pipe
)


def _is_chain_entry(line: str) -> bool:
    return bool(CHAIN_ENTRY_RE.match(line.strip()))


def _is_signed_entry(line: str) -> bool:
    """A chain entry that already carries prev_hash and sig fields."""
    return _is_chain_entry(line) and "| prev_hash:" in line and "| sig:" in line


def _parse_entry(line: str) -> Optional[dict]:
    """Parse a signed chain entry into its components. Returns None on failure."""
    line = line.strip()
    if not _is_signed_entry(line):
        return None
    # Split off trailing sig field
    sig_marker = "| sig:"
    sig_pos = line.rfind(sig_marker)
    if sig_pos == -1:
        return None
    pre_sig = line[:sig_pos].rstrip()
    sig_val = line[sig_pos + len(sig_marker):].strip()

    # Split off prev_hash
    ph_marker = "| prev_hash:"
    ph_pos = pre_sig.rfind(ph_marker)
    if ph_pos == -1:
        return None
    before_hash = pre_sig[:ph_pos].rstrip()
    prev_hash_val = pre_sig[ph_pos + len(ph_marker):].strip()

    return {
        "line":       line,
        "pre_sig":    pre_sig,
        "before_hash": before_hash,
        "prev_hash":  prev_hash_val,
        "sig":        sig_val,
    }


def _read_log(log_path: Path) -> list[str]:
    if not log_path.exists():
        _die(f"Log file not found: {log_path}", 2)
    return log_path.read_text(encoding="utf-8").splitlines()


_CHAIN_ANCHOR_HEX_RE = re.compile(r"^chain_anchor:\s*([0-9a-fA-F]{64})\s*$")


def _read_chain_anchor(lines: list[str]) -> Optional[str]:
    """Read the ``chain_anchor: <64-hex>`` field from the file's leading YAML
    frontmatter, if present. Returns None when no frontmatter or no anchor.

    Rotation-aware verify (kb-curator OBSIDIAN rotate-logs, 2026-05-28):
    after the log is split, the live log's first chain entry's prev_hash points
    to the last entry now in the archive — it is NOT NULL_PREV_HASH. The
    frontmatter records that boundary hex; verify uses it as the initial
    prev_hash for the walk. A non-rotated log has no anchor and verify keeps
    its historical behaviour (initial prev_hash = NULL_PREV_HASH).
    """
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        m = _CHAIN_ANCHOR_HEX_RE.match(line.strip())
        if m:
            return m.group(1).lower()
    return None


def _last_chain_entry_line(log_lines: list[str]) -> Optional[str]:
    """Return the STRIPPED text of the last chain entry (for computing prev_hash).

    Dual-format: a chain entry is a signed pipe line OR a JSONL (brace) line. The
    boundary prev_hash is sha256 of this stripped line regardless of its format.
    """
    for line in reversed(log_lines):
        s = line.strip()
        if _is_signed_entry(s) or _looks_like_jsonl(s):
            return s
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_keygen(vault: Path, rotate: bool) -> None:
    """Generate (or rotate) Ed25519 keypair."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PrivateFormat, PublicFormat, NoEncryption,
    )
    _require_cryptography()

    priv_path = vault / PRIVKEY_REL
    pub_path  = vault / PUBKEY_REL
    arch_dir  = vault / PUBKEY_ARCH
    keylog    = vault / KEYLOG_REL
    now_iso   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Rotation guard
    if priv_path.exists() and not rotate:
        print(f"Private key already exists at {priv_path}.")
        print("To rotate, re-run with --rotate flag.")
        sys.exit(0)

    if priv_path.exists() and rotate:
        # Archive old public key
        arch_dir.mkdir(parents=True, exist_ok=True)
        old_pub_archive = arch_dir / f"_audit_pubkey_{now_iso}_pre_rotation.txt"
        shutil.copy2(pub_path, old_pub_archive)
        print(f"Archived old public key to {old_pub_archive}")

    # Generate new keypair
    private_key = Ed25519PrivateKey.generate()
    public_key  = private_key.public_key()

    priv_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    pub_pem  = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

    # Write private key with 0600 permissions
    priv_path.parent.mkdir(parents=True, exist_ok=True)
    priv_path.write_bytes(priv_pem)
    os.chmod(priv_path, 0o600)

    # Write public key
    pub_path.parent.mkdir(parents=True, exist_ok=True)
    pub_path.write_bytes(pub_pem)

    # Append to key rotation log
    action = "ROTATION" if rotate else "INITIAL_KEYGEN"
    log_entry = (
        f"\n## {now_iso} — {action}\n\n"
        f"- Private key: `{PRIVKEY_REL}` (chmod 0600; forward-compat gitignored when git-init lands)\n"
        f"- Public  key: `{PUBKEY_REL}`\n"
    )
    if rotate:
        log_entry += f"- Archived old pub key: `{PUBKEY_ARCH}/_audit_pubkey_{now_iso}_pre_rotation.txt`\n"
    log_entry += (
        f"- Old entries remain verifiable with the archived key.\n"
        f"- New entries use the new key from this date.\n"
    )
    if keylog.exists():
        with keylog.open("a", encoding="utf-8") as f:
            f.write(log_entry)
    else:
        keylog.write_text(
            "---\n"
            "name: Audit chain key log\n"
            "description: Records Ed25519 keypair generation and rotation events for the audit chain.\n"
            "type: system\n"
            "---\n\n"
            "# audit_chain.py — Key rotation log\n\n"
            "All keygen / rotation events are appended below.\n"
            + log_entry,
            encoding="utf-8",
        )

    print(f"Keys written:")
    print(f"  Private key: {priv_path} (0600)")
    print(f"  Public  key: {pub_path}")
    print(f"  Key log    : {keylog}")
    print()
    print("Next step: run `python3 audit_chain.py migrate` to genesis-sign existing log entries.")


def cmd_migrate(vault: Path) -> None:
    """
    Genesis-sign existing pre-chain _auto_writes.md entries en bloc.
    Inserts a genesis chain entry that commits to the sha256 of all
    pre-chain lines, then overwrites the log. Idempotent: aborts if
    a genesis entry already exists.
    """
    _require_cryptography()
    log_path = vault / LOG_REL
    priv_path = vault / PRIVKEY_REL

    lines = _read_log(log_path)

    # Idempotency: abort if any signed entry is already present
    if any(_is_signed_entry(l) for l in lines):
        print("Chain entries already present — migration already run. Aborting.")
        sys.exit(0)

    private_key = _load_private_key(priv_path)
    now_iso   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_hhmm  = datetime.now(timezone.utc).strftime("%H:%M")

    # Collect all existing chain-candidate lines (date-prefixed log entries)
    legacy_entries = [l for l in lines if _is_chain_entry(l.strip())]
    legacy_count   = len(legacy_entries)
    legacy_blob    = "\n".join(l.strip() for l in legacy_entries)
    legacy_hash    = _sha256(legacy_blob) if legacy_blob else _sha256("")

    # Build genesis entry
    genesis_reason = (
        f"Imported from pre-chain era — {legacy_count} legacy entries "
        f"signed as a single block | legacy_hash:{legacy_hash}"
    )
    pre_sig = (
        f"{now_iso} {now_hhmm} | genesis | 99 Workspace/_auto_writes.md | "
        f"{genesis_reason} | prev_hash:{NULL_PREV_HASH}"
    )
    sig = _sign(pre_sig, private_key)
    genesis_line = f"{pre_sig} | sig:{sig}"

    # Insert migration header + genesis entry just before the first chain candidate
    # (after ## Entries section header or at end of file)
    migration_header = (
        f"\n## Imported from pre-chain era — entries below signed as a "
        f"single block on {now_iso}.\n"
        f"## Use `python3 90\\ System/audit_chain.py verify` to validate the chain.\n"
    )

    # Find insertion point: after "## Entries" section header, or append
    insert_idx = len(lines)  # default: end of file
    for i, line in enumerate(lines):
        if line.strip().startswith("## Entries"):
            insert_idx = i + 1
            break

    # Build new file content
    new_lines = (
        lines[:insert_idx]
        + [migration_header, genesis_line]
        + lines[insert_idx:]
    )
    new_text = "\n".join(new_lines)
    if not new_text.endswith("\n"):
        new_text += "\n"

    # Update frontmatter last_updated
    new_text = re.sub(r"(last_updated:\s*)\S+", f"\\g<1>{now_iso}", new_text, count=1)

    log_path.write_text(new_text, encoding="utf-8")

    print(f"Migration complete.")
    print(f"  Legacy entries genesis-signed: {legacy_count}")
    print(f"  Legacy hash (sha256): {legacy_hash[:16]}…")
    print(f"  Genesis entry inserted at line {insert_idx + 2}")
    print()
    print("Run `python3 audit_chain.py verify` to confirm the chain is valid.")


def cmd_append(vault: Path, verb: str, path_arg: str, reason: str,
               timestamp: Optional[str] = None,
               grep_prefix: bool = False) -> None:
    """Append a new signed chain entry to the log.

    If grep_prefix is True, a Karpathy-pattern grep-friendly section header
    is written immediately before the chain entry:

        ## [YYYY-MM-DD] verb | basename

    The header line is NOT part of the chain (it starts with '#', so
    _is_chain_entry() returns False and the verifier skips it). The hash
    chain covers only the signed entry line — adding the prefix to existing
    logs is safe and does not invalidate prior entries.

    This makes _auto_writes.md easily scriptable:
        grep '## \[2026-05' _auto_writes.md          # all entries this month
        grep '## .* write |' _auto_writes.md          # all write verbs
        grep '## .* | _hot' _auto_writes.md           # all entries for _hot.*
    """
    _require_cryptography()
    log_path  = vault / LOG_REL
    priv_path = vault / PRIVKEY_REL

    private_key = _load_private_key(priv_path)
    lines       = _read_log(log_path)
    now         = datetime.now(timezone.utc)
    ts          = timestamp or now.strftime("%Y-%m-%d %H:%M")

    # [HARDENED:claude] First-JSONL-append safeguard: verify the existing chain
    # and snapshot the log BEFORE introducing the pipe->JSONL boundary.
    _safeguard_first_jsonl_append(vault, log_path, lines)

    # Compute prev_hash from the last chain entry (pipe OR jsonl), per the
    # byte-rule: sha256(previous STRIPPED raw line).
    last_entry = _last_chain_entry_line(lines)
    if last_entry is None:
        # No chain entry yet — use null sentinel (would happen if migrate not run)
        prev_hash = NULL_PREV_HASH
    else:
        prev_hash = _sha256(last_entry)

    # JSONL writer — pipes (and every other character) carried VERBATIM. The
    # legacy `.replace("|", "-")` corruption is GONE.
    verb     = verb.strip()
    path_out = path_arg.strip()
    reason   = reason.strip()

    # Domain-separated signed payload (includes the literal format field). sig is
    # Ed25519 over the canonical serialization of this object WITHOUT sig.
    payload = {
        "format":    JSONL_FORMAT,
        "ts":        ts,
        "verb":      verb,
        "path":      path_out,
        "reason":    reason,
        "prev_hash": prev_hash,
    }
    sig  = _sign(_canonical_payload(payload), private_key)
    # The persisted line is EXACTLY the canonical form including sig, so the
    # verifier's byte-authentication re-derives identical bytes.
    full = _canonical_payload({**payload, "sig": sig})

    # Build grep-prefix header (KA-03, Frontier Closeout S05, 2026-05-17)
    # Format:  ## [YYYY-MM-DD] verb | basename. The header is NOT part of the
    # chain (starts with '#'), so its content does not affect integrity.
    if grep_prefix:
        date_part = ts[:10]  # YYYY-MM-DD portion of the timestamp
        basename  = path_out.split("/")[-1] if "/" in path_out else path_out.split("\\")[-1]
        prefix_line = f"## [{date_part}] {verb} | {basename}\n"
    else:
        prefix_line = ""

    # Append to file
    with (vault / LOG_REL).open("a", encoding="utf-8") as f:
        if prefix_line:
            f.write(prefix_line)
        f.write(full + "\n")

    print(f"Appended (jsonl): {ts} | {verb} | {path_out}")


def _verify_chain(lines: list[str], public_key, initial_prev_hash: Optional[str] = None) -> tuple[str, list[dict], int]:
    """Walk the dual-format chain. Pure: no printing, no sys.exit.

    Returns (status, errors, entries_checked). Shared by cmd_verify and the
    first-JSONL-append safeguard so the two can never diverge.

    ``initial_prev_hash``: rotation-aware seed for the walk. If omitted (or
    None), the walk starts at NULL_PREV_HASH — the historical behaviour and the
    correct seed for a never-rotated log. Callers that have just rotated the log
    pass the sha256 of the last entry now in the archive (the ``chain_anchor``
    recorded in the live log's frontmatter); the walk then begins at that
    boundary and the first kept entry's stored prev_hash matches it.

    Per-line dispatch:
      - lstrip-starts with '{'  -> JSONL entry. MUST validate (fail-hard); then
        byte-authenticate (canonical re-serialization incl. sig must equal the
        stored line), prev_hash-check, and signature-check over the canonical
        payload WITHOUT sig (domain-separated by the literal format field).
      - signed pipe entry        -> legacy verification (sig over pre_sig).
      - anything else            -> non-chain line, skipped (NOT hashed).
    prev_hash advances as sha256(STRIPPED line) for both formats — the byte-rule.
    """
    errors: list[dict] = []
    prev_hash = (initial_prev_hash or NULL_PREV_HASH).lower()  # expected prev_hash for the first chain entry; seeded from chain_anchor on rotated logs
    checked = 0

    for raw_line in lines:
        s = raw_line.strip()
        if not s:
            continue

        if _looks_like_jsonl(s):
            idx = checked
            checked += 1
            obj, err = _validate_jsonl_line(s)
            if err is not None:
                # [HARDENED:codex] fail-hard — never fall back to the pipe parser.
                errors.append({"entry_idx": idx, "error": err, "line": s[:120]})
                prev_hash = _sha256(s)
                continue
            # Byte-authenticate: the canonical re-serialization INCLUDING sig must
            # byte-equal the stored line. Protects the last entry's raw bytes.
            if _canonical_payload(obj) != s:
                errors.append({"entry_idx": idx, "error": "jsonl_not_canonical", "line": s[:120]})
            if obj["prev_hash"] != prev_hash:
                errors.append({
                    "entry_idx": idx,
                    "error": "prev_hash_mismatch",
                    "expected": prev_hash[:16] + "…",
                    "got":      obj["prev_hash"][:16] + "…",
                })
            signed = {k: v for k, v in obj.items() if k != "sig"}
            if not _verify_sig(_canonical_payload(signed), obj["sig"], public_key):
                errors.append({"entry_idx": idx, "error": "invalid_signature", "line": s[:120]})
            prev_hash = _sha256(s)

        elif _is_signed_entry(s):
            idx = checked
            checked += 1
            parsed = _parse_entry(s)
            if parsed is None:
                errors.append({"entry_idx": idx, "error": "parse_failure", "line": s[:120]})
                prev_hash = _sha256(s)
                continue
            if parsed["prev_hash"] != prev_hash:
                errors.append({
                    "entry_idx": idx,
                    "error": "prev_hash_mismatch",
                    "expected": prev_hash[:16] + "…",
                    "got":      parsed["prev_hash"][:16] + "…",
                })
            if not _verify_sig(parsed["pre_sig"], parsed["sig"], public_key):
                errors.append({"entry_idx": idx, "error": "invalid_signature", "line": s[:120]})
            prev_hash = _sha256(s)

        # else: non-chain line (frontmatter, '#'/'##' header, prose, blank) — skip.

    status = "ok" if not errors else "tampered"
    return status, errors, checked


def _safeguard_first_jsonl_append(vault: Path, log_path: Path, lines: list[str]) -> None:
    """[HARDENED:claude] Operational recovery for the FIRST JSONL append.

    Only fires when no JSONL entry exists yet. Verifies the existing chain and
    ABORTS if it does not already verify (so a later red verify is attributable
    to the boundary, not pre-existing tamper), then snapshots the log to a
    timestamped backup before the boundary entry is written.
    """
    if any(_looks_like_jsonl(line) for line in lines):
        return  # JSONL already present — not the first append.

    public_key = _load_public_key(vault / PUBKEY_REL)
    anchor = _read_chain_anchor(lines)  # rotation-aware seed (None on a never-rotated log)
    status, errors, checked = _verify_chain(lines, public_key, initial_prev_hash=anchor)
    if status != "ok":
        _die(
            "Refusing the FIRST JSONL append: the existing chain does not verify "
            f"(status={status}, {len(errors)} error(s)). Resolve the integrity failure "
            "before introducing the pipe->JSONL boundary, so a later verify failure is "
            "not misattributed to the format change.",
            1,
        )

    stamp  = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = log_path.with_name(log_path.name + f".pre-jsonl-backup-{stamp}")
    shutil.copy2(log_path, backup)
    print(f"[first-jsonl-append] existing chain verified OK ({checked} entries).")
    print(f"[first-jsonl-append] backup written: {backup}")
    print(
        "[runbook] If `verify` goes red right after this refactor, diff against the "
        "backup above and inspect the boundary entry's prev_hash (= sha256 of the prior "
        "STRIPPED pipe line) before assuming tamper."
    )


def cmd_verify(vault: Path, emit_json: bool = False) -> int:
    """
    Walk the dual-format chain (legacy pipe + JSONL) and verify every entry.
    Returns 0 if fully valid, 1 if any integrity failure, 2 if no entries.
    """
    _require_cryptography()
    log_path  = vault / LOG_REL
    pub_path  = vault / PUBKEY_REL

    public_key = _load_public_key(pub_path)
    lines      = _read_log(log_path)
    anchor     = _read_chain_anchor(lines)  # rotation-aware seed (None on a never-rotated log)

    status, errors, checked = _verify_chain(lines, public_key, initial_prev_hash=anchor)

    if checked == 0:
        msg = "No signed chain entries found. Run migrate first."
        if emit_json:
            print(json.dumps({"status": "error", "message": msg, "entries": 0}))
        else:
            print(msg)
        return 2

    result = {
        "status":          status,
        "entries_checked": checked,
        "errors":          errors,
    }

    if emit_json:
        print(json.dumps(result, indent=2))
    else:
        if status == "ok":
            print(f"Chain OK — {checked} entries verified, 0 errors.")
        else:
            print(f"CHAIN INTEGRITY FAILURE — {len(errors)} error(s) in {checked} entries:")
            for e in errors:
                print(f"  entry[{e['entry_idx']}]: {e['error']}")
                if "expected" in e:
                    print(f"    expected prev_hash: {e['expected']}")
                    print(f"    got      prev_hash: {e['got']}")

    return 0 if status == "ok" else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="audit_chain.py",
        description=(
            "Hash-chained Ed25519-signed audit log for Obsidian vault _auto_writes.md.\n\n"
            "IMPORTANT: --vault <path> is required for all subcommands.\n"
            "There is no hard-coded default — every invocation must name its vault."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--vault", required=True,
        help="Absolute path to the vault root (e.g. /Users/you/MyVault). REQUIRED.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # keygen
    p_kg = sub.add_parser("keygen", help="Generate (or rotate) Ed25519 keypair")
    p_kg.add_argument("--rotate", action="store_true",
                      help="Rotate existing keypair (archives old public key)")

    # migrate
    sub.add_parser("migrate", help="Genesis-sign existing pre-chain entries en bloc")

    # append
    p_ap = sub.add_parser("append", help="Append a new signed chain entry")
    p_ap.add_argument("--verb",   required=True, help="Verb (write, edit, note, rename, delete, …)")
    p_ap.add_argument("--path",   required=True, dest="path_arg", help="File path (vault-relative)")
    p_ap.add_argument("--reason", required=True, help="One-line reason (≤80 chars)")
    p_ap.add_argument("--timestamp", default=None,
                      help="Override timestamp (YYYY-MM-DD HH:MM); default is now (UTC)")
    p_ap.add_argument("--grep-prefix", action="store_true", dest="grep_prefix",
                      help=(
                          "Prepend a Karpathy grep-friendly header before the chain entry: "
                          "'## [YYYY-MM-DD] verb | basename'. "
                          "Header is NOT part of the chain — does not affect integrity. "
                          "Makes _auto_writes.md scriptable: grep '## .* write |' to find all writes."
                      ))

    # verify
    p_vf = sub.add_parser("verify", help="Verify the full chain integrity")
    p_vf.add_argument("--json", action="store_true", dest="emit_json",
                      help="Emit machine-readable JSON result (for automated health checks)")

    args   = parser.parse_args()
    vault  = Path(args.vault)

    if not vault.exists():
        _die(f"Vault path does not exist: {vault}", 2)

    if args.command == "keygen":
        cmd_keygen(vault, rotate=getattr(args, "rotate", False))
    elif args.command == "migrate":
        cmd_migrate(vault)
    elif args.command == "append":
        cmd_append(vault, args.verb, args.path_arg, args.reason,
                   timestamp=getattr(args, "timestamp", None),
                   grep_prefix=getattr(args, "grep_prefix", False))
    elif args.command == "verify":
        rc = cmd_verify(vault, emit_json=getattr(args, "emit_json", False))
        sys.exit(rc)


if __name__ == "__main__":
    main()
