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
    {"id": "s01", "title": "Logs foundation",       "model": "Sonnet 4.6", "thinking": "Medium", "items": ["logs-01", "logs-02"], "why_model": "Well-scoped setup work — Sonnet 4.6 at Medium is the cost-efficient fit.", "prompt": "..."},
    {"id": "s02", "title": "Metrics + SLOs",        "model": "Opus 4.8",   "thinking": "High",   "items": ["met-01", "met-02"],   "why_model": "SLO design needs judgement about what to measure — Opus 4.8 at High.", "prompt": "..."},
    {"id": "s03", "title": "Tracing rollout",       "model": "Opus 4.8",   "thinking": "Extra",  "items": ["tr-01", "tr-02"],     "why_model": "Cross-service instrumentation with heavy tool-calling — Extra for agentic depth.", "prompt": "..."},
    {"id": "s04", "title": "Automation + alerting", "model": "Opus 4.8",   "thinking": "Max",    "items": ["auto-01", "auto-02"], "why_model": "Auto-rollback logic is high-stakes and easy to get subtly wrong — Max.", "prompt": "..."}
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

## Aurora edition — dual-layer item + session example

Demonstrates the dual-layer fields (`human_summary`, `deliverable`, `agent_instructions`, `schema`, `code`) plus the per-session `model` + `thinking` pair and a combined `why_model`. Drop these into any item or session in an existing spec; they all degrade gracefully if omitted.

```json
{
  "items": [
    {
      "id": "be-01",
      "title": "Add invite-by-email endpoint",
      "category": "backend",
      "priority": "P1",
      "effort": "M",
      "human_summary": "Admins can email a teammate an invite link instead of doing the create-user-and-share-password dance. Cuts onboarding from 10 minutes to one click.",
      "deliverable": "POST /api/v1/invites returns a token-bearing magic link; recipient lands on /accept-invite which provisions the account.",
      "why": "Manual user creation is the #1 onboarding complaint in NPS verbatims.",
      "owner": "Backend",
      "target": "End of Q3",
      "touches": "services/auth/invites.go, web/pages/accept-invite.tsx, db/migrations/0042_invites.sql",
      "agent_instructions": [
        "Add the migration for the invites table per the schema below.",
        "Implement POST /api/v1/invites returning 201 with {token, expires_at}.",
        "Wire a worker that emails the magic link via SendGrid (template ID INV-001).",
        "Add /accept-invite page that exchanges token for session and redirects to /dashboard."
      ],
      "schema": {
        "lang": "sql",
        "code": "CREATE TABLE invites (\n  id            UUID PRIMARY KEY,\n  inviter_id    UUID NOT NULL REFERENCES users(id),\n  email         CITEXT NOT NULL,\n  token         TEXT NOT NULL UNIQUE,\n  expires_at    TIMESTAMPTZ NOT NULL,\n  accepted_at   TIMESTAMPTZ,\n  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()\n);\nCREATE INDEX idx_invites_token ON invites(token);"
      },
      "code": {
        "lang": "ts",
        "code": "interface InviteResponse {\n  token: string;\n  expires_at: string;  // ISO 8601\n  invite_url: string;  // e.g. https://app.example.com/accept-invite?t=...\n}"
      }
    }
  ],
  "sessions": [
    {
      "id": "s04",
      "title": "Invite flow end-to-end",
      "model": "Sonnet 4.6",
      "thinking": "Medium",
      "effort": "~3h",
      "items": ["be-01", "fe-01"],
      "human_summary": "Stand up the invite-by-email flow end-to-end. Admins click 'Invite' in the dashboard, type an email, the teammate gets a link, clicks it, lands inside.",
      "deliverable": "A real admin can invite a real teammate and watch them join the workspace. CI passes; staging demo recorded.",
      "why_model": "Mechanical CRUD + template wiring — well-defined, so Sonnet 4.6 at Medium effort is the cost-efficient fit.",
      "prompt": "Execute SESSION S04 — Invite flow end-to-end.\n\nItems: BE-01 (backend endpoint + table) and FE-01 (frontend dashboard button + accept page).\n\n1. Run the migration in db/migrations/0042_invites.sql.\n2. Implement BE-01 following its agent_instructions and schema.\n3. Implement FE-01: add the 'Invite teammate' modal to the admin dashboard, build the /accept-invite page.\n4. Add an integration test that drives the full flow with a real email captured by mailhog in CI.\n5. Record a 30-second screencast for the staging demo channel."
    }
  ]
}
```

Notice that the **prompt body** doesn't repeat the schema or the dev-step bullets — those live in the items' `agent_instructions` / `schema` / `code` fields, which the executing Claude can read by opening the item articles in the same HTML file. This keeps the prompt focused on session-level orchestration and lets the per-item detail sit next to its item.

For per-session **model + thinking-effort** choices, see `model-effort-guidance.md`. Every session above sets a `model` + `thinking` pair the user dials into the Cowork picker before pasting, and explains the pair in one sentence in `why_model`.
