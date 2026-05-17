# Example Plan Specs

Five small reference specs, one per infographic template. Use these as starting points when interviewing a user — paste the relevant one, swap in their plan's content.

Each example is a complete, valid spec that the build script will accept.

## Example 1 — Phase Journey (product launch)

See `../../plan-builder-workspace/test-spec.json` (if present) for a full Q4-product-launch plan: 5 sessions, 9 items, 4-phase journey from v2.5 to v3.0.

**Use phase-journey when:** the work is sequential and unlocks downstream work (spike → build → pilot → roll-out).

## Example 2 — Maturity Ladder (observability climb)

```json
{
  "title": "Observability Maturity — Ad-hoc to Continuous",
  "subtitle": "12-week climb across four maturity levels",
  "categories": [
    {"key": "logs",    "label": "Logs"},
    {"key": "metrics", "label": "Metrics"},
    {"key": "traces",  "label": "Traces"},
    {"key": "auto",    "label": "Automation"}
  ],
  "items": [
    {"id": "logs-01", "title": "Adopt structured JSON logs", "category": "logs",    "priority": "P0", "effort": "M"},
    {"id": "logs-02", "title": "Centralize via Loki",        "category": "logs",    "priority": "P1", "effort": "M"},
    {"id": "met-01",  "title": "Wire Prometheus + RED",      "category": "metrics", "priority": "P1", "effort": "L"},
    {"id": "met-02",  "title": "Define service SLOs",        "category": "metrics", "priority": "P1", "effort": "M"},
    {"id": "tr-01",   "title": "Deploy OpenTelemetry",       "category": "traces",  "priority": "P1", "effort": "L"},
    {"id": "tr-02",   "title": "Per-endpoint trace sampling","category": "traces",  "priority": "P2", "effort": "S"},
    {"id": "auto-01", "title": "Auto-rollback on SLO burn",  "category": "auto",    "priority": "P1", "effort": "L"},
    {"id": "auto-02", "title": "Predictive anomaly alerts",  "category": "auto",    "priority": "P2", "effort": "L"}
  ],
  "sessions": [
    {"id": "s01", "title": "Logs foundation",          "model": "Sonnet", "items": ["logs-01", "logs-02"],            "prompt": "..."},
    {"id": "s02", "title": "Metrics + SLOs",           "model": "Sonnet", "items": ["met-01", "met-02"],              "prompt": "..."},
    {"id": "s03", "title": "Tracing rollout",          "model": "Sonnet", "items": ["tr-01", "tr-02"],                "prompt": "..."},
    {"id": "s04", "title": "Automation + alerting",    "model": "Opus",   "items": ["auto-01", "auto-02"],            "prompt": "..."}
  ],
  "infographic": {
    "type": "maturity-ladder",
    "title": "Climbing from <em>ad-hoc</em> to <em>continuous</em>",
    "narrative": "...",
    "levels": [
      {"num": 1, "name": "Ad-hoc",     "tagline": "manual logs only",      "items": ["logs-01"]},
      {"num": 2, "name": "Repeatable", "tagline": "centralized + indexed", "items": ["logs-02", "met-01"]},
      {"num": 3, "name": "Defined",    "tagline": "SLOs + tracing",        "items": ["met-02", "tr-01", "tr-02"]},
      {"num": 4, "name": "Continuous", "tagline": "auto-remediation",      "items": ["auto-01", "auto-02"]}
    ],
    "anchor_bottom": {"name": "Today",      "tagline": "manual ops"},
    "anchor_top":    {"name": "Continuous", "tagline": "self-healing"}
  }
}
```

## Example 3 — Hub & Spoke (cross-team launch)

Skeleton shown — fill in items and prompts:

```json
{
  "title": "v3.0 Cross-Team Launch",
  "infographic": {
    "type": "hub-spoke",
    "title": "Five workstreams converging on <em>v3.0</em>",
    "hub":    {"name": "v3.0 ship", "tagline": "Q3 close · all teams green"},
    "spokes": [
      {"name": "Backend",  "tagline": "auth + perf",   "items": ["be-01", "be-02"]},
      {"name": "Frontend", "tagline": "redesign",      "items": ["fe-01", "fe-02", "fe-03"]},
      {"name": "Mobile",   "tagline": "iOS + Android", "items": ["mo-01", "mo-02"]},
      {"name": "DevOps",   "tagline": "k8s migration", "items": ["op-01"]},
      {"name": "Docs",     "tagline": "API + guides",  "items": ["doc-01", "doc-02"]}
    ]
  }
}
```

## Example 4 — Before/After (monolith → services)

```json
{
  "title": "Monolith to Services Migration",
  "infographic": {
    "type": "before-after",
    "title": "Migrating from <em>monolith</em> to <em>service mesh</em>",
    "before": {
      "name": "Monolith (today)",
      "bullets": ["Single deployable", "Shared database", "30-min deploys", "Coupled team velocity"]
    },
    "after": {
      "name": "Service mesh (target)",
      "bullets": ["8 deployable services", "Service-owned data", "<5-min deploys", "Independent team velocity"]
    },
    "workstreams": [
      {"name": "Extract auth service",       "items": ["m-01", "m-02"]},
      {"name": "Extract billing",            "items": ["m-03", "m-04"]},
      {"name": "Database split",             "items": ["m-05", "m-06"]}
    ]
  }
}
```

## Example 5 — Pillars (engineering culture)

```json
{
  "title": "Building Defensible Engineering Culture",
  "infographic": {
    "type": "pillars",
    "title": "Building <em>defensible engineering culture</em> on four pillars",
    "roof":       {"name": "Defensible engineering culture"},
    "pillars": [
      {"name": "Code review",     "tagline": "every PR",         "items": ["cul-01", "cul-02"]},
      {"name": "Testing",         "tagline": "coverage > 80%",   "items": ["cul-03", "cul-04"]},
      {"name": "Postmortems",     "tagline": "blameless",        "items": ["cul-05"]},
      {"name": "Documentation",   "tagline": "decision records", "items": ["cul-06", "cul-07"]}
    ],
    "foundation": {"name": "Existing process + people"}
  }
}
```

## Choosing between templates — quick decision guide

1. Does the plan have **distinct sequential phases** (spike → build → roll-out)? → **phase-journey**
2. Does it describe a **maturity climb** (manual → automated, ad-hoc → continuous)? → **maturity-ladder**
3. Are there **multiple parallel teams** converging on one outcome? → **hub-spoke**
4. Is it explicitly a **transformation** with bullets contrasting before/after? → **before-after**
5. Does the plan rest on **N foundational workstreams** that together support a goal? → **pillars**

When unsure, **phase-journey** is the safe default — it accommodates most plans.
