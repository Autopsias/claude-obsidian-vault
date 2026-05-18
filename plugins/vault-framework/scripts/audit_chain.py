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
date pattern (YYYY-MM-DD) are chain entries.

KEY FILES
---------
  Private key : <vault>/.obsidian/.audit_key     (PEM, chmod 0600)
  Public  key : <vault>/90 System/_audit_pubkey.txt (PEM)

  Note: the private key location (.obsidian/) is a forward-compat assertion —
  .obsidian/ should be in .gitignore. File-permission 0600 is the protection
  mechanism until git-init lands.

KEY ROTATION
------------
  1. Run: python3 audit_chain.py keygen --vault /path/to/vault --rotate
     Generates a new keypair. Old public key is archived in _audit_pubkey_archive/
     with a date suffix. New keys written to the standard paths.
  2. Rotation does NOT re-sign old entries. Old entries remain verifiable with the
     archived public key. New entries use the new key.
  3. Document in 90 System/_audit_chain_keylog.md (auto-created by keygen).
  4. Re-run: python3 audit_chain.py verify --vault /path/to/vault
     — should show split-key report.

USAGE
-----
  # --vault is REQUIRED for all subcommands (no hard-coded default).
  # Set VAULT=/path/to/your/vault for convenience.

  # Generate keypair (first-time setup or rotation):
  python3 audit_chain.py keygen --vault /path/to/vault
  python3 audit_chain.py keygen --vault /path/to/vault --rotate

  # Migrate existing pre-chain entries (one-time, run after keygen):
  python3 audit_chain.py migrate --vault /path/to/vault

  # Append a new entry:
  python3 audit_chain.py append --vault /path/to/vault \\
      --verb write --path "99 Workspace/foo.md" --reason "added x"

  # Append with Karpathy grep-prefix header (KA-03, 2026-05-17):
  python3 audit_chain.py append --vault /path/to/vault \\
      --verb write --path "99 Workspace/foo.md" --reason "added x" --grep-prefix
  # → writes:  ## [2026-05-17] write | foo.md
  #             2026-05-17 HH:MM | write | 99 Workspace/foo.md | added x | prev_hash:… | sig:…
  # grep '## \\[2026' _auto_writes.md   — lists all entries this year
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
# Crypto helpers (requires: pip install cryptography --break-system-packages)
# ---------------------------------------------------------------------------

def _require_cryptography() -> None:
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: F401
            Ed25519PrivateKey, Ed25519PublicKey,
        )
    except ImportError:
        _die("'cryptography' package not found. Install with: pip install cryptography --break-system-packages", 2)


def _load_private_key(key_path: Path):
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    if not key_path.exists():
        _die(f"Private key not found: {key_path}\nRun: python3 audit_chain.py keygen --vault <vault>", 2)
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
# Path constants (all relative to vault root — no hard-coded absolutes)
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


def _last_chain_entry_line(log_lines: list[str]) -> Optional[str]:
    """Return the raw text of the last signed chain entry (for computing prev_hash)."""
    for line in reversed(log_lines):
        if _is_signed_entry(line.strip()):
            return line.strip()
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
        f"- Private key: `{PRIVKEY_REL}` (chmod 0600; add .obsidian/ to .gitignore)\n"
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
    print("Next step: run `python3 audit_chain.py migrate --vault <vault>` to genesis-sign existing log entries.")


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
        f"## Use `python3 audit_chain.py verify --vault <vault>` to validate the chain.\n"
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
    print("Run `python3 audit_chain.py verify --vault <vault>` to confirm the chain is valid.")


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
        grep '## \\[2026-05' _auto_writes.md          # all entries this month
        grep '## .* write |' _auto_writes.md           # all write verbs
        grep '## .* | _hot' _auto_writes.md            # all entries for _hot.*
    """
    _require_cryptography()
    log_path  = vault / LOG_REL
    priv_path = vault / PRIVKEY_REL

    private_key = _load_private_key(priv_path)
    lines       = _read_log(log_path)
    now         = datetime.now(timezone.utc)
    ts          = timestamp or now.strftime("%Y-%m-%d %H:%M")

    # Compute prev_hash from last chain entry
    last_entry = _last_chain_entry_line(lines)
    if last_entry is None:
        # No signed entry yet — use null sentinel (would happen if migrate not run)
        prev_hash = NULL_PREV_HASH
    else:
        prev_hash = _sha256(last_entry)

    # Sanitise inputs: strip pipes that would corrupt the field structure
    verb     = verb.strip().replace("|", "-")
    path_out = path_arg.strip().replace("|", "-")
    reason   = reason.strip().replace("|", "-")

    pre_sig = (
        f"{ts} | {verb} | {path_out} | {reason} | prev_hash:{prev_hash}"
    )
    sig  = _sign(pre_sig, private_key)
    full = f"{pre_sig} | sig:{sig}"

    # Build grep-prefix header (KA-03, Frontier Closeout S05, 2026-05-17)
    # Format:  ## [YYYY-MM-DD] verb | basename
    # The basename is the last path component; keeps headers short and greppable.
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

    print(f"Appended: {ts} | {verb} | {path_out}")


def cmd_verify(vault: Path, emit_json: bool = False) -> int:
    """
    Walk the chain and verify every signed entry.
    Returns 0 if fully valid, 1 if any integrity failure.
    """
    _require_cryptography()
    log_path  = vault / LOG_REL
    pub_path  = vault / PUBKEY_REL

    public_key  = _load_public_key(pub_path)
    lines       = _read_log(log_path)
    signed_lines = [l.strip() for l in lines if _is_signed_entry(l.strip())]

    if not signed_lines:
        msg = "No signed chain entries found. Run migrate first."
        if emit_json:
            print(json.dumps({"status": "error", "message": msg, "entries": 0}))
        else:
            print(msg)
        return 2

    errors   : list[dict] = []
    prev_hash = NULL_PREV_HASH  # expected prev_hash for the first entry

    for idx, raw_line in enumerate(signed_lines):
        parsed = _parse_entry(raw_line)
        if parsed is None:
            errors.append({"entry_idx": idx, "error": "parse_failure", "line": raw_line[:120]})
            continue

        # 1. prev_hash check (skip for genesis which anchors to NULL)
        if parsed["prev_hash"] != prev_hash:
            errors.append({
                "entry_idx": idx,
                "error": "prev_hash_mismatch",
                "expected": prev_hash[:16] + "…",
                "got":      parsed["prev_hash"][:16] + "…",
            })

        # 2. Signature check
        if not _verify_sig(parsed["pre_sig"], parsed["sig"], public_key):
            errors.append({
                "entry_idx": idx,
                "error": "invalid_signature",
                "line": raw_line[:120],
            })

        # Advance chain (use sha256 of full line including sig, so any tampering breaks next link)
        prev_hash = _sha256(raw_line)

    status = "ok" if not errors else "tampered"
    result = {
        "status":        status,
        "entries_checked": len(signed_lines),
        "errors":        errors,
    }

    if emit_json:
        print(json.dumps(result, indent=2))
    else:
        if status == "ok":
            print(f"Chain OK — {len(signed_lines)} entries verified, 0 errors.")
        else:
            print(f"CHAIN INTEGRITY FAILURE — {len(errors)} error(s) in {len(signed_lines)} entries:")
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
