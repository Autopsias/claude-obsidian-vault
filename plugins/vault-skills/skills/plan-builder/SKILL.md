---
name: plan-builder
description: Build a self-contained HTML plan dashboard for multi-phase work across multiple Cowork sessions. Ships with a sticky session strip, donut rings, a session-arc timeline, per-session copy-paste prompts, light/dark theme, and a plan-achievement infographic (phase-journey, maturity-ladder, hub-spoke, before-after, pillars, custom). Every item and session renders DUAL LAYER — plain-English summary + deliverable on top, technical agent spec in collapsible details kept in the DOM for any Claude reading the file. Recommends a Cowork model + thinking-effort pair (Opus 4.8 / Sonnet 4.6 / Haiku 4.5 × Low–Max) per session, and embeds an Operating Manual so future sessions update progress without drift. Use when the user says "create a plan", "build a roadmap", "execution plan", "session plan", "improvement plan", "rollout plan", "project plan dashboard", "multi-session plan", or describes a body of work spanning multiple Cowork sessions even without the word "plan". Not for simple to-do lists.
---

# Plan Builder (Aurora edition)

Generates a self-contained HTML plan dashboard for any multi-session execution plan. Output is a single `.html` file (~150-250 KB, no external dependencies beyond Google Fonts) that the user opens directly in their browser.

The Aurora edition gives every plan a **dual-layer voice**: the parts a human reads to follow the plan, and the parts an AI agent reads to execute it. Both live in the same document — the human layer prominent in serif type, the agent layer one click away inside a `<details>` block but always present in the DOM.

## What the output gives the user

1. **Editorial page header** — serif title, glass-blur sticky banner, last-updated stamp.
2. **Sticky session navigation strip** — 1 chip per session, color-coded by status, click to jump.
3. **Operating Manual** at the very top — collapsed for humans, fully in DOM for any Claude that opens the file (this is the load-bearing rule sheet).
4. **Plan Achievement infographic** — visual story of what the plan achieves (one of 5 structured SVG templates or `custom`).
5. **Up Next callout** — quiet terminal-style prompt, auto-derives the next non-DONE session.
6. **Twin donut rings** — items + sessions, status-segmented, TODO arc at reduced opacity so 0/N looks intentional.
7. **Status filter chips + category filter chips** — both filter the cards below.
8. **Categories status grid** — one row per category with colored accent + segmented progress bar + ratio.
9. **Session arc timeline** — N SVG segments, status-colored, model dot below each, click jumps.
10. **Session Plan section** — every session as a card with: step indicator ("Session 3 of 18"), title, status pill, **model chip + thinking-effort chip** (the pair to set in the Cowork picker), time estimate, plain-English human summary, deliverable callout, items in scope, why-this-model-and-effort rationale, prominent action bar ("Copy prompt" / "Jump to card" / "Open next →") with a **picker hint** ("set Cowork picker → Opus 4.8 · High"), collapsible agent spec containing the full prompt + closeout, notes.
11. **Category sections** — one per category with item cards in the same dual-layer pattern.
12. **Floating progress pill** — bottom-right; appears once you scroll past the dashboard; shows overall % done + quick link to the next session.
13. **Light + dark theme** — auto via `prefers-color-scheme` + manual cycle button.

## When to invoke

- "I need a plan for X" / "Build a plan to do Y" / "Create a roadmap for Z"
- "Help me organize this body of work into sessions"
- After running an analysis/audit that produced a long list of action items
- After a `/design:design-critique` or similar produced ~15+ items the user wants to execute

If the user has fewer than 6-8 actionable items, this skill is overkill — suggest a simpler list instead.

## Workflow

### 1. Capture the plan structure

Interview the user. Get enough to produce a useful first draft; don't drill on every field. Ask about:

- **Title** — one line, e.g., "Q4 Product Launch Plan"
- **Subtitle / one-line goal** — what this plan achieves
- **Narrative** (optional) — 1-2 sentence explanation of WHY this plan exists; renders inside the Plan Achievement section
- **Categories** — 3-7 logical groupings of work (e.g., "Quick Wins", "Defence on Truth", "Skill Updates")
- **Items** — the actual action items
- **Sessions** — how items will be batched into Cowork sessions, and for each one the **model + thinking-effort** to set in the Cowork picker (see "Recommend a model + thinking-effort for each session" below)
- **Infographic template** — pick one of: `phase-journey`, `maturity-ladder`, `hub-spoke`, `before-after`, `pillars`, or `custom`. See `references/infographic-templates.md`.

Use AskUserQuestion for choices (template selection, infographic type) and free-form for content. Don't ask 30 questions — group into a few covering the key decisions, then iterate.

#### Dual-layer authoring — the highest-leverage move

For each item and each session, draft **two** pieces of text:

- `human_summary` — one or two sentences in plain English, the voice you'd use explaining the work to a peer in the hallway. No acronyms, no file paths, no dev steps. **This is the most prominent text on the card.** Aim for "what does this mean for the business / for the user" rather than "what files get touched."
- `deliverable` — one sentence describing the concrete outcome. "When done, X exists / Y is verifiable / Z is true." Rendered as a green-tinted callout. Makes progress legible at a glance.

The user almost never volunteers these. Draft both from the title + description, show the draft, let them refine.

The technical details (`description`, `agent_instructions`, `schema`, `mockup`, `code`, `touches`) go into the **agent-spec** layer — a collapsible details block that's still in the DOM, so a Claude opening the file sees everything, but the human view stays clean.

When to add a `schema`, `mockup`, or `code` block:

- **`schema`** — when an item involves a data shape, API contract, or DB schema. JSON, SQL DDL, GraphQL, TS interface — anything an executing Claude will want to match exactly.
- **`mockup`** — when there's a UX surface or visual layout. Inline SVG is best; ASCII works for terminal output / data tables.
- **`code`** — when a small code excerpt clarifies the expected shape (a function signature, a config snippet, a usage example).

If none of those add clarity, leave them out — empty blocks aren't helpful.

#### Recommend a model + thinking-effort for each session

Cowork exposes **two picker dials** the user sets before pasting a prompt: the **model** (Opus 4.8 / Sonnet 4.6 / Haiku 4.5) and the **thinking-effort** (`Low` / `Medium` / `High` / `Extra` / `Max`). Set BOTH on every session via the `model` and `thinking` fields, and justify the pair in one sentence in `why_model`.

**First, ask the question that sets the whole effort baseline: will the user run these sessions _live_ (watching them) or _async_ (paste-and-walk-away)?** Extra's real cost over High is ~2–3× latency and rate-limit burn, with near-zero quality downside and negligible token-dollar difference — so the live/async answer, not raw difficulty, is what decides whether Extra earns its place. Ask once in the interview; let the answer set the default and override per session.

Pick the lane by the session's *dominant* activity:

- **Coding / agentic / multi-step / heavy tool-calling build** (most plan-builder sessions) → **`Opus 4.8 · Extra`** when async, **`Opus 4.8 · High`** when live. This is Anthropic's own line: `xhigh`/Extra is *the recommended starting point for coding and agentic work* — but its cost is latency, so don't pay it while the user is watching.
- **Bounded, single-pass work** — one structured doc/slide/sheet, a contained refactor with a clear spec, a claim/data review → **`Opus 4.8 · High`**. "Standard build → High" means *non-agentic, single-pass*, not "any build."
- **Irreversible architecture / gnarly multi-root-cause debugging** → **`Opus 4.8 · Max`** (rare). Avoid `Max` on structured-output sessions (tables, slides, fills) — it overthinks.
- **Pure execution of an already-designed, atomic, unambiguous spec** (not design, not safety-critical) → **`Sonnet 4.6 · Medium`** (or `High`). This is the plan-with-Opus / execute-with-Sonnet pattern — Sonnet follows a clear plan cheaply.
- **Trivial high-volume passes** (renames, formatting, simple transforms, classification) → **`Sonnet 4.6` / `Haiku 4.5 · Low`**.

**Then sanity-check the spread before you finalize.** Effort is a per-session allocation, not a blanket setting. If nearly every card lands on Extra (or Max), re-examine — structured / eval / packaging / scaffolding sessions usually belong at High even inside a coding plan. A healthy heavy-engineering plan is *mostly Extra with a few High*; a healthy mixed plan is *mostly High with a few Extra and the odd Sonnet*. All-one-level is a smell.

**Read `references/model-effort-guidance.md` before authoring** — it has the full archetype→pair decision table, the effort ladder, the live-vs-async lever, cost/latency caveats, and sources. As with `human_summary`, propose a pair for every session and let the user override; don't leave `thinking` blank on a real plan.

### 2. Build the JSON spec

Compile the user's answers into a JSON spec. See `references/schemas.md` for the full schema. Save to a temp file (e.g., `/tmp/plan-spec.json`) so the build script can read it.

For sessions, the `prompt` field is what the user pastes into a fresh Cowork session. Help the user write good prompts — Cowork-paste-ready, specific instructions, pre-session decisions called out. Keep them 150-300 words. The build script appends a structured closeout to every prompt automatically; the user only writes the task body.

### 3. Run the build script

```bash
python /path/to/skill/scripts/build_plan.py <spec.json> <output.html>
```

The script reads the spec, validates it (`scripts/validate_spec.py` surfaces errors before build), then emits a complete HTML file with all CSS, JS, fonts, donuts, arc, infographic, item cards, session cards, and prompts assembled.

### 4. Save and register the plan

A plan only matters if Claude can find it three months later when the user comes back for session 12. Three layers:

**Layer 1 — Default save location.** Save the plan at `<project-root>/_plans/_plan_<slug>_<YYYY-MM-DD>.html`. The leading underscore matches Cowork-vault conventions for working files; `_plans/` is greppable.

For vault-style projects (Galp-Vault et al. with `99 Workspace/` etc.), prefer `99 Workspace/_plan_<slug>_<date>.html` to match existing conventions. Ask if unsure.

**Layer 2 — Project-level index.** Pass `--register-in <project-root>` to `build_plan.py` and it creates/updates `<project-root>/_plans_index.md`. Future Claude sessions can find any active plan by reading this file.

```bash
python build_plan.py spec.json output.html --register-in /path/to/project
```

**Layer 3 — Pointer in CLAUDE.md or session-handoff.** The `--register-in` flag prints a one-line snippet to paste into the project's `CLAUDE.md` (preferred) or its session-handoff file.

After saving, respond to the user with:
- A `computer://` link to the file
- The CLAUDE.md / handoff snippet to paste (or offer to add it yourself)
- Counts: sessions, items, categories
- Infographic template chosen
- The Up Next session (S01)
- A note: "Future sessions can find this plan by reading `_plans_index.md` in the project root."

## Operating principles

### The dual-layer principle

The output is two documents stitched into one:
- A **human-readable plan** — what the work means, what each session achieves, where you are.
- An **agent-runnable spec** — full prompts, schemas, mockups, code excerpts, edit instructions.

The human layer is prominent (serif type, callouts, generous whitespace). The agent layer lives inside `<details class="agent-spec">` blocks — visually quiet but always in the DOM, so any Claude that opens the file sees everything regardless of `open` state. This is what lets the file serve both audiences without compromising either.

When drafting cards, write the `human_summary` and `deliverable` as if your reader has never seen the source spec. If the human layer can't stand on its own, the plan won't survive a quarter on the shelf.

### Why the Operating Manual matters

The HTML embeds an Operating Manual at the top of `<main>` describing what Claude can edit (only `data-status` + pill text + `data-updated` + notes) and what auto-recomputes (donuts, arc, categories, counters, last-updated stamp, Up Next, floating progress pill). This is the single most load-bearing feature of the output — it lets a fresh Cowork session read the file once and update progress correctly without breaking anything. The build script handles it; don't remove or restructure.

### Why prompts are self-contained

Every session prompt block ends with a structured closeout (5 steps, no counter math) embedded in the prompt text. When the user clicks "Copy prompt" and pastes it into a fresh Cowork session, that fresh Claude sees the closeout in its context — it doesn't have to read the HTML to discover the protocol. Don't move the closeout out of the prompt body or it will silently break.

### Why we minimize Claude's update surface

The dashboard auto-recomputes counters, donut segments, category bars, session arc, last-updated stamp, Up Next callout, and floating progress pill from `data-status` attributes on each `<article>`. Claude only ever needs to update those attributes (and add a note). Counters, span text, comment-block counts, and SVG fills all derive from there. This drops per-session edit cost from ~10 surgical edits to ~5 simple ones and removes drift potential.

### Be helpful with prompt drafting

When interviewing, the user might say "S03 covers items DT-01 and DT-02; just bundle them." Don't insist on full prompt text — offer to draft it from the item descriptions. Show the draft, let them refine. Same for `human_summary`, `deliverable`, `why_model`, `agent_instructions`.

## Plan-achievement infographic templates

Five reusable SVG templates ship with the skill, plus `custom` for bespoke visuals. Pick one based on the plan's archetype:

- **`phase-journey`** — horizontal flow: Now → Phase 1 → Phase 2 → … → Goal. Best for *staged rollouts* (the safe default).
- **`maturity-ladder`** — vertical stairs: each step = a capability level. Best for *capability-building plans*.
- **`hub-spoke`** — center node = goal, spokes = workstreams. Best for *cross-cutting initiatives*.
- **`before-after`** — two cards side-by-side with current-state and target-state bullets. Best for *transformation plans*.
- **`pillars`** — roof = goal, pillars = workstreams (each fills with progress), foundation = current capability. Best for *structural improvements*.
- **`custom`** — user (or Claude) provides raw SVG markup with simple data-binding hooks. Best when none of the structured templates capture the narrative without distortion.

See `references/infographic-templates.md` for the data each template needs and when to recommend it. The build script handles SVG generation for the 5 structured templates — the spec just needs the right shape per template. For `custom`, the SVG itself comes from the spec and the build wires data binding.

## Files and references

- `scripts/build_plan.py` — builds the HTML from a JSON spec. Run as `python build_plan.py <spec.json> <output.html>`.
- `scripts/validate_spec.py` — validates a spec before build; surfaces missing fields and invalid IDs.
- `assets/base-template.html` — the static HTML structure (CSS, JS, head, footer) with marker placeholders that the build script fills.
- `assets/infographics/` — SVG renderers for the 5 templates (loaded by build_plan.py).
- `references/infographic-templates.md` — descriptions of each template, the data it needs, and when to recommend it.
- `references/schemas.md` — full JSON schema for the plan spec, including the dual-layer fields and the `model` / `thinking` session fields.
- `references/model-effort-guidance.md` — per-session model + thinking-effort decision framework (Opus 4.8 / Sonnet 4.6 / Haiku 4.5 × Low/Medium/High/Extra/Max), grounded in Anthropic + advanced-user guidance.
- `references/examples.md` — sample specs for different plan archetypes.

## Output expectations

Final output: a single `.html` file usually under 250 KB, opens in any modern browser. Google Fonts loaded over the network for typography but page works offline with system font fallback. The HTML is self-contained — the user can email it, host it, or stash it on a network drive and it still works.

If anything is unclear during interview, ask. The user's domain knowledge about their own plan beats your guesses — but don't ask them to author the prompt-block body if a draft from item descriptions would do; offer first. Same for `human_summary`, `deliverable`, and `why_model`.
