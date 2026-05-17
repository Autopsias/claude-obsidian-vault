# vault-framework

The foundation plugin — install this one first. The other four sub-plugins of
`claude-obsidian-vault` build on the kernel and the rule set this plugin
ships.

## What it ships

```
vault-framework/
├── .claude-plugin/plugin.json
├── commands/
│   ├── vault-setup.md            # Path-detecting scaffolder (A / B / C)
│   ├── hot.md                    # Refresh ≤2 KB orientation surface
│   └── promote.md                # 99 Workspace/ → typed zone ritual
├── skills/
│   └── project-setup/SKILL.md    # Substrate-aware interview + routing
├── rules/                        # 11 .claude/rules disciplines
│   ├── auto-write-discipline.md
│   ├── daily-notes-discipline.md
│   ├── freshness-discipline.md
│   ├── inbox-discipline.md
│   ├── ingestion-pipeline-discipline.md
│   ├── mount-discipline.md
│   ├── plugin-security-discipline.md
│   ├── retrieval-cascade-discipline.md
│   ├── session-bootstrap-discipline-flat.md
│   ├── session-bootstrap-discipline.md
│   └── state-moc-edit-discipline.md
├── templates/
│   ├── CLAUDE-template.md        # 24-var parameterised stable prefix
│   ├── operating-guide-template.md  # 9 universal P-rules + 4 ext slots
│   ├── retrieval-contract-template.md
│   ├── values.example.yaml       # Substitution values (de-Galpify exemplar)
│   ├── meeting.md / source.md / decision.md   # Entity templates
│   └── Bases/                    # 11 .base files + bases-verifier
└── scripts/
    ├── populate-claude-md.py     # YAML → CLAUDE.md substitution
    └── bases-verifier.py         # Frontmatter audit against Bases
```

## The three slash commands

### `/vault-setup`

Path-detecting scaffolder. Inspects the current folder and the user-scope
plugin install, then routes:

- **Path A** — Obsidian is present + folder has existing content
  → scaffolds onto the existing structure, retrofitting frontmatter rather
  than over-writing files.
- **Path B** — Obsidian is absent
  → emits the bootstrap shell prompt (Obsidian install + Smart Connections
  config + .obsidian directory creation), then resumes with scaffold-new.
- **Path C** — framework is installed at user-scope + a new (empty) folder
  → scaffold-new (substrate-aware: asks the three project-setup interview
  questions, then defers to the appropriate sub-skill).

### `/hot`

Refreshes `99 Workspace/_hot.md` — the ≤2 KB orientation surface read FIRST
at every session start, before `_session_handoff.md`. Contains: canonical
plan + progress counter, Up Next items, one in-flight risk, one open
question. Karpathy pattern: cheap to read; expensive when stale.

### `/promote`

Runs the P-10 promotion ritual: takes a file from `99 Workspace/` (the
auto-write zone), proposes a typed-zone destination based on its content,
applies the three-question quality filter, and on user approval moves the
file with full audit-log + cross-reference rewriting.

## The consolidated project-setup skill

Routes by (substrate × scenario) — five paths:

| Starting point | Substrate | → Route |
|---|---|---|
| New (greenfield) | Flat markdown | `cowork-preparation` (greenfield) |
| New | Obsidian (with install) | `obsidian-project-new` |
| New | Obsidian (no install) | bootstrap.sh prompt → `obsidian-project-new` |
| Existing flat-markdown | Flat markdown | `cowork-preparation` (port-existing) |
| Existing flat-markdown | Obsidian | `obsidian-project-convert` |
| Existing Obsidian | Obsidian | scaffold-on-existing (refuse downgrade) |
| Existing Obsidian | Flat markdown | refuse (substrate downgrade unsupported) |

The first four sub-skill paths are owned by `vault-framework`'s
project-setup; the fifth and sixth are explicit refusals with an explanation.

## The 11 rules

Each is path-gated — they auto-load only when Claude touches a matching
path. Key ones:

- `session-bootstrap-discipline.md` — the 8-step (Obsidian) session-start
  sequence; flat-markdown variant in the `-flat` file.
- `retrieval-cascade-discipline.md` — the 5-step cascade with Step −1
  temporal-intent routing matrix (Routes A/B/C/D).
- `auto-write-discipline.md` — the hash-chained Ed25519-signed log; what
  Claude is allowed to write without explicit user approval.
- `mount-discipline.md` — the hard-stop rule against routing writes to a
  wrong mount.

## The operating-guide-template

Nine universal P-rules (kernel v1.2) — stable-prefix discipline, retrieval
cascade, bitemporal versioning, voice/tone, autonomy boundary, P-promotion
ritual, eval cadence, inbox triage, ingestion. Plus four extension slots
(`EXT-2` / `EXT-5` / `EXT-9` / `EXT-13`) the project must fill: state MOC
schema, session lifecycle specifics, lifecycle triggers, substrate-review
cadence.

## How it composes with the other four plugins

`vault-framework` is the dependency every other plugin assumes. Install it
first; the others will reference its rules and templates.

- `vault-skills` — runs kb-curator/plan-builder etc. _against_ a vault
  scaffolded by this plugin.
- `vault-eval` — its 33-question eval template is shaped against the
  cascade defined in this plugin's `retrieval-cascade-discipline.md`.
- `vault-ingestion` — writes through this plugin's `inbox-discipline.md`
  and `auto-write-discipline.md`.
- `vault-voice` — auto-loads via `.claude/rules/voice-discipline.md` (which
  ships in that plugin); reads from the corpus seeded by /vault-setup.

## Version

`0.1.0` — initial extraction; see `CHANGELOG.md` upstream when present.
