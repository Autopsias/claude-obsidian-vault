---
name: plan-builder
description: Build a self-contained HTML plan dashboard for executing multi-phase work across multiple Cowork sessions. Output ships with sticky session strip, twin donut rings, session-arc timeline, categories grid, copy-pasteable per-session prompts with embedded closeout protocols, light/dark theme, and a plan-achievement infographic (5 templates — phase-journey, maturity-ladder, hub-spoke, before-after, pillars). The HTML embeds an Operating Manual that future Claude sessions read before editing so progress updates stay drift-free. Use this skill when the user mentions "create a plan", "build a roadmap", "execution plan", "session plan", "improvement plan", "rollout plan", "project plan dashboard", "multi-session plan", or wants to track progress through discrete items batched into sequential sessions. Trigger even without the word "plan" — if they describe a body of work spanning multiple Cowork sessions, this is the tool. Do NOT use for simple to-do lists or one-off charts.
---

# Plan Builder

Generates a self-contained HTML plan dashboard for any multi-session execution plan. Output is a single `.html` file (~200 KB, no external dependencies beyond Google Fonts) that the user opens directly in their browser.

## What the output gives the user

1. **Sticky session navigation strip** at the top — 1 chip per session, color-coded by status, click to jump
2. **Plan Achievement infographic** — visual story of what the plan achieves (one of 5 SVG templates)
3. **Up Next callout** — terminal-command styled, auto-derives the next non-DONE session
4. **Twin donut rings** — items + sessions, status-segmented, with TODO arc shown at reduced opacity so 0/N looks intentional
5. **Status filter chips + category filter chips** — both filter the cards below
6. **Categories status grid** — one row per category with colored accent + segmented progress bar + ratio
7. **Session arc timeline** — N SVG segments, status-colored, model dot below each, click jumps
8. **Session Plan section** — every session as a card with: title, status pill, model chip, effort, item list, copy-pasteable prompt block, lean closeout checklist, notes
9. **Category sections** — one per category with item cards (id, title, status, priority, effort, description, why, owner, target, files touched, session back-link, notes)
10. **Light + dark theme** — auto-switch via `prefers-color-scheme` + manual cycle button
11. **Operating Manual** at the very top — collapsed by default for humans, fully visible to any Claude that opens the file

## When to invoke

- "I need a plan for X" / "Build a plan to do Y" / "Create a roadmap for Z"
- "Help me organize this body of work into sessions"
- After running an analysis/audit that produced a long list of action items
- After a `/design:design-critique` or similar produced ~15+ items the user wants to execute

If the user has fewer than 6-8 actionable items, this skill is overkill — suggest a simpler list instead.

## Workflow

### 1. Capture the plan structure

Interview the user. The skill needs ENOUGH to produce a useful first draft; you don't need to drill on every field. Ask about:

- **Title** — one line, e.g., "Q4 Product Launch Plan"
- **Subtitle / one-line goal** — what this plan achieves
- **Narrative** (optional) — 1-2 sentence explanation of WHY this plan exists; renders inside the Plan Achievement section
- **Categories** — 3-7 logical groupings of work (e.g., "Quick Wins", "Defence on Truth", "Skill Updates")
- **Items** — the actual action items, each with: title, description, why, owner, target date, files/areas touched, priority (P0/P1/P2/P3), effort (S/M/L/XL), and which category it belongs to
- **Sessions** — how items will be batched. Each session: title, model recommendation (Sonnet/Opus + why), estimated effort, list of item IDs in scope, and the prompt content the user will paste into a fresh Cowork session
- **Infographic template** — pick one of: `phase-journey`, `maturity-ladder`, `hub-spoke`, `before-after`, `pillars`. See `references/infographic-templates.md` for descriptions and when each fits.
- **Infographic content** — depends on template choice. For `phase-journey`: the phases (each with name, tagline, item IDs); the "Now" anchor (current state, taglines); the "Goal" anchor (target state, taglines).

Use AskUserQuestion for choices (template selection, infographic type) and free-form for content. Don't ask 30 questions — group into a few questions covering the key decisions, then iterate.

### 2. Build the JSON spec

Compile the user's answers into a JSON spec. See `references/schemas.md` for the full schema. Save to a temp file (e.g., `/tmp/plan-spec.json`) so the build script can read it.

For sessions, the prompt content is the bulk of each entry. Help the user write good prompts — Cowork-paste-ready, with specific instructions and any pre-session decisions called out. Keep them around 150-300 words. The build script appends a structured closeout to every prompt automatically; the user only writes the task body.

### 3. Run the build script

```bash
python /path/to/skill/scripts/build_plan.py <spec.json> <output.html>
```

The script reads the spec, validates it (use `scripts/validate_spec.py` to surface errors before build), then emits a complete HTML file with all CSS, JS, fonts, donuts, arc, infographic, item cards, session cards, and prompts assembled.

### 4. Save and register the plan (so future sessions can find it)

A plan only matters if Claude can find it three months later when the user comes back for session 12. Make discovery work via three layers:

**Layer 1 — Default save location.** Save the plan at `<project-root>/_plans/_plan_<slug>_<YYYY-MM-DD>.html`. The leading underscore matches Cowork-vault conventions for working files; `_plans/` is greppable.

For vault-style projects (Galp-Vault et al. with `99 Workspace/` etc.), prefer `99 Workspace/_plan_<slug>_<date>.html` to match existing conventions. Ask the user if unsure where to place it.

**Layer 2 — Project-level index.** Pass `--register-in <project-root>` to `build_plan.py` and it will create/update `<project-root>/_plans_index.md` listing all plans in the project (one line per plan: title, path, session/item counts, date). Future Claude sessions can find any active plan by reading this file.

```bash
python build_plan.py spec.json output.html --register-in /path/to/project
```

**Layer 3 — Pointer in CLAUDE.md or session-handoff.** The `--register-in` flag also prints a one-line snippet to paste into the project's `CLAUDE.md` (preferred) or its session-handoff file. Show the snippet to the user; offer to update CLAUDE.md directly if the project allows it.

Example snippet emitted:
```
**Active plan:** [Q4 Launch](_plans/_plan_q4_launch_2026-05-10.html) · 5 sessions · execute via plan-builder protocol · see also `_plans_index.md`
```

After saving, respond to the user with:
- A `computer://` link to the file
- The CLAUDE.md / handoff snippet for them to paste (or offer to add it yourself)
- Counts: sessions, items, categories
- Infographic template chosen
- The Up Next session (S01)
- A note: "Future sessions can find this plan by reading `_plans_index.md` in the project root."

## Operating principles

### Why the Operating Manual matters

The HTML embeds an Operating Manual at the top describing what Claude can edit (only `data-status` + pill text + `data-updated` + notes) and what auto-recomputes (donuts, arc, categories, counters, last-updated stamp). This is the single most load-bearing feature of the output: it lets a fresh Cowork session read the file once and update progress correctly without breaking anything. Do NOT remove or modify this manual structure when generating — the build script handles it.

### Why prompts are self-contained

Every session prompt block ends with a structured closeout (5 steps, no counter math) embedded in the prompt text. When the user copies a prompt and pastes it into a fresh Cowork session, that fresh Claude sees the closeout in its context — it doesn't have to read the HTML file to discover the protocol. Don't move the closeout out of the prompt body or it will silently break.

### Why we minimize Claude's update surface

The dashboard auto-recomputes counters, donut segments, category bars, session arc, and last-updated stamp from `data-status` attributes on each `<article>`. Claude only ever needs to update those attributes (and add a note). Counters, span text, comment-block counts, and SVG fills all derive from there. This drops per-session edit cost from ~10 surgical edits to ~5 simple ones and removes drift potential.

### Be helpful with prompt drafting

When interviewing, the user might say "S03 covers items DT-01 and DT-02; just bundle them." Don't insist on full prompt text — offer to draft it from the item descriptions. Show the draft, let them refine. Same for "Why this model" rationales.

## Plan-achievement infographic templates

Five reusable SVG templates ship with the skill. Pick one based on the plan's archetype:

- **`phase-journey`** — horizontal flow: Now → Phase 1 → Phase 2 → … → Goal. Best for *staged rollouts* (most plans). Each phase fills with green progress as items in that phase complete.
- **`maturity-ladder`** — vertical stairs: each step = a capability level. Best for *capability-building plans* (e.g., "we need to go from no observability to production-grade").
- **`hub-spoke`** — center node = goal, spokes = workstreams. Best for *cross-cutting initiatives* where multiple workstreams converge on one outcome.
- **`before-after`** — two cards side-by-side with current-state and target-state bullets, arrow with progress %. Best for *change management / transformation plans*.
- **`pillars`** — roof = goal, pillars = workstreams (each fills with progress), foundation = current capability. Best for *structural improvements* (e.g., "build defensible engineering culture on these 4 pillars").
- **`custom`** — user (or Claude) provides raw SVG markup with simple data-binding hooks. Best when the plan's narrative needs a bespoke visual that none of the structured templates capture — geographic maps, network/dependency graphs, mountain-climb illustrations, Sankey flows, custom illustrations. Author the SVG, mark elements with `data-group="GROUP_ID"` and `data-render="progress-fill|count|percent|opacity|status-class|progress-stroke|progress-height"`, and the build script auto-binds progress data to those elements. For total flexibility, supply `renderer_js` with custom logic (receives `(svg, itemsArr, GROUPS)`).

See `references/infographic-templates.md` for the data each template needs and when to recommend it. The build script handles SVG generation for the 5 structured templates — the spec just needs the right shape per template. For `custom`, the SVG itself comes from the spec and the build wires data binding.

When recommending: try the 5 structured templates first. Drop to `custom` when the narrative is genuinely unconventional — when forcing the plan into one of the structured shapes would distort the story you're trying to tell.

## Files and references

- `scripts/build_plan.py` — builds the HTML from a JSON spec. Run as `python build_plan.py <spec.json> <output.html>`.
- `scripts/validate_spec.py` — validates a spec before build; surfaces missing fields and invalid IDs.
- `assets/base-template.html` — the static HTML structure (CSS, JS, head, footer) with marker placeholders that the build script fills.
- `assets/infographics/` — SVG renderers for the 5 templates (loaded by build_plan.py).
- `references/infographic-templates.md` — descriptions of each template, the data it needs, and when to recommend it.
- `references/schemas.md` — full JSON schema for the plan spec.
- `references/examples.md` — sample specs for different plan archetypes.

## Output expectations

Final output: a single `.html` file under 250 KB, opens in any modern browser. Google Fonts loaded over the network for typography but page works offline with system font fallback. The HTML is self-contained — the user can email it, host it, or stash it on a network drive and it still works.

If anything is unclear during interview, ask. The user's domain knowledge about their own plan beats your guesses — but don't ask them to author the prompt-block body if a draft from item descriptions would do; offer first.
