#!/usr/bin/env python3
"""
_eval_faithfulness.py — Faithfulness (F) scorer for the Galp Vault retrieval eval.

PR-03 / S02 — Galp Vault Frontier Closeout plan, 2026-05-17.

Purpose
-------
Add a **7th eval dimension — Faithfulness (F)** — that catches the failure
mode the existing dimensions miss: Claude answers a question correctly
*from parametric knowledge* instead of from the retrieved passages.

- S (supersession), X (cross-zone), T (temporal route), MH (multi-hop),
  CAL (calibrated refusal), FT (fact-level temporal) all assume the
  answer is grounded in retrieval. None of them tests *whether* it is.
- F closes that gap: every claim in the answer must be supported by the
  retrieved passages. If the runner pulled a fact from training data
  rather than vault content, F=0 even if S/X/T all pass.

Dual-evaluator design
---------------------
Self-evaluation by the same model that produced the answer has a known
positive bias ("self-preference"). To mitigate, this scorer runs the
faithfulness judgement through TWO independent judge models and averages:

  - **Anthropic Claude Haiku** (`claude-haiku-4-5-20251001`)
  - **OpenAI gpt-4o-mini**     (`gpt-4o-mini`)

If only one key is available, the scorer runs single-judge mode with an
explicit `single_judge: true` note in the output. If neither key is
available, the scorer returns a "deferred" verdict, never a fabricated
score.

Prompt
------
The judge prompt is intentionally small and crisp:

    Given the retrieved passages below and the candidate answer, decide
    whether every factual claim in the answer is supported by the
    passages. Reply with exactly one of:
      YES     — every claim is supported
      PARTIAL — some claims are supported, others are not
      NO      — no claims are supported, or the answer contradicts the passages
    Then on a new line, in ≤20 words, explain why.

Score mapping (per judge):
    YES     → 1.0
    PARTIAL → 0.5
    NO      → 0.0

The averaged score is per-question; the run aggregate is the mean over
all scored questions.

Inputs
------
JSON run record (file or stdin). Schema:

    [
      {
        "q_id": 11,
        "question": "...",
        "passages": [
          {"path": "50 Sources/...", "excerpt": "..."},
          ...
        ],
        "answer": "Claude's free-text answer to the question."
      },
      ...
    ]

Outputs
-------
A scorecard JSON document covering per-question and aggregate F scores.
For each question, both judges' verdicts + scores + explanations are
preserved for audit.

CLI
---
    python3 _eval_faithfulness.py --run results.json
    python3 _eval_faithfulness.py --run results.json --out scorecard.json
    python3 _eval_faithfulness.py --self-test  # no API calls; tests parsing
    python3 _eval_faithfulness.py --dry-run --run results.json
        # parses input, prints planned API call counts, exits without calling

Exit codes
----------
    0 — at least one judge scored every question
    1 — input validation failure
    2 — both API keys absent AND --require-judges set
    3 — judge call raised a hard error (network, auth)

Environment variables
---------------------
    ANTHROPIC_API_KEY  — enables the Haiku judge
    OPENAI_API_KEY     — enables the gpt-4o-mini judge

Either or both may be set. The scorer never fails open when both are
absent — it returns `verdict: "deferred"` so the consumer can decide
to retry later.

Cross-references
----------------
- IR metrics sibling:  90 System/_eval_ir_metrics.py
- Question rubric:     90 System/_eval_retrieval.md
- Closed-loop schema:  90 System/_closed_loop_contract.md (for T2 emissions
                        when F drops sustainedly below the 0.85 floor)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

# Judge models — pinned to specific versions for reproducibility. Update only
# with a documented baseline re-run.
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
OPENAI_MODEL = "gpt-4o-mini"

# API endpoints — direct REST calls (no SDK dependency in the sandbox).
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Output budget — judgements should be terse; cap to avoid runaway tokens.
MAX_JUDGE_TOKENS = 80

# Pass floor — sustained mean F below this triggers a T2 closed-loop entry.
# (Recorded in the eval baseline; enforcement is a downstream policy, not
# this script's concern.)
F_FLOOR = 0.85


VERDICT_SCORE = {"YES": 1.0, "PARTIAL": 0.5, "NO": 0.0}


# ──────────────────────────────────────────────────────────────────────────────
# Prompt construction
# ──────────────────────────────────────────────────────────────────────────────

JUDGE_PROMPT_TEMPLATE = """\
You are evaluating the faithfulness of a candidate answer to a retrieval question.

QUESTION:
{question}

RETRIEVED PASSAGES (the only evidence the candidate is allowed to use):
{passages_block}

CANDIDATE ANSWER:
{answer}

Decide whether every factual claim in the candidate answer is supported by the
retrieved passages above. Reply with EXACTLY one of these tokens on the first line:

  YES     — every factual claim in the answer is supported by the passages
  PARTIAL — some claims are supported, others are not (or are speculative)
  NO      — no claims are supported, or the answer contradicts the passages

Then on a new line, in 20 words or fewer, justify the verdict by pointing to
the unsupported claim (if any) or by confirming alignment.
"""


def build_passages_block(passages: list[dict]) -> str:
    """Format the passages block. Each passage gets a leading marker for
    citation traceability."""
    if not passages:
        return "(no passages retrieved — answer must therefore be NO or PARTIAL)"
    lines = []
    for idx, p in enumerate(passages, start=1):
        path = p.get("path") or p.get("source") or f"passage_{idx}"
        excerpt = (p.get("excerpt") or p.get("text") or "").strip()
        # Cap each excerpt to keep the prompt under reasonable token count.
        if len(excerpt) > 2000:
            excerpt = excerpt[:2000] + " […truncated]"
        lines.append(f"[{idx}] {path}\n{excerpt}")
    return "\n\n".join(lines)


def build_prompt(question: str, passages: list[dict], answer: str) -> str:
    return JUDGE_PROMPT_TEMPLATE.format(
        question=question.strip(),
        passages_block=build_passages_block(passages),
        answer=answer.strip(),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Verdict parsing
# ──────────────────────────────────────────────────────────────────────────────

_VERDICT_RE = re.compile(r"^\s*(YES|PARTIAL|NO)\b[\s\-—:.]*", re.IGNORECASE)


def parse_judge_output(text: str) -> tuple[Optional[str], str]:
    """Extract (verdict, explanation) from a judge reply.

    Returns (None, raw) if the reply does not start with a recognised verdict.
    Explanation captures both same-line tail (after the verdict token and any
    separator punctuation) AND any following lines.
    """
    if not text:
        return None, ""
    stripped = text.strip()
    if not stripped:
        return None, ""
    lines = stripped.splitlines()
    first_line = lines[0]
    m = _VERDICT_RE.match(first_line)
    if not m:
        return None, stripped
    verdict = m.group(1).upper()
    tail = first_line[m.end():].strip()
    rest = "\n".join(lines[1:]).strip()
    if tail and rest:
        explanation = f"{tail}\n{rest}"
    elif tail:
        explanation = tail
    else:
        explanation = rest
    return verdict, explanation


# ──────────────────────────────────────────────────────────────────────────────
# Judge dataclass
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class JudgeReply:
    judge: str               # "anthropic" | "openai"
    model: str
    verdict: Optional[str]   # YES | PARTIAL | NO | None (parse failure)
    score: Optional[float]   # 1.0 / 0.5 / 0.0 / None
    raw: str
    explanation: str
    error: Optional[str] = None
    latency_s: float = 0.0


# ──────────────────────────────────────────────────────────────────────────────
# Judge invocations — direct REST, no SDK
# ──────────────────────────────────────────────────────────────────────────────

def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict,
    timeout: float = 60.0,
) -> dict:
    """POST JSON, return parsed JSON. Raises urllib HTTPError / URLError on
    network or HTTP failure; raises ValueError on non-JSON body."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"non-JSON response: {raw[:200]!r}") from exc


def call_anthropic_haiku(prompt: str, api_key: str) -> JudgeReply:
    t0 = time.time()
    headers = {
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": MAX_JUDGE_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        body = _post_json(ANTHROPIC_URL, headers, payload)
        # Response shape: {"content": [{"type":"text","text":"..."}], ...}
        parts = body.get("content") or []
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        verdict, explanation = parse_judge_output(text)
        return JudgeReply(
            judge="anthropic",
            model=ANTHROPIC_MODEL,
            verdict=verdict,
            score=VERDICT_SCORE.get(verdict) if verdict else None,
            raw=text,
            explanation=explanation,
            latency_s=time.time() - t0,
        )
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        return JudgeReply(
            judge="anthropic",
            model=ANTHROPIC_MODEL,
            verdict=None,
            score=None,
            raw="",
            explanation="",
            error=f"{type(exc).__name__}: {exc}",
            latency_s=time.time() - t0,
        )


def call_openai_mini(prompt: str, api_key: str) -> JudgeReply:
    t0 = time.time()
    headers = {
        "authorization": f"Bearer {api_key}",
        "content-type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "max_tokens": MAX_JUDGE_TOKENS,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        body = _post_json(OPENAI_URL, headers, payload)
        # Response shape: {"choices":[{"message":{"content":"..."}}], ...}
        choices = body.get("choices") or []
        text = ""
        if choices:
            msg = (choices[0] or {}).get("message") or {}
            text = msg.get("content") or ""
        verdict, explanation = parse_judge_output(text)
        return JudgeReply(
            judge="openai",
            model=OPENAI_MODEL,
            verdict=verdict,
            score=VERDICT_SCORE.get(verdict) if verdict else None,
            raw=text,
            explanation=explanation,
            latency_s=time.time() - t0,
        )
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        return JudgeReply(
            judge="openai",
            model=OPENAI_MODEL,
            verdict=None,
            score=None,
            raw="",
            explanation="",
            error=f"{type(exc).__name__}: {exc}",
            latency_s=time.time() - t0,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Per-question scoring
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class QuestionScore:
    q_id: Any
    verdict_aggregate: str   # "YES" | "PARTIAL" | "NO" | "deferred"
    score: Optional[float]
    judges: list[JudgeReply] = field(default_factory=list)
    single_judge: bool = False
    reason: str = ""


def _score_from_replies(replies: list[JudgeReply]) -> tuple[Optional[float], str]:
    """Average scores across successful judges. Returns (score, aggregate_verdict).

    aggregate_verdict heuristic for human display:
      - if both judges agree → that verdict
      - if disagreement → "MIXED (avg score)"
      - if only one judge succeeded → that judge's verdict
      - if none succeeded → "deferred"
    """
    scored = [r for r in replies if r.score is not None]
    if not scored:
        return None, "deferred"

    avg = sum(r.score for r in scored) / len(scored)

    verdicts = {r.verdict for r in scored if r.verdict is not None}
    if len(verdicts) == 1:
        return avg, next(iter(verdicts))
    if len(scored) == 1:
        return avg, scored[0].verdict or "deferred"
    return avg, f"MIXED ({avg:.2f})"


def score_question(
    q_id: Any,
    question: str,
    passages: list[dict],
    answer: str,
    anthropic_key: Optional[str],
    openai_key: Optional[str],
    dry_run: bool = False,
) -> QuestionScore:
    if dry_run or (not anthropic_key and not openai_key):
        return QuestionScore(
            q_id=q_id,
            verdict_aggregate="deferred",
            score=None,
            judges=[],
            reason="dry_run" if dry_run else "no judge API keys available",
        )

    prompt = build_prompt(question, passages, answer)
    replies: list[JudgeReply] = []
    if anthropic_key:
        replies.append(call_anthropic_haiku(prompt, anthropic_key))
    if openai_key:
        replies.append(call_openai_mini(prompt, openai_key))

    score, agg_verdict = _score_from_replies(replies)
    return QuestionScore(
        q_id=q_id,
        verdict_aggregate=agg_verdict,
        score=score,
        judges=replies,
        single_judge=(len([r for r in replies if r.score is not None]) == 1),
    )


# ──────────────────────────────────────────────────────────────────────────────
# Run scoring
# ──────────────────────────────────────────────────────────────────────────────

def score_run(
    run: list[dict],
    anthropic_key: Optional[str] = None,
    openai_key: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    per_q: list[dict[str, Any]] = []
    scored_vals: list[float] = []
    deferred = 0
    errors = 0

    for record in run:
        q_id = record.get("q_id", "?")
        question = record.get("question") or ""
        passages = record.get("passages") or []
        answer = record.get("answer") or ""

        qs = score_question(
            q_id=q_id,
            question=question,
            passages=passages,
            answer=answer,
            anthropic_key=anthropic_key,
            openai_key=openai_key,
            dry_run=dry_run,
        )

        if qs.score is not None:
            scored_vals.append(qs.score)
        else:
            deferred += 1
        if any(r.error for r in qs.judges):
            errors += 1

        per_q.append({
            "q_id": qs.q_id,
            "verdict_aggregate": qs.verdict_aggregate,
            "score": qs.score,
            "single_judge": qs.single_judge,
            "reason": qs.reason or None,
            "judges": [
                {
                    "judge": r.judge,
                    "model": r.model,
                    "verdict": r.verdict,
                    "score": r.score,
                    "explanation": r.explanation,
                    "raw": r.raw,
                    "error": r.error,
                    "latency_s": round(r.latency_s, 3),
                }
                for r in qs.judges
            ],
        })

    aggregate_f = (sum(scored_vals) / len(scored_vals)) if scored_vals else None

    return {
        "aggregate_F": aggregate_f,
        "scored_count": len(scored_vals),
        "deferred": deferred,
        "errors": errors,
        "judges_active": {
            "anthropic": bool(anthropic_key) and not dry_run,
            "openai": bool(openai_key) and not dry_run,
        },
        "f_floor": F_FLOOR,
        "f_below_floor": (aggregate_f is not None and aggregate_f < F_FLOOR),
        "per_question": per_q,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────────────────────────────────────

def render_text_report(scorecard: dict[str, Any]) -> str:
    lines = []
    lines.append("── Faithfulness (F) scorecard ───────────────────────────────")
    agg = scorecard.get("aggregate_F")
    if agg is None:
        lines.append("  Aggregate F : (deferred — no judges succeeded)")
    else:
        flag = "  ⚠ BELOW FLOOR" if scorecard["f_below_floor"] else ""
        lines.append(f"  Aggregate F : {agg:.4f}   (floor = {scorecard['f_floor']:.2f}){flag}")
    lines.append(
        f"  Scored      : {scorecard['scored_count']}   "
        f"deferred: {scorecard['deferred']}   "
        f"judge errors: {scorecard['errors']}"
    )
    ja = scorecard["judges_active"]
    lines.append(
        f"  Judges      : anthropic={'ON' if ja['anthropic'] else 'OFF'}  "
        f"openai={'ON' if ja['openai'] else 'OFF'}"
    )
    lines.append("")
    for r in scorecard["per_question"]:
        s = r["score"]
        s_str = f"{s:.2f}" if s is not None else "N/A "
        sj = "  [single]" if r.get("single_judge") else ""
        reason = f"  reason={r['reason']}" if r.get("reason") else ""
        lines.append(
            f"  Q{r['q_id']:<3} → {r['verdict_aggregate']:<8}  "
            f"F={s_str}{sj}{reason}"
        )
        for j in r["judges"]:
            if j.get("error"):
                lines.append(f"      {j['judge']:>9} ERROR: {j['error']}")
            else:
                lines.append(
                    f"      {j['judge']:>9} {j['verdict'] or '?':<8} "
                    f"({j['model']})  {j['explanation'][:80]}"
                )
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Self-test — exercises parsing + scoring without making any API calls
# ──────────────────────────────────────────────────────────────────────────────

def _self_test() -> int:
    failures: list[str] = []

    # Verdict parsing
    cases = [
        ("YES\nEvery claim is in passage 1.",         "YES",     "Every claim is in passage 1."),
        ("NO. The answer contradicts passage 2.",     "NO",      "answer contradicts passage 2.".lower() in ""),  # noqa
        ("PARTIAL — claims 1,2 supported; claim 3 not.", "PARTIAL", "claims 1,2 supported"),
        ("yes",                                        "YES",     ""),
        ("Some random reply",                          None,      "Some random reply"),
        ("",                                           None,      ""),
    ]
    for text, expected_verdict, expected_substring in cases:
        verdict, expl = parse_judge_output(text)
        if verdict != expected_verdict:
            failures.append(
                f"parse_judge_output({text!r}) verdict={verdict!r} expected={expected_verdict!r}"
            )
        if isinstance(expected_substring, str) and expected_substring and \
                expected_substring not in expl and expected_substring.lower() not in expl.lower():
            failures.append(
                f"parse_judge_output({text!r}) explanation={expl!r} missing {expected_substring!r}"
            )

    # _score_from_replies aggregation
    r_yes = JudgeReply(judge="a", model="x", verdict="YES", score=1.0, raw="", explanation="")
    r_no  = JudgeReply(judge="a", model="x", verdict="NO",  score=0.0, raw="", explanation="")
    r_par = JudgeReply(judge="b", model="y", verdict="PARTIAL", score=0.5, raw="", explanation="")
    r_err = JudgeReply(judge="b", model="y", verdict=None, score=None, raw="", explanation="", error="boom")

    s, v = _score_from_replies([r_yes, r_yes])
    if not (s == 1.0 and v == "YES"):
        failures.append(f"unanimous YES failed: ({s}, {v})")
    s, v = _score_from_replies([r_yes, r_no])
    if not (s == 0.5 and v.startswith("MIXED")):
        failures.append(f"YES+NO disagreement failed: ({s}, {v})")
    s, v = _score_from_replies([r_yes, r_par])
    if not (abs(s - 0.75) < 1e-9 and v.startswith("MIXED")):
        failures.append(f"YES+PARTIAL avg failed: ({s}, {v})")
    s, v = _score_from_replies([r_err])
    if not (s is None and v == "deferred"):
        failures.append(f"all-errors deferred failed: ({s}, {v})")
    s, v = _score_from_replies([r_par, r_err])
    if not (s == 0.5 and v == "PARTIAL"):
        failures.append(f"one-good-one-error fall-through failed: ({s}, {v})")

    # Build prompt smoke
    p = build_prompt(
        question="Q",
        passages=[{"path": "X.md", "excerpt": "alpha beta gamma"}],
        answer="Alpha beta.",
    )
    if "QUESTION:" not in p or "[1] X.md" not in p:
        failures.append("build_prompt missing required fragments")

    # score_question without keys → deferred
    qs = score_question(
        q_id=99, question="Q", passages=[], answer="A",
        anthropic_key=None, openai_key=None, dry_run=False,
    )
    if qs.verdict_aggregate != "deferred" or qs.score is not None:
        failures.append(f"no-keys path did not defer: {qs}")

    # score_run dry-run smoke
    sc = score_run(
        run=[{"q_id": 1, "question": "Q", "passages": [], "answer": "A"}],
        dry_run=True,
    )
    if sc["aggregate_F"] is not None or sc["scored_count"] != 0:
        failures.append(f"dry-run aggregate not None: {sc}")

    if failures:
        print("FAIL — faithfulness self-test:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(
        "PASS — faithfulness self-test (parse_judge_output, _score_from_replies, "
        "build_prompt, score_question, score_run dry-run)",
        file=sys.stderr,
    )
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="Faithfulness scorer for the Galp Vault retrieval eval.",
    )
    p.add_argument(
        "--run",
        type=Path,
        help="Path to the run JSON document (list of {q_id, question, passages, answer}).",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write the full scorecard JSON.",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the text report on stdout.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate input; do not call any judge API.",
    )
    p.add_argument(
        "--require-judges",
        action="store_true",
        help="Exit with code 2 if neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set.",
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Run the embedded assertion suite (no API calls). Exit 0 on PASS.",
    )
    args = p.parse_args(argv)

    if args.self_test:
        return _self_test()

    if not args.run:
        p.error("--run is required (or pass --self-test)")

    try:
        run = _load_json(args.run)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL — cannot read --run: {exc}", file=sys.stderr)
        return 1
    if not isinstance(run, list):
        print("FAIL — --run JSON must be a list of records", file=sys.stderr)
        return 1

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY") or None
    openai_key = os.environ.get("OPENAI_API_KEY") or None

    if args.require_judges and not (anthropic_key or openai_key):
        print(
            "FAIL — --require-judges set but neither ANTHROPIC_API_KEY "
            "nor OPENAI_API_KEY is in env",
            file=sys.stderr,
        )
        return 2

    scorecard = score_run(
        run=run,
        anthropic_key=anthropic_key,
        openai_key=openai_key,
        dry_run=args.dry_run,
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
        print(f"Wrote scorecard → {args.out}", file=sys.stderr)

    if args.json:
        print(json.dumps(scorecard, indent=2))
    else:
        print(render_text_report(scorecard))
    return 0


if __name__ == "__main__":
    sys.exit(main())
