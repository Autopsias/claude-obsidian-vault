---
name: vault-voice
description: Personal-voice layer for any draft Claude writes under the user's name — auto-loads voice-profile.md (Layer A user-specific) + writing-craft.md (Layer B universal) on document-generation paths. Triggers on "draft an email", "write a memo", "stakeholder update", "in my voice", "draft this for me", "briefing", "communication to <X>", or any audience-facing prose under the user's name. Do NOT apply to vault-internal artefacts (audit reports, tech specs), raw transcripts, or documents the user is reading rather than authoring.
---

# vault-voice

The runtime layer. When this skill fires, Claude has loaded the user's
voice profile and the universal writing craft kernel, and is ready to
draft.

## Three modes

### DRAFT mode (default)

Trigger: "draft an email", "write a memo", "draft this for me", "in my
voice", "stakeholder update", "briefing".

Action: Claude reads the user's rough notes / bullet points / dictation,
applies both layers (voice profile + writing craft), produces a finished
draft.

### REWRITE mode

Trigger: "rewrite this in my voice", "voicify this", "make this sound like
me", "clean this up in my voice", "fix this email's tone".

Action: Claude takes an existing draft (written by someone else, an AI,
or the user in a hurry), rewrites in the user's voice + craft layers,
returns the rewritten version PLUS an annotated diff showing what changed
and why.

### CHECK mode

Trigger: "check this draft", "is this in my voice", "voice check", "scan
for AI tells".

Action: Claude scans an existing draft and reports voice-profile + craft
violations WITHOUT rewriting. The user fixes them or asks Claude to
proceed to REWRITE.

## Pre-ship checklist (25 items)

Per `voice-discipline.md`, after every draft Claude must run a 25-item
compound checklist:

- **15 voice checks** from `_voice_profile.md §8` (DNA-specific):
  openers / closers / hedge-then-commit / register / sample-grounded
  pattern / anti-patterns / typo conventions / sign-off repertoire
- **10 craft checks** from `_writing_craft.md §8` (universal):
  Pyramid Principle (top-down ordering) / BLUF (bottom line up front) /
  SCQA / active voice / SVO close / sentence length / paragraph length /
  reader-respect / clarity / discourse construction

If any fail, revise. If you cannot make all pass without distorting
meaning, surface the conflict to the user.

## Cite divergences

If you deliberately depart from a rule, call it out:

> "I'm using `Warm regards,` because the recipient explicitly asked for a
> warmer close last week. Profile says never use it; flagging the
> divergence for awareness."

Silent drift corrupts both layers.

## When NOT to apply

- Vault-internal artefacts (audit reports, tech specs, debriefs)
- Raw transcripts or quoted material
- Documents the user is reading, not authoring
- Machine-readable artefacts (JSON, YAML, Python)
- Direct quotes from another person

## Files

- `rules/voice-discipline.md` — path-gated auto-load (lifted into
  `.claude/rules/` on install)
- `templates/voice-profile-template.md` — Layer A scaffold (user
  populates from their corpus via the populate script)
- `templates/writing-craft-template.md` — Layer B universal kernel
  (lifted into `90 System/_writing_craft.md` as-is)
- `../../scripts/populate-voice-profile.py` — corpus extractor
