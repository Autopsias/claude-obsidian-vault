# Plan Spec Schema

The build script expects a JSON file with this shape. All fields without "(optional)" are required.

```json
{
  "title": "Q4 Product Launch Plan",
  "subtitle": "Get the v3.0 release across the line",
  "meta": "12 sessions · 28 items · 4 phases",
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
      "description": "Detailed description of what this item is.",
      "why": "(optional) Why this item exists / what problem it solves.",
      "owner": "(optional) Person or team",
      "target": "(optional) Target date e.g. 2026-06-15",
      "touches": "(optional) Files / areas affected, shown in <code>",
      "priority": "P0",
      "effort": "M",
      "updated": "(optional) ISO date, defaults to today"
    }
  ],
  "sessions": [
    {
      "id": "s01",
      "title": "Auth migration spike",
      "model": "Sonnet",
      "effort": "~2h",
      "why_model": "(optional) Rationale for model choice",
      "items": ["eng-01", "eng-02"],
      "prompt": "Execute SESSION S01 — Auth migration spike.\n\nRead first: ...\n\nItems:\n1. eng-01 — ...\n2. eng-02 — ...",
      "updated": "(optional) ISO date"
    }
  ],
  "infographic": {
    "type": "phase-journey",
    "title": "From <em>v2.5</em> to <em>v3.0 production</em>",
    "eyebrow": "(optional) Plan Achievement · Visual Story",
    "narrative": "(optional) 1-2 sentence story of WHY this plan exists",

    // Template-specific fields below — vary per type:

    // For type: "phase-journey"
    "phases": [
      {"num": 1, "name": "Foundation", "tagline": "auth + observability", "items": ["eng-01", "eng-02"]}
    ],
    "anchor_now":  {"name": "v2.5 brittle", "tagline": "no auth · gap-y observability"},
    "anchor_goal": {"name": "v3.0 ready", "tagline": "auth · observable · documented"}

    // For type: "maturity-ladder"
    // "levels": [{"num": 1, "name": "...", "tagline": "...", "items": [...]}, ...]
    // "anchor_bottom": {"name": "...", "tagline": "..."}
    // "anchor_top":    {"name": "...", "tagline": "..."}

    // For type: "hub-spoke"
    // "hub": {"name": "...", "tagline": "..."}
    // "spokes": [{"name": "...", "tagline": "...", "items": [...]}, ...]

    // For type: "before-after"
    // "before": {"name": "...", "bullets": ["...", "..."]}
    // "after":  {"name": "...", "bullets": ["...", "..."]}
    // "workstreams": [{"name": "...", "items": [...]}, ...]

    // For type: "pillars"
    // "roof": {"name": "..."}
    // "pillars": [{"name": "...", "tagline": "...", "items": [...]}, ...]
    // "foundation": {"name": "..."}
  }
}
```

## Field reference

### Top-level

- **`title`** (string, required) — Plan title shown in the page header `<h1>` and `<title>`.
- **`subtitle`** (string, optional) — Short tagline shown in the header meta line.
- **`meta`** (string, optional) — Custom meta line. Defaults to `"N sessions · M items"`.
- **`categories`** (array, required) — At least one category. Items must reference one.
- **`items`** (array, required) — Action items. Must have unique IDs. Categories must exist.
- **`sessions`** (array, required) — Sessions in execution order. Items referenced must exist.
- **`infographic`** (object, required) — One of the 5 plan-achievement template specs.

### Items

- **`id`** (string, required) — Unique. Convention: `cat-prefix-NN` (e.g., `eng-01`, `qw-01`). Lowercase.
- **`title`** (string, required)
- **`category`** (string, required) — Must match a `categories[].key`.
- **`description`** (string) — One paragraph max.
- **`why`** (string) — One sentence. Renders in italic with "Why:" prefix.
- **`owner`** (string)
- **`target`** (string) — ISO date or relative ("end of Q3").
- **`touches`** (string) — Files/areas, e.g. `"src/auth/*, README.md"`. Renders in `<code>`.
- **`priority`** (`"P0"|"P1"|"P2"|"P3"`) — Defaults to `"P3"`. Drives chip color.
- **`effort`** (`"S"|"M"|"L"|"XL"`) — Defaults to `"M"`. Free-form chip text.
- **`updated`** (ISO date string) — Defaults to today.

### Sessions

- **`id`** (string, required) — Convention: `sNN` (e.g., `s01`).
- **`title`** (string, required)
- **`model`** (`"Sonnet"|"Opus"`) — Defaults to `"Sonnet"`. Drives the model chip color.
- **`effort`** (string) — Free-form, e.g. `"~2h"`, `"half day"`.
- **`why_model`** (string) — One sentence rationale shown above the prompt.
- **`items`** (array of item IDs, required) — Items completed in this session.
- **`prompt`** (string, required) — The task body the user pastes into Cowork. The build script appends a structured CLOSEOUT block automatically. Don't include closeout instructions yourself.
- **`updated`** (ISO date string) — Defaults to today.

### Infographics

See `infographic-templates.md` for descriptions and which template fits which plan archetype.
