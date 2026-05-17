# Bases — Shared References

This directory contains the canonical Obsidian Bases definitions and the vault
verifier from the Galp Vault reference implementation.

## Contents

### 6 Primary Bases

| File | Type filter | Zone |
|------|-------------|------|
| `People.base` | `person` | `10 People/` |
| `Companies.base` | `company` | `20 Companies/` |
| `Projects.base` | `project` | `30 Projects/` |
| `Meetings.base` | `meeting` | `40 Meetings/` |
| `Sources.base` | `source` | `50 Sources/` |
| `Decisions.base` | `decision` | `70 Decisions/` |

### 2 View-Only Bases (cross-zone)

| File | Purpose |
|------|---------|
| `Open Items.base` | Cross-zone view of files with open action items |
| `Tier-2 Sources.base` | Cross-zone view of secondary/reference sources |

### 3 Temporal Bases (BT-04/05/06 — bitemporal retrieval)

| File | P-3 Route | Query trigger |
|------|-----------|---------------|
| `Latest Only.base` | Route A | "current", "latest" |
| `As Of.base` | Route B | "as of <date>", "on <date>" |
| `Version Chain.base` | Route C | "evolved", "changed", "history from X to Y" |

The temporal bases require the bitemporal frontmatter fields on all source/decision
documents: `document_date`, `is_latest_version`, and (when superseded) `superseded_by`,
`superseded_date`, `previous_version`. Templates in `../templates/` carry these fields.

### bases-verifier.py

Full 1071-line vault verifier (M7). Walks all `.base` files, extracts each Base's
schema (type filter + required fields), then checks every typed-zone `.md` file for:

1. Clean YAML frontmatter parse
2. `type:` value in the P-4 closed vocabulary
3. All required keys present and non-empty for the type's bound Base
4. Wikilinks in frontmatter resolve to existing notes (basename or alias match)

Additional checks: BC-01/02/03 (bitemporal field consistency), wikilink graph
resolution, YAML validity.

**Usage:**
```bash
python3 "90 System/_bases_verifier.py"                    # full run
python3 "90 System/_bases_verifier.py" --strict           # exit 1 on violations
python3 "90 System/_bases_verifier.py" --report PATH      # custom report path
python3 "90 System/_bases_verifier.py" --vault PATH       # vault root override
```

**Exit codes:** 0 = no violations (or violations without --strict), 1 = --strict +
violations, 2 = unexpected error (missing Bases dir, malformed .base, IO failure).

## How to instantiate for a new vault

1. **Copy this entire `bases/` directory** into `90 System/Bases/` in the new vault.
   Rename the directory to `Bases` (capitalised, matching Obsidian convention).

2. **Copy `bases-verifier.py`** to `90 System/_bases_verifier.py`.

3. **Open each `.base` file in a text editor** and update any hardcoded project names
   (e.g. "Peninsula" in Projects.base) to match the new vault's project name.

4. **For the temporal bases** (`As Of.base` in particular): `As Of.base` contains a
   manual-edit placeholder for `AS_OF_DATE`. The runner must plug in the target date
   before each use — it is not automated.

5. **Run the verifier** after adding the first batch of typed-zone notes to confirm
   the schema enforcement is working: `python3 "90 System/_bases_verifier.py"`.

6. **Update `_retrieval_contract.md`** to reference the pinned Obsidian version
   against which the `.base` filter syntax was validated. Obsidian minor version
   bumps can silently break Bases filter-syntax resolution — this is the regression
   the `_smoke_test_retrieval.py --bases` mode catches.

## P-4 Type vocabulary

The verifier enforces this closed set:

```
person | company | project | meeting | source | concept | decision |
guide | contract | log | handoff | handoff_archive | eval | inbox |
daily | template | base | system
```

Allow-listed (valid but Bases-unbound — no per-Base schema check):
`inbox | daily | log | handoff | handoff_archive | system | contract | guide | eval | template | base | concept`
