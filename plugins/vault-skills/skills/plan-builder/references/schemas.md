# Plan Spec Schema (Aurora edition)

The build script expects a JSON file with this shape. All fields without "(optional)" are required.

The Aurora edition introduces **dual-layer authoring**: each item and session can carry both a *human-readable* layer (plain English, prominent on screen) and an *agent-readable* layer (technical spec, collapsed by default but always in the DOM for any Claude that opens the file). Every new field is optional; old specs continue to build identically except for the visual refresh.

```json
{
  "title": "Q4 Product Launch Plan",
  "subtitle": "Get the v3.0 release across the line",
  "meta": "(optional) 12 sessions · 28 items · 4 phases",
  "categories": [
    {
      "key": "engineering",
      "label": "Engineering",
      "description": "(optional) one-line context shown in the section header"
    }
  ],
  "items": [
    {
      "id": "eng-01",
      "title": "Spike: validate auth migration approach",
      "category": "engineering",

      "human_summary": "(optional, RECOMMENDED) one or two plain-English sentences about what this is and why it matters in real-world terms. Rendered prominent + readable.",
      "deliverable":   "(optional, RECOMMENDED) one sentence describing the concrete outcome — 'When done, X exists / Y is verifiable.' Rendered as a highlighted callout.",
      "why":           "(optional) one sentence on the underlying problem this solves. Rendered as italic 'Why:' line.",

      "description":  "(optional, agent layer) longer technical description. Surfaced inside the collapsible agent-spec, not in the human layer.",
      "agent_instructions": [
        "(optional, agent layer) numbered bullets describing concrete dev steps Claude should take",
        "or a single string if a paragraph is enough"
      ],
      "schema": {
        "lang":    "json",
        "code":    "{ \"field\": \"...\", \"...\": \"...\" }",
        "caption": "(optional) one-line caption shown below the block"
      },
      "mockup": {
        "svg":     "<svg viewBox='0 0 200 100'>...</svg>",
        "caption": "(optional) caption"
      },
      "code": {
        "lang": "ts",
        "code": "interface InviteRequest { ... }"
      },

      "owner":   "(optional) Person or team",
      "target":  "(optional) Target date e.g. 2026-06-15 or 'end of Q3'",
      "touches": "(optional) Files / areas affected. Surfaced inside the agent-spec.",
      "priority": "P0",
      "effort":   "M",
      "updated":  "(optional) ISO date, defaults to today"
    }
  ],
  "sessions": [
    {
      "id":      "s01",
      "title":   "Auth migration spike",
      "model":   "Opus 4.8",
      "thinking":"High",
      "effort":  "~2h",

      "human_summary": "(optional, RECOMMENDED) one or two sentences in plain English about what this session achieves. Rendered in serif at 18px — the most prominent text on the card.",
      "deliverable":   "(optional, RECOMMENDED) one sentence: what concretely exists at session end. Rendered as a highlighted callout.",
      "why_model":     "(optional) One-sentence rationale for the model + thinking-effort pair. Renders as 'Why Opus 4.8 · High effort: …'",
      "agent_instructions": [
        "(optional, agent layer) any extra notes that should go INSIDE the agent-spec but outside the prompt body itself. Most plans won't need this."
      ],

      "items":  ["eng-01", "eng-02"],
      "prompt": "Execute SESSION S01 — Auth migration spike.\n\nItems:\n1. eng-01 — ...\n2. eng-02 — ...\n\n(The build script appends a structured CLOSEOUT block automatically — don't include closeout instructions here.)",
      "updated": "(optional) ISO date"
    }
  ],
  "infographic": {
    "type":      "phase-journey",
    "title":     "From <em>v2.5</em> to <em>v3.0 production</em>",
    "eyebrow":   "(optional) Plan Achievement · Visual Story",
    "narrative": "(optional) 1-2 sentence story of WHY this plan exists",

    "phases": [
      {"num": 1, "name": "Foundation", "tagline": "auth + observability", "items": ["eng-01", "eng-02"]}
    ],
    "anchor_now":  {"name": "v2.5 brittle", "tagline": "no auth · gap-y observability"},
    "anchor_goal": {"name": "v3.0 ready",   "tagline": "auth · observable · documented"}

    /* see infographic-templates.md for the maturity-ladder / hub-spoke /
       before-after / pillars / custom field shapes */
  }
}
```

## Field reference

### Top-level

- **`title`** (string, required) — Plan title in the page header `<h1>` and `<title>`.
- **`subtitle`** (string, optional) — Short tagline shown in the header meta line.
- **`meta`** (string, optional) — Custom meta line. Defaults to `"N sessions · M items"`.
- **`categories`** (array, required) — At least one category. Items must reference one.
- **`items`** (array, required) — Action items. Unique IDs. Categories must exist.
- **`sessions`** (array, required) — Sessions in execution order. Items referenced must exist.
- **`infographic`** (object, required) — One of the 5 plan-achievement template specs (`phase-journey`, `maturity-ladder`, `hub-spoke`, `before-after`, `pillars`) or `custom`.

### Items — the dual-layer surface

**Human layer (prominent on screen):**
- **`id`** (string, required) — Unique. Convention: `cat-prefix-NN` (e.g., `eng-01`, `qw-01`). Lowercase.
- **`title`** (string, required)
- **`category`** (string, required) — Must match a `categories[].key`.
- **`human_summary`** (string, optional, *recommended*) — One or two plain-English sentences. Rendered above the deliverable callout at 14.5px. This is what Ricardo reads when scanning the plan.
- **`deliverable`** (string, optional, *recommended*) — Concrete outcome. Rendered as a green-tinted callout with eyebrow label "When done". Makes progress legible at a glance.
- **`why`** (string, optional) — One sentence on the underlying problem. Rendered as italic "Why:" line.
- **`priority`** (`"P0"|"P1"|"P2"|"P3"`) — Defaults to `"P3"`. Drives chip color.
- **`effort`** (`"S"|"M"|"L"|"XL"`) — Defaults to `"M"`. Free-form chip text accepted.
- **`owner`** (string, optional)
- **`target`** (string, optional) — ISO date or relative ("end of Q3").
- **`updated`** (string, optional) — ISO date string. Defaults to today.

**Agent layer (collapsed by default, always in DOM):**
- **`description`** (string, optional) — Longer technical description. Surfaced inside the agent-spec details block, not in the prominent area.
- **`agent_instructions`** (array of string OR single string, optional) — Concrete dev steps for Claude. Rendered as an ordered list inside the agent-spec.
- **`schema`** (string OR object, optional) — Code block. Object form: `{lang, code, caption}`. Shown in a dark inline `code-block` inside the agent-spec.
- **`mockup`** (string OR object, optional) — Visual mockup. Forms accepted:
  - String starting with `<svg`: rendered as inline SVG.
  - String otherwise: rendered as ASCII / plaintext mockup in a `<pre>`.
  - Object: `{svg|img|ascii, caption, alt}`.
- **`code`** (string OR object, optional) — Code excerpt (different from schema). Same form as `schema`.
- **`touches`** (string, optional) — Files / areas affected. Surfaced inside agent-spec when other agent fields are present, otherwise visible in the meta-row.

### Sessions — same dual-layer pattern

**Human layer:**
- **`id`** (string, required) — Convention: `sNN` (e.g., `s01`).
- **`title`** (string, required)
- **`model`** (string) — The Cowork model to set in the picker. Free-form label; write the real name, e.g. `"Opus 4.8"`, `"Sonnet 4.6"`, `"Haiku 4.5"`. Defaults to `"Sonnet"`. The chip colour + arc dot derive a *family* (opus / sonnet / haiku) from the label, so any version string renders correctly. **Set this explicitly on every session** (see `model-effort-guidance.md`).
- **`thinking`** (`"Low"|"Medium"|"High"|"Extra"|"Max"`, optional but *strongly recommended*) — The Cowork **thinking-effort** level to set in the picker. Renders as a colour-coded chip (escalating warm tint) beside the model. Synonyms normalise: `xhigh`/`extra high` → `Extra`, `max`/`maximum` → `Max`, etc. House default is `High`; escalate to `Extra`/`Max` for hard/long/agentic sessions, drop to `Medium`/`Low` for mechanical ones. Invalid values fail validation. See `model-effort-guidance.md`.
- **`effort`** (string, optional) — TIME estimate, free-form, e.g. `"~2h"`, `"half day"`. **This is duration, not thinking-effort** — the thinking level lives in `thinking`. Renders as a separate neutral chip.
- **`human_summary`** (string, optional, *strongly recommended*) — One or two sentences in plain English about what this session achieves. Rendered in serif at 18px — the most prominent text on the card. Ricardo reads this first.
- **`deliverable`** (string, optional, *recommended*) — Concrete outcome at session end. Rendered as a green callout.
- **`why_model`** (string, optional, *recommended*) — One-sentence rationale for the model **and** thinking-effort pair. Rendered as an italic line, e.g. "Why Opus 4.8 · Extra effort: …".

**Agent layer:**
- **`items`** (array of item IDs, required) — Items completed in this session.
- **`prompt`** (string, required) — The task body the user pastes into Cowork. The build script appends a structured CLOSEOUT block automatically. **Don't include closeout instructions yourself.** Rendered inside the collapsible agent-spec; the prominent "Copy prompt" button copies the full text whether the block is open or not.
- **`agent_instructions`** (array OR string, optional) — Extra agent-only notes that don't belong inside the prompt body. Most sessions won't need this.
- **`updated`** (string, optional) — ISO date.

### Authoring guidance

When interviewing the user, the highest-leverage fields to draft *for them* are `human_summary` and `deliverable` — these turn the plan from "a list of tickets" into "a story the principal can follow at a glance." The author rarely volunteers them, but Claude can draft both from the title and existing description and ask the user to refine.

Bias toward writing `human_summary` in the voice of someone explaining the work to a peer in the hallway — short, concrete, no jargon-for-jargon's-sake. Save acronyms, code, file paths and dev steps for `agent_instructions` and `description`, where they belong.

### Model & thinking-effort

Every session recommends a Cowork **model** + **thinking-effort** pair the user sets in the picker *before* pasting the prompt. Default to **`Opus 4.8 · High`**; escalate to `Extra`/`Max` for hard, long, or agentic sessions; drop to `Sonnet 4.6` / `Haiku 4.5` at `Medium`/`Low` for mechanical work. Put the justification in `why_model`. The full decision framework (archetype → pair), the effort ladder, cost caveats, and sources live in **`model-effort-guidance.md`** — read it when authoring a plan.

### Infographics

See `infographic-templates.md` for descriptions and which template fits which plan archetype.
