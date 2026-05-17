---
paths:
  - "99 Workspace/_skill_packages/**/*"
  - "00 Inbox/**/*.docx"
  - "00 Inbox/**/*.pptx"
  - "00 Inbox/**/*.md"
triggers:
  - "writing a memo"
  - "draft an email"
  - "draft a message"
  - "write up"
  - "draft this for me"
  - "in my voice"
  - "stakeholder update"
  - "briefing"
  - "communication to"
  - "rewrite in my voice"
  - "voicify"
  - "make this sound like me"
  - "voice check"
skills_in_scope:
  - "docx"
  - "pptx"
  - "amazon-memo-writer:write-memo"
  - "product-management:stakeholder-update"
  - "legal:respond"
  - "design:ux-copy"
---

# Voice discipline

Two compounding sources of truth:

- **Layer A — Voice (user-specific):** `90 System/_voice_profile.md` — the
  user's authored DNA: openers, closers, hedge-then-commit, sample-grounded
  patterns, anti-patterns. Calibrated from a real corpus of the user's
  prose; population is via `populate-voice-profile.py`.
- **Layer B — Craft (universal, cross-language):** `90 System/_writing_craft.md`
  — Pyramid Principle (Minto), BLUF, SCQA, plain-language clarity rules,
  discourse construction. Works for EN / PT / ES / other languages with
  documented adjustments.

Both layers fire on every audience-facing draft. Voice = authentic user.
Craft = clear, structured, well-constructed prose. They compound.

## When this rule fires

This rule applies whenever Claude is drafting **audience-facing prose for
the user to send or deliver** — emails, memos, stakeholder updates, board
material, presentation copy, Slack messages, talking points.

It does NOT apply to:

- Vault-internal artefacts: audit reports, technical specifications,
  debrief summaries, eval reports, machine-readable artefacts (JSON / YAML
  / Python).
- Raw transcripts or quoted material (preserve as-is).
- Documents the user is reading, not authoring (research summaries,
  briefing-IN material).

If in doubt, ask: *is the user going to put their name on this and send it
to a human reader?* If yes, apply this rule. If no, don't.

## Four load-bearing rules

1. **Load BOTH layers before drafting.** Read `90 System/_voice_profile.md`
   AND `90 System/_writing_craft.md` first. Do not work from memory — the
   phrase libraries, anti-patterns, structural frameworks, and compound
   checklist are the load-bearing parts.

2. **Use the matching curated samples.** If the user has a
   `_voice_corpus/` folder with annotated samples, load 1-2 that match the
   draft's language, length, audience, and pattern (acknowledge-pivot-
   assert / self-correction / sharp pushback / strategic argument). The
   explicit anti-example (a sample of what NOT to do) is especially useful.

3. **Run the pre-ship checklist before delivering.** Voice-DNA checks from
   `_voice_profile.md §8` + craft checks from `_writing_craft.md §8`. If
   any fail, revise. If you cannot make all pass without distorting
   meaning, surface to the user with the conflict explained.

4. **Cite divergences from either layer.** If you deliberately depart from
   a rule, call it out in the response. Silent drift corrupts both layers.

## Language-specific notes

Apply both layers in any language. If `_voice_profile.md` has language-
specific sections (e.g. PT phrase library, EN openers), load the matching
one. If `_writing_craft.md` has cross-language adjustments (active-voice
tolerance varies by language, sentence-length norms vary), apply them.

If the project's primary language is non-English and the voice profile has
not been calibrated for that language yet, surface this as a known gap and
proceed with universal craft (Layer B) + best-effort voice (Layer A).

## When this rule is wrong

If the rule fires on something that shouldn't be voice-tuned (e.g. you're
quoting another person verbatim, or you're writing a JSON config file
that happens to live in a path that matches), surface this and stop —
the rule is path-gated and trigger-matched, but the path/trigger heuristic
isn't perfect. The user's intent wins.
