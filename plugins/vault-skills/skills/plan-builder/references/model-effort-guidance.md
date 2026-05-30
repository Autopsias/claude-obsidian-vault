# Model & thinking-effort guidance (per session)

This is the reference the skill uses to recommend, for **every session**, both a
Cowork **model** and a **thinking-effort** level. It is grounded in Anthropic's
own documentation and in advanced-user practice (sources at the bottom).
Last reviewed: **2026-05-30** (refined: live-vs-async lever; reconciled the
bounded-build→High vs coding/agentic→Extra boundary; added the Sonnet-execute lane).

> **Freshness.** Model names, defaults, and the effort ladder rev often — this was
> written for Opus 4.8 (which defaults to High; `xhigh` shows as **Extra** in the
> Cowork picker). The **picker is ground truth**: verify the current model lineup
> and its default effort at authoring time rather than trusting these labels verbatim.

---

## TL;DR — the house default

> **Default every session to `Opus 4.8 · High`.**
> Then **escalate** to `Extra` / `Max` for the genuinely hard sessions, and
> **de-escalate** to `Sonnet 4.6` (or `Haiku 4.5`) at `Medium` / `Low` for
> mechanical, well-scoped batch work.

> **Refinement — split the default by how the session runs.** Most plan-builder
> sessions are coding/agentic, and Anthropic's own guidance is that **`Extra`
> (`xhigh`) is the *recommended starting point* for coding and agentic work** — not
> High. Extra's cost is mostly **latency + rate-limit**, not quality or dollars, so
> let *how the user runs it* decide: **async** (paste-and-walk-away) coding/agentic
> session → **`Opus 4.8 · Extra`**; **live** (watched) session → **`Opus 4.8 ·
> High`**. Keep the plain "High default" for *bounded, single-pass* work. See
> **"Live vs async"** below.

Why `Opus 4.8 · High` is the baseline (not Sonnet · Medium):

1. **It's Anthropic's own default.** Opus 4.8 ships defaulting to High, which
   Anthropic says "spends similar tokens to Opus 4.7 on coding tasks with better
   performance." High is the *calibrated sweet spot*, not an extravagance.
2. **Plan-builder sessions are never trivial.** The skill refuses to build a
   plan for <6–8 items. Each session is a batch of multi-step orchestration in a
   fresh context — exactly where deeper reasoning pays off and where Medium risks
   under-thinking the hand-offs.
3. **Opus 4.8 is the recommended model for demanding knowledge work** —
   production-ready code, sophisticated agents, and complex document creation —
   which is what these sessions are.
4. **The "Medium-as-default" advice is for a different workload.** Advanced users
   run Medium by default in *high-volume coding CLI* loops where they pay per
   token across hundreds of calls. Cowork plan sessions are lower-volume and
   higher-stakes, so the cost argument for Medium is weaker.

This is a *default*, not a rule. The whole point of putting model + effort on
each card is to vary them deliberately.

---

## The two dials

Cowork (as of 2026-05-28) gives you **two independent controls** next to each
other, set BEFORE you start a session:

- **Model** — *how capable* the engine is (Opus 4.8 ▸ Sonnet 4.6 ▸ Haiku 4.5).
- **Thinking effort** — *how much it deliberates* before/while answering.

They are orthogonal. "Opus 4.8 · Low" (a sharp model thinking briefly) and
"Sonnet 4.6 · Extra" (a lighter model thinking hard) are both valid, different
trade-offs. Each session card recommends a **pair**.

### How thinking-effort actually works (adaptive thinking)

Opus 4.8 uses **adaptive thinking** as its *only* mode: the model itself decides
*whether* and *how much* to think on each turn. **Effort is soft guidance** on
that allocation — a behavioural signal, not a hard token budget. At `High`+ it
almost always thinks; at `Low`/`Medium` it may skip thinking on simple turns.
(Manual `budget_tokens` is gone on Opus 4.7/4.8 — effort is the control.)

---

## The effort ladder (Cowork picker labels)

We display the **Cowork picker labels**. Equivalents in the API / Claude Code
are noted for cross-reference.

| Cowork label | API / Code token | What it does | Reach for it when… |
|---|---|---|---|
| **Low** | `low` | Minimises thinking; skips it on easy turns. Fastest, cheapest, lightest on rate limits. | Trivial, well-defined work: renames, formatting, simple lookups/classification, mechanical batch edits. Pair with an explicit checklist if the task has several parts. |
| **Medium** | `medium` | Moderate thinking; good results at lower cost. | The cost-efficient drop-in for clearly-scoped, everyday work where you don't need maximum depth. |
| **High** ⭐ | `high` (the model default) | Always thinks; deep reasoning. Best balance of quality and tokens. | **Default for substantive sessions** — most build, integration, analysis, and writing work. |
| **Extra** | `xhigh` | Always thinks *deeply* with extended exploration; meaningfully more tokens than High. | **Anthropic's recommended starting point for coding & agentic work** and exploratory tasks: long-running async sessions (30 min+), repeated tool-calling, deep web/KB search, multi-file refactors, big migrations. |
| **Max** | `max` | Maximum depth, no constraints. Slowest, most expensive. | **Genuinely frontier problems only**: gnarly multi-root-cause debugging, novel algorithmic design, high-stakes architecture where being wrong is costly. On most workloads Max adds cost for small gains and can *overthink* structured-output tasks. |

Rule of thumb: **High by default, Extra for hard/long/agentic, Max only when
you'd accept real extra cost and latency to be right.** Don't default to Max —
on structured or less intelligence-sensitive tasks it can hurt.

---

## Choosing the model

| Model | Use it for | Notes |
|---|---|---|
| **Opus 4.8** ⭐ | The default. Production-ready code, complex agentic workflows, hard reasoning, multi-day/multi-session work, polished docs/slides/spreadsheets. | Flagship (shipped 2026-05-28). Same price as 4.7 ($5/$25 per M tok). 1M context. Sharper judgment; ~4× less likely than 4.7 to leave code flaws unflagged; better at flagging its own uncertainty. |
| **Sonnet 4.6** | Well-scoped, mechanical, or high-volume sessions where Opus is overkill: routine CRUD, refactors with clear specs, straightforward content. | Cheaper/faster. Pair with Medium for the cost-lean lane. |
| **Haiku 4.5** | Truly trivial, high-throughput sessions: bulk formatting, simple transforms, light classification. | Cheapest/fastest. Usually paired with Low. Rare as a whole-session choice in a plan. |

---

## Decision framework — session archetype → recommended pair

Match the session's *dominant* activity, not the easiest sub-task in it.

| Session archetype | Model | Effort | Rationale to write in `why_model` |
|---|---|---|---|
| Architecture / design decision, irreversible trade-offs | Opus 4.8 | **Max** (or Extra) | Hard reasoning where being wrong is expensive. |
| Deep research / multi-source synthesis / heavy tool-calling | Opus 4.8 | **Extra** | Exploratory + agentic — Anthropic's recommended starting point. |
| Long-running async build, large multi-file refactor, codebase migration | Opus 4.8 | **Extra** | 30 min+ sustained work with many steps. |
| Gnarly debugging (multiple possible root causes) | Opus 4.8 | **Max** | Needs maximum reasoning to isolate the cause. |
| Coding / agentic build, heavy tool-calling (async) | Opus 4.8 | **Extra** | Anthropic's recommended start for coding/agentic; use **High** for the *live* version (Extra's cost is latency). |
| Standard build / integration — **bounded, single-pass, not agentic** | Opus 4.8 | **High** ⭐ | Substantive but well-understood, and not a long tool-calling loop. |
| Analysis, drafting, structured docs/slides/spreadsheets | Opus 4.8 | **High** | Quality matters; avoid Max here (overthinking risk on structured output). |
| Pure execution of an atomic, pre-designed spec (not design/safety-critical) | Sonnet 4.6 | **Medium**/High | plan-with-Opus / execute-with-Sonnet — Sonnet follows a clear plan cheaply. |
| Well-scoped refactor / routine CRUD with a clear spec | Sonnet 4.6 | **Medium** | Mechanical enough to trade some depth for cost/speed. |
| Bulk rename / formatting / simple transforms / classification | Sonnet 4.6 or Haiku 4.5 | **Low** | Trivial, high-volume — optimise for speed and rate limits. |

When two archetypes fit, **default up, not down**: a session that's "mostly
mechanical but with one design call" should take the higher pair. The one
exception is the Extra-vs-High choice on coding/agentic sessions — there, let
**live-vs-async** decide (see below), not difficulty alone.

### Cost / latency caveats (call these out when relevant)

- Higher effort can exhaust the output budget and run longer — fine for async
  sessions, annoying if you're watching it live.
- **Max can over-think** structured or less intelligence-sensitive tasks
  (tables, fills, format conversions). Prefer High/Extra there.
- Higher effort uses rate limits faster. For a long plan, reserve Extra/Max for
  the sessions that earn it.

### Live vs async — the lever that actually decides Extra-vs-High

The single most useful question before pairing efforts: **will the user watch the
session run, or fire it and walk away?** Over High, Extra (`xhigh`) buys ~2–3×
latency and rate-limit burn for a small — often zero — quality gain; the
token-dollar difference is minor. The cost you actually pay is *time and limits*,
and that only hurts when someone's waiting.

- **Async** (paste the prompt, come back later): use the higher lane freely.
  Anthropic says start coding/agentic work at `xhigh`/Extra, and async is where
  it's free of downside. The right default for "~1 day" sessions.
- **Live** (watching it work, iterating turn-by-turn): default most sessions to
  **High** — the model still thinks deeply, you just don't pay Extra's latency on
  every turn. Step a specific session up to Extra only when it clearly needs the depth.

Ask once during the interview, let the answer set the baseline, override per
session. A plan that's all-Extra "because the work is hard" usually just means
nobody asked whether it runs live.

---

## How the skill encodes this

- Each session carries a `thinking` field (`Low|Medium|High|Extra|Max`; synonyms
  like `xhigh` normalise to `Extra`). It renders as a colour-coded chip beside
  the model chip and the time-estimate chip.
- `why_model` should justify **both** dials in one sentence — it renders as
  "Why Opus 4.8 · Extra effort: …".
- Each card shows a **picker hint** ("set Cowork picker → Opus 4.8 · High") and
  the session protocol reminds the user that model + effort are *picker settings
  set before pasting the prompt*, not edits to the HTML file.
- During the interview, **propose a pair for every session** using the framework
  above; let the user override. Don't leave `thinking` blank on a real plan.

---

## Sources (reviewed 2026-05-29)

- Anthropic — *Effort* (Claude API docs): effort levels, per-level guidance, `xhigh` as the recommended start for coding/agentic work, Max-overthinking caveat. <https://platform.claude.com/docs/en/build-with-claude/effort>
- Anthropic — *Adaptive thinking* (Claude API docs): adaptive-only on Opus 4.7/4.8, effort as soft guidance, `max_tokens` interaction. <https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking>
- Anthropic — *Claude Opus 4.8* (product page): positioning, High default, 1M context, pricing, recommended use cases. <https://www.anthropic.com/claude/opus>
- Anthropic — *Introducing Claude Opus 4.7*: origin of the `xhigh` level and "start at high/xhigh for coding/agentic". <https://www.anthropic.com/news/claude-opus-4-7>
- 9to5Mac, *Anthropic upgrades Claude with Opus 4.8* (2026-05-28): Cowork/claude.ai Effort Control launch; "Extra" = `xhigh`; High default; raised rate limits. <https://9to5mac.com/2026/05/28/anthropic-upgrades-claude-with-opus-4-8-heres-whats-new/>
- Business Standard / BeInCrypto / 9to5Mac (2026-05-28/29): Opus 4.8 benchmark deltas (SWE-Bench Pro 64.3→69.2, HLE 54.7→57.9, GDPval-AA 1753→1890), Fast Mode ~2.5× faster, "4× less likely to leave code flaws unflagged".
- Advanced-user practice — MindStudio, *Claude Code Effort Levels Explained* (2026-03): Low/Medium/High/Max task mapping; Medium as the high-volume coding default. <https://www.mindstudio.ai/blog/claude-code-effort-levels-explained/>
- Advanced-user practice — *ultrathink / thinking modes* handbook: effort↔keyword mapping and the "5+ files / security / architecture → max" decision rule. <https://github.com/ThamJiaHe/claude-code-handbook/blob/main/docs/ultrathink-thinking-modes.md>
