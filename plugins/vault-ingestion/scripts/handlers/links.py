"""
handlers/links.py — Auto-link-candidate population for the v2 ingestion pipeline.

Contract:   90 System/_ingestion_contract.md §12 (AL-04, added 2026-05-17)
Plan:       99 Workspace/_plan_galp_frontier_adoption_2026-05-16.html (S08)
Authored:   2026-05-17 (AL-05 of Frontier Adoption plan)

What this module does
---------------------
Given the body text of a newly-ingested .md, produce the
`pipeline.link_candidates` list (contract §12) plus the detected `language`
that ingest.py writes into frontmatter. Composed of three steps, all
graceful-degradation by design — failure of any sub-step never blocks
ingest:

    1. Language detection
       - prefers `langdetect` if installed,
       - falls back to a tiny PT/EN/UNK word-frequency heuristic.

    2. Catalog-driven exact matching (AL-03)
       - via `LinkMatcher.from_catalog(_entity_catalog.json)`.
       - All hits land with `confidence: 'exact'`.

    3. spaCy NER for off-catalog entities (best-effort)
       - loads `pt_core_news_lg` for PT bodies / `en_core_web_lg` for EN /
         `xx_ent_wiki_sm` as a small fallback — whichever first one is
         actually installed wins.
       - keeps PERSON / ORG / LOC / GPE entities whose surface form is
         NOT already covered by the exact pass.
       - emits these with `confidence: 'ner'` and `entity_id:
         'ner/<surface-form>'`.

Dedupe + cap (§12.2)
--------------------
After both passes:

    - dedupe by `(entity_id, matched_string)`, keeping the first
      occurrence (smallest start offset);
    - sort by `(confidence == 'exact' first, then start offset asc)`;
    - cap at 50 entries — a warning is emitted into pipeline.warnings if
      the cap fires (`link_candidates_truncated: <N>`).

Module API
----------
    populate_link_candidates(body, vault_root, *, run_ner) -> LinkResult

`LinkResult` carries:
    - `candidates`: list[dict] (frontmatter shape per §12.1)
    - `language`: str — ISO 639-1 code ('pt'/'en'/'unknown')
    - `warnings`: list[str] — non-fatal issues
    - `exact_count`, `ner_count`: int — for the ingestion log

Failure modes
-------------
- Missing catalog → `[]` + warning `link_candidates_skipped:
  catalog_unavailable`. No frontmatter field.
- spaCy not installed / no model present → exact-pass results only +
  warning `ner_skipped: <reason>`. Frontmatter still written.
- Any unexpected exception → return what we have so far, log a warning,
  never raise to the caller.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Constants (contract §12.2) ─────────────────────────────────────────────
MAX_CANDIDATES = 50  # §12.2 cap per source
CATALOG_REL = "99 Workspace/_entity_catalog.json"

# spaCy entity types we keep on the NER pass. PERSON / ORG / LOC / GPE
# matches what catalog seeds today; FAC / WORK_OF_ART / EVENT etc. are
# explicitly excluded (too noisy).
_NER_KEEP_LABELS = frozenset({"PERSON", "ORG", "LOC", "GPE"})

# Lightweight language-detection fallback — used only if `langdetect` is
# absent. Tokens taken from the most-common 30 PT and EN stopwords. A
# string is "pt" if PT hits clearly exceed EN hits and vice versa;
# otherwise "unknown".
_PT_STOPWORDS = frozenset({
    "de", "a", "o", "e", "do", "da", "em", "para", "com", "que",
    "os", "as", "um", "uma", "por", "no", "na", "se", "não", "mais",
    "ao", "dos", "das", "como", "mas", "foi", "ser", "ter", "à", "ou",
    "está", "são", "este", "esta", "isso", "também", "já", "muito",
})

_EN_STOPWORDS = frozenset({
    "the", "of", "and", "to", "a", "in", "for", "is", "on", "that",
    "by", "this", "with", "i", "you", "it", "not", "or", "be", "are",
    "from", "at", "as", "your", "have", "more", "will", "an", "but",
    "we", "they", "which", "their", "would", "there",
})

_WORD_RE = re.compile(r"\w+", re.UNICODE)


# ── Result dataclass ───────────────────────────────────────────────────────

@dataclass
class LinkResult:
    """Outcome of populate_link_candidates()."""

    candidates:   list[dict] = field(default_factory=list)
    language:     str = "unknown"
    warnings:     list[str] = field(default_factory=list)
    exact_count:  int = 0
    ner_count:    int = 0
    catalog_used: bool = False


# ── Public entry point ─────────────────────────────────────────────────────

def populate_link_candidates(
    body: str,
    vault_root: Path,
    *,
    run_ner: bool = True,
) -> LinkResult:
    """Run language detection + AL-03 matcher + (optional) spaCy NER over `body`.

    Always returns a LinkResult — never raises.

    Parameters
    ----------
    body : str
        The extracted markdown body. May be empty.
    vault_root : Path
        Path to the vault root (used to locate the entity catalog).
    run_ner : bool
        If False, skip the spaCy NER pass entirely. Default True. Tests
        set this False to avoid loading large models.
    """
    result = LinkResult()
    if not body:
        return result

    # 1. Language detection
    try:
        result.language = _detect_language(body)
    except Exception as exc:  # pragma: no cover — paranoia
        result.warnings.append(f"language_detection_failed: {exc}")
        result.language = "unknown"

    # 2. Catalog-driven exact matching (AL-03)
    exact_candidates: list[dict] = []
    exact_surfaces: set[str] = set()
    catalog_path = vault_root / CATALOG_REL
    try:
        exact_candidates, exact_surfaces = _exact_pass(body, catalog_path)
        result.catalog_used = True
        result.exact_count = len(exact_candidates)
    except FileNotFoundError:
        result.warnings.append("link_candidates_skipped: catalog_unavailable")
        # No catalog → no exact pass; NER may still run.
    except ImportError as exc:
        # pyahocorasick missing — graceful skip
        result.warnings.append(f"link_candidates_skipped: matcher_unavailable: {exc}")
    except Exception as exc:
        result.warnings.append(f"link_candidates_exact_failed: {exc}")

    # 3. spaCy NER for off-catalog entities (best effort)
    ner_candidates: list[dict] = []
    if run_ner:
        try:
            ner_candidates = _ner_pass(
                body, language=result.language, skip_surfaces=exact_surfaces,
            )
            result.ner_count = len(ner_candidates)
        except ImportError as exc:
            result.warnings.append(f"ner_skipped: spacy_unavailable: {exc}")
        except OSError as exc:
            # spaCy raises OSError when the model itself isn't downloaded.
            result.warnings.append(f"ner_skipped: model_unavailable: {exc}")
        except Exception as exc:
            result.warnings.append(f"ner_failed: {exc}")

    # 4. Merge → dedupe → sort → cap
    merged = exact_candidates + ner_candidates
    deduped = _dedupe(merged)
    sorted_ = sorted(
        deduped,
        key=lambda c: (0 if c["confidence"] == "exact" else 1, c["offsets"][0]),
    )

    if len(sorted_) > MAX_CANDIDATES:
        truncated = len(sorted_) - MAX_CANDIDATES
        sorted_ = sorted_[:MAX_CANDIDATES]
        result.warnings.append(f"link_candidates_truncated: {truncated}")

    result.candidates = sorted_
    return result


# ── Language detection ─────────────────────────────────────────────────────

def _detect_language(text: str) -> str:
    """Best-effort PT/EN/unknown detection.

    Prefers `langdetect` if installed (it's not in requirements.txt but
    safe to opportunistically use). Otherwise falls back to stopword
    frequency. Returns ISO 639-1 codes; defaults to 'unknown' on tie or
    insufficient signal.
    """
    # Try langdetect first
    try:
        from langdetect import detect, DetectorFactory   # type: ignore

        DetectorFactory.seed = 0  # deterministic
        code = detect(text)
        if code in ("pt", "en"):
            return code
        return "unknown"
    except ImportError:
        pass
    except Exception:
        # any langdetect failure → fall through to heuristic
        pass

    # Stopword-frequency fallback
    tokens = [t.lower() for t in _WORD_RE.findall(text)]
    if not tokens:
        return "unknown"
    pt_hits = sum(1 for t in tokens if t in _PT_STOPWORDS)
    en_hits = sum(1 for t in tokens if t in _EN_STOPWORDS)
    if max(pt_hits, en_hits) < 3:
        return "unknown"
    if pt_hits > en_hits * 1.3:
        return "pt"
    if en_hits > pt_hits * 1.3:
        return "en"
    return "unknown"


# ── Exact pass via AL-03 matcher ───────────────────────────────────────────

def _exact_pass(body: str, catalog_path: Path) -> tuple[list[dict], set[str]]:
    """Run the AL-03 LinkMatcher and shape the output into §12.1 dicts.

    Returns `(candidates, surfaces)` where `surfaces` is the set of
    matched_string values (used by the NER pass to suppress duplicates).
    Raises FileNotFoundError if the catalog is missing.
    """
    # Add 90 System/ to sys.path so we can import _link_matcher.
    # ingest.py already does this for some scripts (enrich_links) — we
    # do it again here defensively because handlers may be imported
    # in isolation by tests.
    system_dir = Path(__file__).resolve().parent.parent.parent  # handlers/ → _ingestion_pipeline/ → 90 System/
    if str(system_dir) not in sys.path:
        sys.path.insert(0, str(system_dir))

    from _link_matcher import LinkMatcher   # noqa: E402

    matcher = LinkMatcher.from_catalog(catalog_path)
    matches = matcher.match(body)

    candidates: list[dict] = []
    surfaces: set[str] = set()
    for m in matches:
        wikilink = _wikilink_for(m.entity_id)
        candidates.append({
            "entity_id":         m.entity_id,
            "matched_string":    m.matched_string,
            "confidence":        "exact",
            "offsets":           [m.start, m.end],
            "proposed_wikilink": wikilink,
        })
        surfaces.add(m.matched_string)
    return candidates, surfaces


def _wikilink_for(entity_id: str) -> str:
    """Convert a catalog entity_id ('10 People/Susana Zumel Vara') into the
    Obsidian wikilink form ('[[Susana Zumel Vara]]') used in the proposed
    wikilink slot. Per §12.1 we use the basename of the path so the
    wikilink resolves the way Obsidian / Bases expects it.
    """
    basename = entity_id.split("/", 1)[-1] if "/" in entity_id else entity_id
    return f"[[{basename}]]"


# ── spaCy NER pass ─────────────────────────────────────────────────────────

def _ner_pass(
    body: str,
    *,
    language: str,
    skip_surfaces: set[str],
) -> list[dict]:
    """Best-effort spaCy NER for entities not in the catalog.

    Loads the model whose language matches the detected body language,
    falling back to a small generic NER model if neither large one is
    installed. Surfaces already in `skip_surfaces` are dropped (the
    exact pass already covered them).

    Returns a list of §12.1 candidate dicts with `confidence: 'ner'`.
    """
    import spacy  # ImportError handled by caller

    # Model preference per language.
    model_names: list[str]
    if language == "pt":
        model_names = ["pt_core_news_lg", "pt_core_news_md", "pt_core_news_sm"]
    elif language == "en":
        model_names = ["en_core_web_lg", "en_core_web_md", "en_core_web_sm"]
    else:
        # mixed / unknown — try both, large first
        model_names = [
            "pt_core_news_lg", "en_core_web_lg",
            "pt_core_news_md", "en_core_web_md",
            "xx_ent_wiki_sm",   # multilingual fallback
        ]

    nlp = None
    last_err: Optional[Exception] = None
    for name in model_names:
        try:
            nlp = spacy.load(name)
            break
        except OSError as exc:
            last_err = exc
            continue
    if nlp is None:
        # Re-raise the last OSError so caller logs `model_unavailable`.
        raise (last_err or OSError("no spaCy NER model installed"))

    doc = nlp(body)
    candidates: list[dict] = []
    for ent in doc.ents:
        if ent.label_ not in _NER_KEEP_LABELS:
            continue
        surface = ent.text.strip()
        if not surface:
            continue
        if surface in skip_surfaces:
            continue
        candidates.append({
            "entity_id":         f"ner/{surface}",
            "matched_string":    surface,
            "confidence":        "ner",
            "offsets":           [ent.start_char, ent.end_char],
            "proposed_wikilink": f"[[{surface}]]",
        })
    return candidates


# ── Dedupe helper ──────────────────────────────────────────────────────────

def _dedupe(candidates: list[dict]) -> list[dict]:
    """Keep first occurrence of each `(entity_id, matched_string)` pair.

    "First" is the candidate with the smallest start offset.
    """
    by_key: dict[tuple[str, str], dict] = {}
    for c in candidates:
        key = (c["entity_id"], c["matched_string"])
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = c
            continue
        # Keep the smaller-start one
        if c["offsets"][0] < existing["offsets"][0]:
            by_key[key] = c
    return list(by_key.values())
