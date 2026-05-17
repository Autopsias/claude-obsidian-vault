#!/usr/bin/env python3
"""
smoke_test_retrieval_template.py — M11 retrieval smoke-test template.

PURPOSE
-------
Template version of the M11 smoke-test for the galp-vault-canonical
shared references layer. New projects built from obsidian-project-new
or obsidian-project-convert use this as a starting point.

WHAT TO DO WHEN INSTANTIATING
------------------------------
1. Replace every {{PLACEHOLDER}} in the PINNED SUBSTRATE section below
   with your actual values from 90 System/_retrieval_contract.md.
2. Replace the QUERIES list with project-specific stable English queries.
   Each query needs:
     - "query": the text sent to the embedder
     - "expected_any_in_top5": list of vault-relative paths; ≥1 must appear
       in top-5 cosine matches for the query to pass
     - "rationale": why this query is stable and what regression it catches
3. Replace the _BASES_SPEC list with your vault's actual Base files and zones.
4. Update the VAULT_ROOT derivation if 90 System/ is named differently.
5. Run: python3 "90 System/_smoke_test_retrieval.py" --health
   to verify substrate before running the full smoke-test.

USAGE (same interface as the instantiated version)
------
  python3 "90 System/_smoke_test_retrieval.py"            # full run
  python3 "90 System/_smoke_test_retrieval.py" --health   # index-health check only
  python3 "90 System/_smoke_test_retrieval.py" --bases    # Bases functional smoke-test
  python3 "90 System/_smoke_test_retrieval.py" --report PATH  # write report to PATH

DEPENDENCIES
------------
- numpy           (likely already installed)
- sentence-transformers  (one-time pip install; ~1GB with torch on first run)

If sentence-transformers is missing, the script exits 2 and prints the
install command. The --health mode does NOT require sentence-transformers.

CROSS-REFERENCES (project-specific paths)
-----------------------------------------
- Pinned values:       90 System/_retrieval_contract.md
- Plugin discipline:   .claude/rules/plugin-security-discipline.md
- Full eval (M2):      90 System/_eval_retrieval.md
- Cascade definition:  CLAUDE.md + _operating_guide.md P-3
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


# ──────────────────────────────────────────────────────────────────────────────
# Pinned substrate — must match 90 System/_retrieval_contract.md
# Replace these with your actual pinned values at scaffold time.
# ──────────────────────────────────────────────────────────────────────────────

# PROJECT-SPECIFIC: Replace with your embedding model key
PINNED_MODEL_KEY = "{{EMBED_MODEL_KEY}}"   # e.g. "TaylorAI/bge-micro-v2"

# PROJECT-SPECIFIC: Replace with your model's embedding dimension
PINNED_DIM = {{EMBED_DIMS}}                # e.g. 384

# PROJECT-SPECIFIC: Replace with your pinned Smart Connections version
PINNED_PLUGIN_VERSION = "{{SC_PLUGIN_VERSION}}"  # e.g. "4.5.0"

# Pass logic: at least one expected path in top-N is a pass.
PASS_TOP_N = 5


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures — project-specific stable English queries
# ──────────────────────────────────────────────────────────────────────────────
# Replace all entries below with vault-specific queries.
#
# Selection criteria:
#   - Use English queries only (multilingual content is handled by the M2 eval
#     via the M9 fall-through rule — do NOT duplicate that here)
#   - Choose queries whose top hits have been stable for ≥2 weeks
#   - Each query should exercise a DIFFERENT document/zone to maximise coverage
#   - 5 queries is the recommended minimum; 10 is the recommended maximum
#
# Do NOT chase rank churn. The bar is "at least one expected in top-5",
# not "top-1 stays put". Update expected_any_in_top5 when top hits genuinely
# shift (e.g. after a major vault restructure or bulk ingestion).
#
# To probe a query's current top hits:
#   mcp__smart-connections__lookup with limit=10 and include_blocks=False

QUERIES: list[dict] = [
    # ── FIXTURE 1: Core project/state document ───────────────────────────────
    # PURPOSE: Verify the primary project state MOC clusters correctly.
    # Replace with a query that should hit your main project document.
    {
        "query": "{{PROJECT_NAME}} programme overview",
        "expected_any_in_top5": [
            "30 Projects/{{PROJECT_SLUG}}.md",         # state MOC
            "50 Sources/{{KEY_SOURCE_SLUG}}.md",       # primary source doc
        ],
        "rationale": (
            "State MOC + primary source — the two highest-traffic entry points. "
            "Probes that the most central project artefacts cluster correctly. "
            "Degradation here means semantic is broken on core vocabulary."
        ),
    },
    # ── FIXTURE 2: People / role recall ──────────────────────────────────────
    # PURPOSE: Verify person-page recall by role, not just by name.
    # Replace with a query about a named role/decision rather than a person's name.
    {
        "query": "{{KEY_DECISION_OR_RULING}} constraint ruling",
        "expected_any_in_top5": [
            "10 People/{{DECISION_MAKER_SLUG}}.md",    # person page
            "50 Sources/{{DECISION_SOURCE_SLUG}}.md",  # supporting source
        ],
        "rationale": (
            "Probes person-page recall by role rather than by name — "
            "if SC drops to keyword matching, the person page won't surface."
        ),
    },
    # ── FIXTURE 3: System governance ─────────────────────────────────────────
    # PURPOSE: Verify plugin/contract governance files are indexed.
    {
        "query": "Smart Connections plugin security audit license",
        "expected_any_in_top5": [
            "90 System/_plugin_security.md",
            "90 System/_retrieval_contract.md",
        ],
        "rationale": (
            "Plugin audit + retrieval contract — the two governance files most "
            "needed during a plugin update review. SC index corruption surfaces here."
        ),
    },
    # ── FIXTURE 4: Meeting / debrief recall ──────────────────────────────────
    # PURPOSE: Verify meeting notes index by location + event type.
    # Replace with a query anchored to a specific meeting or workshop.
    {
        "query": "{{KEY_MEETING_LOCATION_OR_TYPE}} workshop debrief",
        "expected_any_in_top5": [
            "40 Meetings/{{MEETING_SLUG}}.md",          # primary meeting note
            "50 Sources/{{MEETING_OUTPUT_SLUG}}.md",    # meeting output/source
        ],
        "rationale": (
            "Probes that meeting notes index by location + event type — "
            "common retrieval pattern for prep work and debrief lookups."
        ),
    },
    # ── FIXTURE 5: Concept / strategy recall ─────────────────────────────────
    # PURPOSE: Verify a key strategy/architecture concept surfaces correctly.
    {
        "query": "{{KEY_CONCEPT}} concept strategy",
        "expected_any_in_top5": [
            "60 Concepts/{{CONCEPT_SLUG}}.md",          # concept page
            "70 Decisions/{{RELATED_DECISION_SLUG}}.md", # related decision
        ],
        "rationale": (
            "Foundational strategy concept + its formal decision record. "
            "Degradation here means semantic is broken on strategy vocabulary."
        ),
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Bases smoke-test spec
# ──────────────────────────────────────────────────────────────────────────────
# Replace with your vault's actual Base files and zones.
# Run trigger: Obsidian version drift (minor/major) detected by vault health check.
# Skipped on every normal weekly run.
#
# Proxy approach: filesystem + frontmatter assertions rather than live Bases queries.
#   Check 1 (per Base): .base file present + non-empty (schema intact)
#   Check 2 (per Base): primary-type file count ≥ expected_min
#   Check 3 (per Base): specific frontmatter filter ≥ expected_min OR key file exists
#
# PROJECT-SPECIFIC: Update zone paths, type values, expected_min counts,
# and file_exists paths to match your vault's actual content at go-live.

_BASES_SPEC: list[dict] = [
    {
        "name": "People",
        "base_file": "90 System/Bases/People.base",
        "queries": [
            {
                "label": ".base file present and non-empty",
                "check": "base_file_health",
                "base_file": "90 System/Bases/People.base",
                "rationale": "People.base file exists and is ≥50 bytes (schema intact).",
            },
            {
                "label": "all people in vault (count_type ≥{{PEOPLE_MIN_COUNT}})",
                "check": "count_type",
                "zone": "10 People",
                "type_value": "person",
                "expected_min": 3,   # PROJECT-SPECIFIC: update at go-live
                "rationale": "≥N person-typed files in 10 People/ — baseline count.",
            },
            {
                "label": "key person page present",
                "check": "file_exists",
                "rel_path": "10 People/{{KEY_PERSON_SLUG}}.md",  # PROJECT-SPECIFIC
                "rationale": "Load-bearing key person page — absence implies zone corruption.",
            },
        ],
    },
    {
        "name": "Companies",
        "base_file": "90 System/Bases/Companies.base",
        "queries": [
            {
                "label": ".base file present and non-empty",
                "check": "base_file_health",
                "base_file": "90 System/Bases/Companies.base",
                "rationale": "Companies.base file exists and is ≥50 bytes.",
            },
            {
                "label": "all companies in vault (count_type ≥{{COMPANIES_MIN_COUNT}})",
                "check": "count_type",
                "zone": "20 Companies",
                "type_value": "company",
                "expected_min": 2,   # PROJECT-SPECIFIC: update at go-live
                "rationale": "At minimum N companies must be present.",
            },
            {
                "label": "primary counterparty company page present",
                "check": "file_exists",
                "rel_path": "20 Companies/{{PRIMARY_COMPANY_SLUG}}.md",  # PROJECT-SPECIFIC
                "rationale": "Primary counterparty page — absence implies zone corruption.",
            },
        ],
    },
    {
        "name": "Projects",
        "base_file": "90 System/Bases/Projects.base",
        "queries": [
            {
                "label": ".base file present and non-empty",
                "check": "base_file_health",
                "base_file": "90 System/Bases/Projects.base",
                "rationale": "Projects.base file exists and is ≥50 bytes.",
            },
            {
                "label": "primary project state MOC present",
                "check": "file_exists",
                "rel_path": "30 Projects/{{PROJECT_SLUG}}.md",  # PROJECT-SPECIFIC
                "rationale": "Primary state MOC — absence is a vault failure.",
            },
            {
                "label": "projects with status field (≥1)",
                "check": "frontmatter_exists",
                "zone": "30 Projects",
                "field": "status",
                "expected_min": 1,
                "rationale": "At least one project carries status: (probes filter queries).",
            },
        ],
    },
    {
        "name": "Meetings",
        "base_file": "90 System/Bases/Meetings.base",
        "queries": [
            {
                "label": ".base file present and non-empty",
                "check": "base_file_health",
                "base_file": "90 System/Bases/Meetings.base",
                "rationale": "Meetings.base file exists and is ≥50 bytes.",
            },
            {
                "label": "all meetings in vault (count_type ≥{{MEETINGS_MIN_COUNT}})",
                "check": "count_type",
                "zone": "40 Meetings",
                "type_value": "meeting",
                "expected_min": 3,   # PROJECT-SPECIFIC: update at go-live
                "rationale": "≥N meeting-typed files in 40 Meetings/.",
            },
            {
                "label": "meetings with date in {{CURRENT_YEAR}} (≥{{YEAR_MEETINGS_MIN}})",
                "check": "frontmatter_contains",
                "zone": "40 Meetings",
                "field": "date",
                "contains": "{{CURRENT_YEAR}}",  # PROJECT-SPECIFIC
                "expected_min": 2,   # PROJECT-SPECIFIC: update at go-live
                "rationale": "Meeting notes carry date: YYYY-…; probes date-filter resolution.",
            },
        ],
    },
    {
        "name": "Decisions",
        "base_file": "90 System/Bases/Decisions.base",
        "queries": [
            {
                "label": ".base file present and non-empty",
                "check": "base_file_health",
                "base_file": "90 System/Bases/Decisions.base",
                "rationale": "Decisions.base file exists and is ≥50 bytes.",
            },
            {
                "label": "all decisions in vault (count_type ≥{{DECISIONS_MIN_COUNT}})",
                "check": "count_type",
                "zone": "70 Decisions",
                "type_value": "decision",
                "expected_min": 2,   # PROJECT-SPECIFIC: update at go-live
                "rationale": "≥N decision-typed files in 70 Decisions/.",
            },
            {
                "label": "primary decision file present",
                "check": "file_exists",
                "rel_path": "70 Decisions/{{KEY_DECISION_SLUG}}.md",  # PROJECT-SPECIFIC
                "rationale": "Load-bearing strategy decision — absence implies zone corruption.",
            },
        ],
    },
    {
        "name": "Sources",
        "base_file": "90 System/Bases/Sources.base",
        "queries": [
            {
                "label": ".base file present and non-empty",
                "check": "base_file_health",
                "base_file": "90 System/Bases/Sources.base",
                "rationale": "Sources.base file exists and is ≥50 bytes.",
            },
            {
                "label": "all sources in vault (count_type ≥{{SOURCES_MIN_COUNT}})",
                "check": "count_type",
                "zone": "50 Sources",
                "type_value": "source",
                "expected_min": 10,   # PROJECT-SPECIFIC: update at go-live
                "rationale": "≥N source-typed files in 50 Sources/.",
            },
            {
                "label": "primary source document present (glob: {{KEY_SOURCE_GLOB}})",
                "check": "filename_glob",
                "zone": "50 Sources",
                "pattern": "{{KEY_SOURCE_GLOB}}",  # e.g. "*Peninsula*6*"
                "expected_min": 1,
                "rationale": "At least one primary source file must be present.",
            },
        ],
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Vault layout — update VAULT_ROOT derivation if your system files directory
# is named differently (e.g. "System/" instead of "90 System/")
# ──────────────────────────────────────────────────────────────────────────────
VAULT_ROOT = Path(__file__).resolve().parent.parent  # 90 System/ → vault root
SMART_ENV = VAULT_ROOT / ".smart-env"
SMART_ENV_CFG = SMART_ENV / "smart_env.json"
SMART_ENV_MULTI = SMART_ENV / "multi"
RETRIEVAL_CONTRACT = VAULT_ROOT / "90 System" / "_retrieval_contract.md"


# ──────────────────────────────────────────────────────────────────────────────
# Result model
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class TopHit:
    path: str
    score: float
    is_expected: bool


@dataclass
class QueryResult:
    query: str
    expected: list[str]
    top: list[TopHit]
    passed: bool
    rationale: str


# ──────────────────────────────────────────────────────────────────────────────
# .ajson parser
# ──────────────────────────────────────────────────────────────────────────────
def parse_ajson(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    if text.endswith(","):
        text = text[:-1]
    wrapped = "{" + text + "}"
    return json.loads(wrapped)


def iter_source_embeddings(smart_env_multi: Path) -> Iterator[tuple[str, list[float]]]:
    """Yield (vault_relative_path, embedding_vec) per source-level record."""
    for ajson_path in smart_env_multi.iterdir():
        if not ajson_path.name.endswith(".ajson"):
            continue
        try:
            obj = parse_ajson(ajson_path)
        except json.JSONDecodeError:
            continue
        for key, val in obj.items():
            if not key.startswith("smart_sources:"):
                continue
            if not isinstance(val, dict):
                continue
            rel_path = val.get("path")
            embeddings = val.get("embeddings", {}) or {}
            model_record = embeddings.get(PINNED_MODEL_KEY) or {}
            vec = model_record.get("vec")
            if rel_path and isinstance(vec, list) and len(vec) == PINNED_DIM:
                yield rel_path, vec


# ──────────────────────────────────────────────────────────────────────────────
# Substrate health check — no model load required
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class HealthReport:
    ok: bool
    problems: list[str]
    info: dict


def health_check() -> HealthReport:
    problems: list[str] = []
    info: dict = {}

    if not SMART_ENV.is_dir():
        problems.append(f".smart-env/ not found at {SMART_ENV}")
        return HealthReport(False, problems, info)
    info["smart_env"] = str(SMART_ENV)

    if not SMART_ENV_CFG.is_file():
        problems.append(f".smart-env/smart_env.json missing at {SMART_ENV_CFG}")
    else:
        try:
            cfg = json.loads(SMART_ENV_CFG.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            problems.append(f".smart-env/smart_env.json is not valid JSON: {e}")
            cfg = {}
        embed_cfg = (
            cfg.get("smart_sources", {}).get("embed_model", {}).get("transformers", {})
            or {}
        )
        live_model = embed_cfg.get("model_key")
        info["live_embed_model"] = live_model
        info["pinned_embed_model"] = PINNED_MODEL_KEY
        if live_model and live_model != PINNED_MODEL_KEY:
            problems.append(
                f"Embedding model drift: smart_env.json reports {live_model!r}, "
                f"contract pins {PINNED_MODEL_KEY!r}. Re-baseline the contract "
                f"and re-run the M2 eval before treating this as a passing update."
            )

    if not SMART_ENV_MULTI.is_dir():
        problems.append(f".smart-env/multi/ not found at {SMART_ENV_MULTI}")
    else:
        ajson_count = sum(
            1 for p in SMART_ENV_MULTI.iterdir() if p.name.endswith(".ajson")
        )
        info["ajson_file_count"] = ajson_count
        if ajson_count < 10:
            problems.append(
                f".smart-env/multi/ only contains {ajson_count} .ajson files — "
                f"vault may not be fully indexed. Wait for Smart Connections to finish."
            )

    return HealthReport(not problems, problems, info)


# ──────────────────────────────────────────────────────────────────────────────
# Cosine top-K
# ──────────────────────────────────────────────────────────────────────────────
def normalize_rows(mat):
    import numpy as np
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    return mat / np.clip(norms, 1e-12, None)


def topk(query_vec, src_paths: list[str], src_mat_n, k: int) -> list[tuple[str, float]]:
    import numpy as np
    qv = query_vec / max(float(np.linalg.norm(query_vec)), 1e-12)
    sims = src_mat_n @ qv
    if k >= len(src_paths):
        order = sims.argsort()[::-1]
    else:
        idx = sims.argpartition(-k)[-k:]
        order = idx[sims[idx].argsort()[::-1]]
    return [(src_paths[i], float(sims[i])) for i in order]


# ──────────────────────────────────────────────────────────────────────────────
# Full run
# ──────────────────────────────────────────────────────────────────────────────
def run_full(out) -> int:
    t_start = time.time()

    h = health_check()
    print_section(out, "Substrate health")
    for k, v in h.info.items():
        out.write(f"  {k}: {v}\n")
    if not h.ok:
        out.write("\n")
        for p in h.problems:
            out.write(f"  FAIL: {p}\n")
        out.write("\nAborting full run — fix substrate first.\n")
        return 2
    out.write("  OK\n\n")

    try:
        import numpy as np
    except ImportError:
        out.write(
            "FAIL: numpy is required.\n"
            "  Install: pip3 install --break-system-packages numpy\n"
        )
        return 2

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        out.write(
            "FAIL: sentence-transformers is required for the full smoke-test.\n"
            "  Install: pip3 install --break-system-packages sentence-transformers\n"
            "  (~1GB on first run — pulls torch + the model.)\n"
            "\n"
            "Quick alternative — run the substrate health check only:\n"
            '  python3 "90 System/_smoke_test_retrieval.py" --health\n'
        )
        return 2

    print_section(out, "Loading source embeddings from .smart-env/multi/")
    t_load = time.time()
    pairs = list(iter_source_embeddings(SMART_ENV_MULTI))
    if not pairs:
        out.write("  FAIL: zero source-level embeddings extracted.\n")
        return 2
    src_paths = [p for p, _ in pairs]
    src_mat = np.array([v for _, v in pairs], dtype=np.float32)
    src_mat_n = normalize_rows(src_mat)
    out.write(
        f"  Loaded {len(src_paths):,} source embeddings "
        f"(dim={src_mat.shape[1]}) in {time.time() - t_load:.2f}s\n\n"
    )

    print_section(out, f"Loading embedding model ({PINNED_MODEL_KEY})")
    t_model = time.time()
    model = SentenceTransformer(PINNED_MODEL_KEY)
    out.write(f"  Loaded in {time.time() - t_model:.2f}s\n\n")

    print_section(out, f"Running {len(QUERIES)} smoke-test queries")
    t_q = time.time()
    query_texts = [q["query"] for q in QUERIES]
    query_vecs = model.encode(query_texts, normalize_embeddings=False)
    out.write(f"  Embedded {len(query_texts)} queries in {time.time() - t_q:.2f}s\n\n")

    results: list[QueryResult] = []
    for q, qv in zip(QUERIES, query_vecs):
        top_pairs = topk(qv, src_paths, src_mat_n, PASS_TOP_N)
        expected = set(q["expected_any_in_top5"])
        top_hits = [TopHit(p, s, p in expected) for p, s in top_pairs]
        passed = any(h.is_expected for h in top_hits)
        results.append(
            QueryResult(
                query=q["query"],
                expected=q["expected_any_in_top5"],
                top=top_hits,
                passed=passed,
                rationale=q.get("rationale", ""),
            )
        )

    print_section(out, "Per-query results")
    for r in results:
        verdict = "PASS" if r.passed else "FAIL"
        out.write(f"\n[{verdict}] {r.query!r}\n")
        for hit in r.top:
            mark = "  *" if hit.is_expected else "   "
            out.write(f"  {mark} {hit.score:.4f}  {hit.path}\n")
        if not r.passed:
            out.write("  Expected ANY of:\n")
            for e in r.expected:
                out.write(f"      {e}\n")

    n_pass = sum(1 for r in results if r.passed)
    n_fail = len(results) - n_pass
    out.write("\n")
    print_section(out, "Summary")
    out.write(
        f"  Queries: {len(results)}  ·  pass: {n_pass}  ·  fail: {n_fail}\n"
        f"  Substrate: {len(src_paths):,} source embeddings, model {PINNED_MODEL_KEY}\n"
        f"  Wall time: {time.time() - t_start:.2f}s\n"
        f"  Verdict: {'ALL PASS' if n_fail == 0 else 'FAIL — at least one query missed'}\n"
    )
    if n_fail:
        out.write(
            "\nNext steps on FAIL:\n"
            "  1. Confirm Obsidian + Smart Connections is open and indexed.\n"
            "  2. Check 99 Workspace/_session_handoff.md for any mid-rebuild flags.\n"
            "  3. If post-update: downgrade per plugin-security-discipline.md rule 2.\n"
            "  4. If healthy: a fixture has drifted. Re-probe the failing query via\n"
            "     mcp__smart-connections__lookup and update QUERIES[].expected_any_in_top5.\n"
        )
    return 0 if n_fail == 0 else 1


# ──────────────────────────────────────────────────────────────────────────────
# Health-only mode
# ──────────────────────────────────────────────────────────────────────────────
def run_health_only(out) -> int:
    h = health_check()
    print_section(out, "Substrate health")
    for k, v in h.info.items():
        out.write(f"  {k}: {v}\n")
    out.write("\n")
    if h.ok:
        out.write("  OK — substrate present, model matches the contract pin.\n")
        out.write("\nNote: this is a structural check only. To validate query\n")
        out.write("behaviour, run without --health (requires sentence-transformers).\n")
        return 0
    for p in h.problems:
        out.write(f"  FAIL: {p}\n")
    return 2


# ──────────────────────────────────────────────────────────────────────────────
# Bases smoke-test helpers
# ──────────────────────────────────────────────────────────────────────────────
def _read_frontmatter(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end].strip()
    try:
        import yaml  # type: ignore[import]
        result = yaml.safe_load(fm_text)
        return result if isinstance(result, dict) else {}
    except Exception:
        pass
    result_fb: dict = {}
    for line in fm_text.splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            result_fb[k.strip()] = v.strip().strip('"').strip("'")
    return result_fb


def _md_files_in_zone(zone_dir: Path) -> list[Path]:
    _EXCLUDE = {".obsidian", "_archive", ".git", ".smart-env"}
    return [
        f for f in zone_dir.rglob("*.md")
        if not any(part in _EXCLUDE for part in f.parts)
    ]


def _run_bases_query(vault: Path, q: dict) -> tuple[bool, str]:
    check = q["check"]

    if check == "base_file_health":
        p = vault / q["base_file"]
        if not p.exists():
            return False, f"missing: {q['base_file']}"
        sz = p.stat().st_size
        if sz < 50:
            return False, f"suspiciously small ({sz} bytes): {q['base_file']}"
        return True, f"{q['base_file']} present ({sz} bytes)"

    if check == "file_exists":
        p = vault / q["rel_path"]
        if p.exists():
            return True, f"{q['rel_path']} present"
        return False, f"missing: {q['rel_path']}"

    zone_dir = vault / q.get("zone", "")
    if not zone_dir.is_dir():
        return False, f"zone not found: {q.get('zone')}"
    md_files = _md_files_in_zone(zone_dir)

    if check == "count_type":
        type_val = q["type_value"]
        count = sum(
            1 for f in md_files
            if _read_frontmatter(f).get("type") == type_val
        )
        exp = q["expected_min"]
        if count >= exp:
            return True, f"{count} {type_val}-typed files in {q['zone']} (min {exp})"
        return False, f"only {count} {type_val}-typed files in {q['zone']} (min {exp})"

    if check == "frontmatter_contains":
        field, contains, exp = q["field"], q["contains"], q["expected_min"]
        count = sum(
            1 for f in md_files
            if contains in str(_read_frontmatter(f).get(field) or "")
        )
        if count >= exp:
            return True, f"{count} files where {field} contains {contains!r} (min {exp})"
        return False, f"only {count} files where {field} contains {contains!r} (min {exp})"

    if check == "frontmatter_exists":
        field, exp = q["field"], q["expected_min"]
        count = sum(
            1 for f in md_files
            if _read_frontmatter(f).get(field) not in (None, "", [])
        )
        if count >= exp:
            return True, f"{count} files with non-empty {field}: (min {exp})"
        return False, f"only {count} files with non-empty {field}: (min {exp})"

    if check == "filename_glob":
        pattern, exp = q["pattern"], q["expected_min"]
        count = sum(1 for f in md_files if fnmatch.fnmatch(f.name, pattern))
        if count >= exp:
            return True, f"{count} files in {q['zone']} matching {pattern!r} (min {exp})"
        return False, f"only {count} files in {q['zone']} matching {pattern!r} (min {exp})"

    return False, f"unknown check type: {check!r}"


# ──────────────────────────────────────────────────────────────────────────────
# Bases run (--bases mode)
# ──────────────────────────────────────────────────────────────────────────────
def run_bases(out) -> int:
    print_section(out, "Bases functional smoke-test (6 Bases × 3 queries)")
    out.write(
        "  Trigger: Obsidian version drift (minor/major) — skip on normal weekly run.\n"
        "  Proxy approach: filesystem + frontmatter assertions; no Obsidian MCP required.\n\n"
    )

    n_total = 0
    n_pass = 0

    for spec in _BASES_SPEC:
        base_name = spec["name"]
        bar = "─" * max(0, 52 - len(base_name))
        out.write(f"── {base_name} Base {bar}\n")
        for q in spec["queries"]:
            ok, msg = _run_bases_query(VAULT_ROOT, q)
            verdict = "PASS" if ok else "FAIL"
            out.write(f"  [{verdict}] {q['label']}: {msg}\n")
            n_total += 1
            if ok:
                n_pass += 1
        out.write("\n")

    n_fail = n_total - n_pass
    print_section(out, "Bases smoke-test summary")
    out.write(
        f"  Bases: {len(_BASES_SPEC)}  ·  checks: {n_total}  ·  "
        f"pass: {n_pass}  ·  fail: {n_fail}\n"
        f"  Verdict: {'ALL PASS' if n_fail == 0 else 'FAIL — at least one check missed'}\n"
    )
    if n_fail:
        out.write(
            "\nNext steps on FAIL:\n"
            "  1. For base_file_health FAILs: check if Obsidian upgrade zeroed/removed\n"
            "     the .base file; restore from git or backup.\n"
            "  2. For count_type / frontmatter FAILs: verify zone notes are intact and\n"
            "     have correct `type:` frontmatter.\n"
            "  3. Run `python3 \"90 System/_bases_verifier.py\"` for full zone audit.\n"
            "  4. If Bases plugin broken at UI level: downgrade Obsidian or report to\n"
            "     Obsidian forum; do not trust Bases retrieval until resolved.\n"
        )
    return 0 if n_fail == 0 else 1


# ──────────────────────────────────────────────────────────────────────────────
# Output helpers
# ──────────────────────────────────────────────────────────────────────────────
def print_section(out, title: str) -> None:
    out.write(f"── {title} " + "─" * max(0, 70 - len(title) - 4) + "\n")


def print_header(out) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out.write(
        "═" * 76 + "\n"
        f" {{PROJECT_NAME}} Vault — M11 retrieval smoke-test\n"
        f" Run: {now}\n"
        f" Vault: {VAULT_ROOT}\n"
        f" Pinned model: {PINNED_MODEL_KEY} (dim {PINNED_DIM}) · "
        f"plugin v{PINNED_PLUGIN_VERSION}\n"
        + "═" * 76 + "\n\n"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Entry
# ──────────────────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="M11 retrieval smoke-test."
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Run substrate health check only (no model load, no query embed).",
    )
    parser.add_argument(
        "--bases",
        action="store_true",
        help="Run Bases functional smoke-test. Triggered by Obsidian version drift.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the human-readable report to this path (default: stdout).",
    )
    args = parser.parse_args()

    def _dispatch(out) -> int:
        if args.health:
            return run_health_only(out)
        if args.bases:
            return run_bases(out)
        return run_full(out)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        out = args.report.open("w", encoding="utf-8")
        try:
            print_header(out)
            code = _dispatch(out)
        finally:
            out.close()
        verdict = {0: "PASS", 1: "FAIL", 2: "ABORT"}.get(code, str(code))
        print(f"M11 smoke-test {verdict} (exit {code}) — report: {args.report}", file=sys.stderr)
        return code

    print_header(sys.stdout)
    return _dispatch(sys.stdout)


if __name__ == "__main__":
    sys.exit(main())
