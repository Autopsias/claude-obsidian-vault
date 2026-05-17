#!/usr/bin/env python3
"""
populate-voice-profile.py — Corpus → populated voice-profile.md.

Walks a directory of user-authored prose (.md / .txt), computes corpus
statistics relevant to voice calibration (sentence length, em-dash density,
common openers, common sign-offs, etc.), and emits a populated voice
profile with corpus-derived suggestions filling the [POPULATE — ...]
sections of the template.

Stdlib-only. No NLP dependencies. Designed to surface stats and patterns;
the user provides judgment on what counts as a rule.

Usage:
    python3 populate-voice-profile.py \\
        --corpus /path/to/_voice_corpus/ \\
        --template ../templates/voice-profile-template.md \\
        --output /path/to/_voice_profile.md \\
        --user-name "Your Name"

Optional flags:
    --update              Refresh stats but preserve hand-edited rules
                          (only rewrites the [POPULATE — corpus stats]
                          block in §1 frontmatter calibration base).
    --min-words 5000      Floor on corpus size (warns if below).
    --languages en,pt,es  Languages to analyse separately.
"""
from __future__ import annotations

import argparse
import collections
import re
import sys
from datetime import datetime
from pathlib import Path


# ---------- Corpus reading ----------------------------------------------

SUPPORTED_EXTS = {".md", ".txt"}


def read_corpus(corpus_dir: Path) -> list[tuple[Path, str]]:
    """Return list of (path, text) for every supported file in the dir."""
    docs: list[tuple[Path, str]] = []
    for p in sorted(corpus_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            # Strip frontmatter if present
            text = p.read_text(encoding="utf-8", errors="replace")
            if text.startswith("---\n"):
                end = text.find("\n---\n", 4)
                if end > 0:
                    text = text[end + 5 :]
            docs.append((p, text))
    return docs


# ---------- Statistics --------------------------------------------------

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-Þ])")
WORD_SPLIT = re.compile(r"\b\w+\b", re.UNICODE)
EM_DASH = re.compile(r"[—–]")
BULLET_LINE = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)


def sentences(text: str) -> list[str]:
    """Crude sentence segmentation."""
    raw = SENTENCE_SPLIT.split(text)
    return [s.strip() for s in raw if s.strip()]


def words(text: str) -> list[str]:
    return WORD_SPLIT.findall(text)


def compute_stats(docs: list[tuple[Path, str]]) -> dict:
    """Run corpus-wide statistics."""
    total_text = "\n\n".join(t for _, t in docs)

    all_sentences = sentences(total_text)
    all_words = words(total_text)

    sentence_word_counts = [len(words(s)) for s in all_sentences]
    avg_sentence = sum(sentence_word_counts) / len(sentence_word_counts) if sentence_word_counts else 0
    median_sentence = sorted(sentence_word_counts)[len(sentence_word_counts) // 2] if sentence_word_counts else 0
    p90_sentence = sorted(sentence_word_counts)[int(len(sentence_word_counts) * 0.9)] if sentence_word_counts else 0

    em_dash_count = len(EM_DASH.findall(total_text))
    em_dash_per_1k = (em_dash_count / max(len(all_words), 1)) * 1000

    bullet_lines = len(BULLET_LINE.findall(total_text))

    stats = {
        "doc_count": len(docs),
        "total_words": len(all_words),
        "total_sentences": len(all_sentences),
        "avg_sentence_words": avg_sentence,
        "median_sentence_words": median_sentence,
        "p90_sentence_words": p90_sentence,
        "em_dash_count": em_dash_count,
        "em_dash_per_1k_words": em_dash_per_1k,
        "bullet_lines": bullet_lines,
        "earliest_doc": min((p.stat().st_mtime for p, _ in docs), default=0),
        "latest_doc": max((p.stat().st_mtime for p, _ in docs), default=0),
    }
    return stats


# ---------- Pattern extraction -----------------------------------------

OPENER_LEN_RANGE = (4, 12)  # words in a typical opener
CLOSER_LEN_RANGE = (1, 6)


def extract_openers(docs: list[tuple[Path, str]], top: int = 10) -> list[tuple[str, int]]:
    """First sentence of each document — surface most common patterns."""
    first_lines: collections.Counter = collections.Counter()
    for _, text in docs:
        lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("#")]
        if not lines:
            continue
        first = lines[0]
        # First sentence of the first line
        sent = sentences(first)
        if not sent:
            continue
        # First 4-6 words as the "opener key"
        opener_words = words(sent[0])[:5]
        if len(opener_words) >= 2:
            key = " ".join(opener_words)
            first_lines[key] += 1
    return first_lines.most_common(top)


def extract_closers(docs: list[tuple[Path, str]], top: int = 10) -> list[tuple[str, int]]:
    """Last short line of each document — typically the sign-off."""
    closers: collections.Counter = collections.Counter()
    sign_off_patterns = [
        r"^(best|cheers|thanks|regards|atentamente|cumprimentos|obg|abraço|saluda|saludos)",
    ]
    pattern = re.compile("|".join(sign_off_patterns), re.IGNORECASE)
    for _, text in docs:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in reversed(lines[-5:]):
            if pattern.match(line) and len(words(line)) <= CLOSER_LEN_RANGE[1]:
                closers[line] += 1
                break
    return closers.most_common(top)


def extract_phrase_ngrams(
    docs: list[tuple[Path, str]], n: int = 3, top: int = 20
) -> list[tuple[str, int]]:
    """Top n-grams excluding pure stopwords."""
    stop = {
        "the", "a", "an", "to", "of", "and", "in", "is", "it", "be",
        "that", "for", "on", "with", "as", "this", "are", "we", "i", "you",
        "by", "from", "or", "but", "if", "at", "have", "has", "will",
    }
    text = " ".join(t.lower() for _, t in docs)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    toks = text.split()
    ngrams: collections.Counter = collections.Counter()
    for i in range(len(toks) - n + 1):
        gram = toks[i : i + n]
        if all(g in stop for g in gram):
            continue
        ngrams[" ".join(gram)] += 1
    return ngrams.most_common(top)


def detect_ai_tells(docs: list[tuple[Path, str]]) -> dict[str, int]:
    """Count known AI-tell phrases — to surface as anti-patterns IF present."""
    ai_tell_phrases = [
        "warm regards",
        "I very much value",
        "thoughtful and professional",
        "looking ahead, I remain",
        "I'm excited to",
        "thrilled to announce",
        "I'm reaching out to",
        "delve into",
        "ensure that",
        "leverage our",
    ]
    counts: dict[str, int] = {}
    full_text = " ".join(t.lower() for _, t in docs)
    for phrase in ai_tell_phrases:
        c = full_text.count(phrase.lower())
        if c > 0:
            counts[phrase] = c
    return counts


# ---------- Report generation ------------------------------------------

def render_report(
    user_name: str,
    stats: dict,
    openers: list[tuple[str, int]],
    closers: list[tuple[str, int]],
    ngrams: list[tuple[str, int]],
    ai_tells: dict[str, int],
) -> str:
    earliest = datetime.fromtimestamp(stats["earliest_doc"]).strftime("%Y-%m")
    latest = datetime.fromtimestamp(stats["latest_doc"]).strftime("%Y-%m")
    today = datetime.now().strftime("%Y-%m-%d")

    lines: list[str] = []
    lines.append(f"# Voice profile suggestions for {user_name}")
    lines.append(f"\n*Generated {today} from corpus stats. Use as a starting point — apply judgment.*\n")
    lines.append("## Corpus summary\n")
    lines.append(f"- **Docs:** {stats['doc_count']}")
    lines.append(f"- **Total words:** {stats['total_words']:,}")
    lines.append(f"- **Total sentences:** {stats['total_sentences']:,}")
    lines.append(f"- **Date span:** {earliest} → {latest}")
    lines.append("")
    lines.append("## Sentence length\n")
    lines.append(f"- Avg sentence: **{stats['avg_sentence_words']:.1f} words**")
    lines.append(f"- Median: {stats['median_sentence_words']} words")
    lines.append(f"- P90 (long-sentence ceiling): {stats['p90_sentence_words']} words")
    lines.append("")
    lines.append(f"→ Suggested rule (§2 / §4 of profile): 'Avg sentence length ~{int(stats['avg_sentence_words'])} words; cap at ~{stats['p90_sentence_words']} words.'\n")

    lines.append("## Em-dash density\n")
    lines.append(f"- Em-dashes: **{stats['em_dash_count']} total** = {stats['em_dash_per_1k_words']:.2f} per 1000 words")
    if stats["em_dash_per_1k_words"] > 5:
        lines.append("→ High em-dash density. Suggested rule: 'em-dashes acceptable, no specific cap'.")
    elif stats["em_dash_per_1k_words"] > 1:
        lines.append(f"→ Moderate em-dash density. Suggested rule: 'em-dashes ≤4 per long email'.")
    else:
        lines.append("→ Low em-dash density. Suggested rule: 'em-dashes ≤1 per email; above is an AI-tell'.")
    lines.append("")

    lines.append("## Bullet usage\n")
    lines.append(f"- Bullet lines across corpus: **{stats['bullet_lines']}**")
    bullet_ratio = stats["bullet_lines"] / max(stats["doc_count"], 1)
    lines.append(f"- Bullets per document avg: {bullet_ratio:.1f}")
    if bullet_ratio > 5:
        lines.append("→ Liberal bullet use. Suggested rule: 'bullets liberal in long emails and memos'.")
    elif bullet_ratio > 1:
        lines.append("→ Moderate bullet use. Suggested rule: 'bullets in memos, sparingly in emails'.")
    else:
        lines.append("→ Light bullet use. Suggested rule: 'bullets only in memos; never in emails'.")
    lines.append("")

    lines.append("## Most common openers (first 5 words of doc-opening sentence)\n")
    if openers:
        for opener, count in openers:
            lines.append(f"- `{opener}` — {count}×")
    else:
        lines.append("(none detected)")
    lines.append("\n→ Populate §3 with high-frequency openers and audience matrix.\n")

    lines.append("## Sign-offs detected\n")
    if closers:
        for closer, count in closers:
            lines.append(f"- `{closer}` — {count}×")
    else:
        lines.append("(none detected — corpus may not include sign-off lines)")
    lines.append("\n→ Populate §2.2 (sign-off repertoire) from this list.\n")

    lines.append("## Common 3-grams (excluding pure stopwords)\n")
    for gram, count in ngrams[:15]:
        lines.append(f"- `{gram}` — {count}×")
    lines.append("\n→ Inspect for rhetorical pivots (§4) and recurring phrase patterns.\n")

    lines.append("## AI-tell phrases detected (anti-patterns)\n")
    if ai_tells:
        lines.append("⚠ The following AI-tell phrases appear in the corpus:")
        for phrase, count in sorted(ai_tells.items(), key=lambda kv: -kv[1]):
            lines.append(f"- `{phrase}` — {count}× (review whether genuine voice or AI-assisted draft contaminated the corpus)")
    else:
        lines.append("✓ No common AI-tell phrases detected in corpus. Profile §6 can confidently flag these as anti-patterns.")
    lines.append("")

    lines.append("---\n")
    lines.append("## Next steps\n")
    lines.append("1. Open the template (`voice-profile-template.md`).\n")
    lines.append("2. Use the stats above to fill the `[POPULATE — ...]` sections with judgment.\n")
    lines.append("3. The script is a suggestion engine, not a profile generator — your editorial judgment is the load-bearing step.\n")
    lines.append("4. After populating, run a roundtrip test: pick a 200-word sample from the corpus, ask Claude to draft something similar, compare.\n")
    lines.append("5. Commit the populated profile to `_voice_profile.md` and the discipline rule to `.claude/rules/voice-discipline.md`.\n")

    return "\n".join(lines)


# ---------- CLI --------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True, help="path to _voice_corpus/")
    ap.add_argument("--template", default=None, help="path to voice-profile-template.md (optional; for --copy-template mode)")
    ap.add_argument("--output", required=True, help="output path for the suggestion report")
    ap.add_argument("--user-name", required=True, help="user's name (substitutes {{USER_NAME}})")
    ap.add_argument("--min-words", type=int, default=5000, help="minimum corpus size before warnings")
    ap.add_argument("--copy-template", action="store_true", help="also copy the template to <output>.template.md so the user can edit alongside the suggestions")
    args = ap.parse_args()

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        print(f"[FAIL] corpus path is not a directory: {corpus}", file=sys.stderr)
        return 1

    docs = read_corpus(corpus)
    if not docs:
        print(f"[FAIL] no .md or .txt files found in {corpus}", file=sys.stderr)
        return 1

    stats = compute_stats(docs)
    if stats["total_words"] < args.min_words:
        print(
            f"[WARN] corpus has {stats['total_words']:,} words — below {args.min_words} floor. "
            "Suggestions will be less reliable. Add more authored prose.",
            file=sys.stderr,
        )

    openers = extract_openers(docs)
    closers = extract_closers(docs)
    ngrams = extract_phrase_ngrams(docs, n=3)
    ai_tells = detect_ai_tells(docs)

    report = render_report(
        user_name=args.user_name,
        stats=stats,
        openers=openers,
        closers=closers,
        ngrams=ngrams,
        ai_tells=ai_tells,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")

    if args.copy_template and args.template:
        tmpl_path = Path(args.template)
        if tmpl_path.exists():
            tmpl_text = tmpl_path.read_text(encoding="utf-8")
            tmpl_text = tmpl_text.replace("{{USER_NAME}}", args.user_name)
            tmpl_text = tmpl_text.replace(
                "{{DATE}}", datetime.now().strftime("%Y-%m-%d")
            )
            out_tmpl = out.with_suffix(".template.md")
            out_tmpl.write_text(tmpl_text, encoding="utf-8")
            print(f"[OK] template copy written to {out_tmpl}")

    print(f"[OK] suggestion report written to {out}")
    print(
        f"[OK] corpus: {stats['doc_count']} docs / "
        f"{stats['total_words']:,} words / "
        f"avg sentence {stats['avg_sentence_words']:.1f} words"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
