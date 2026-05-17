#!/usr/bin/env python3
"""
populate-claude-md.py — Render a CLAUDE.md from a parameterised template + values.yaml.

Usage:
    python3 populate-claude-md.py \\
        [--template CLAUDE-template.md] \\
        [--values   values-galp.yaml]   \\
        [--output   CLAUDE.md]
    
    # Print to stdout:
    python3 populate-claude-md.py --output -

Defaults (relative to this script's directory):
    --template  CLAUDE-template.md
    --values    values-galp.yaml
    --output    CLAUDE.md

Variable syntax: {{VAR_NAME}} in the template.
Multi-line YAML block scalars (|-) are supported.

Round-trip test:
    python3 populate-claude-md.py --values values-galp.yaml --output /tmp/CLAUDE-rt.md
    diff /tmp/CLAUDE-rt.md /path/to/vault/CLAUDE.md  # must exit 0
"""

import argparse, os, re, sys

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


def load_values_fallback(path: str) -> dict:
    """
    Minimal single-pass YAML parser that handles:
    - key: "quoted value"
    - key: bare value
    - key: |- ... block scalars (strips leading 2-space indent)
    """
    values: dict = {}
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")
        # Skip comments and blank lines
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        # Key: value or Key: |-
        if ":" in line and not line.startswith(" "):
            k, _, rest = line.partition(":")
            rest = rest.strip()
            if rest in ("|-", "|"):
                # Collect block scalar lines
                i += 1
                block_lines = []
                while i < len(lines):
                    bl = lines[i].rstrip("\n")
                    if bl and not bl.startswith(" ") and not bl.startswith("\t"):
                        break
                    # Strip exactly 2-space indent
                    if bl.startswith("  "):
                        block_lines.append(bl[2:])
                    else:
                        block_lines.append(bl)
                    i += 1
                # Strip trailing blank lines (|- behaviour)
                while block_lines and block_lines[-1].strip() == "":
                    block_lines.pop()
                values[k.strip()] = "\n".join(block_lines)
            else:
                # Scalar — strip surrounding quotes
                v = rest.strip('"\'')
                values[k.strip()] = v
                i += 1
        else:
            i += 1
    return values


def load_values(path: str) -> dict:
    if _HAS_YAML:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return {k: str(v) for k, v in data.items()}
    else:
        print("WARNING: PyYAML not available; using fallback parser.", file=sys.stderr)
        return load_values_fallback(path)


def populate(template: str, values: dict) -> str:
    """
    Replace {{KEY}} with values[KEY] for every key, longest keys first
    (prevents prefix-collision bugs like VAULT_PATH vs VAULT_FOLDER_NAME).
    """
    result = template
    for key in sorted(values, key=len, reverse=True):
        result = result.replace("{{" + key + "}}", values[key])
    # Warn on any remaining {{…}} placeholders
    unresolved = re.findall(r"\{\{[A-Z_]+\}\}", result)
    if unresolved:
        print(f"WARNING: unresolved variables: {sorted(set(unresolved))}", file=sys.stderr)
    return result


def main() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Render CLAUDE.md from a parameterised template + values YAML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--template", default=os.path.join(here, "CLAUDE-template.md"),
                    help="Path to the CLAUDE-template.md file")
    ap.add_argument("--values",   default=os.path.join(here, "values-galp.yaml"),
                    help="Path to the values YAML file")
    ap.add_argument("--output",   default=os.path.join(here, "CLAUDE.md"),
                    help='Output path (use "-" for stdout)')
    args = ap.parse_args()

    with open(args.template, encoding="utf-8") as f:
        template = f.read()

    values = load_values(args.values)
    rendered = populate(template, values)

    if args.output == "-":
        sys.stdout.write(rendered)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(rendered)
        print(f"Written → {args.output}")


if __name__ == "__main__":
    main()
