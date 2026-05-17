# vault-voice

The personal-voice layer. Auto-loads on document-generation paths so any
draft Claude writes under your name carries your DNA, not Claude's.

## What it ships

```
vault-voice/
├── .claude-plugin/plugin.json
├── skills/vault-voice/SKILL.md
├── rules/
│   └── voice-discipline.md           # Auto-load on document-gen paths
├── templates/
│   ├── voice-profile-template.md     # Layer A — user-specific voice DNA
│   └── writing-craft-template.md     # Layer B — universal cross-language craft
└── scripts/
    └── populate-voice-profile.py     # Corpus → populated voice-profile.md
```

## The two-layer model

| Layer | Source | Scope |
|---|---|---|
| **A — Voice** | `_voice_profile.md` (user-specific) | Personal DNA: openers, closers, hedge patterns, sample-grounded patterns, anti-patterns from a real corpus |
| **B — Craft** | `_writing_craft.md` (universal) | Pyramid Principle (Minto), BLUF, SCQA, clarity rules, discourse construction. Cross-language (EN/PT/ES with adjustments) |

Both layers fire on every audience-facing draft. Voice = authentic user.
Craft = clear, structured, well-constructed prose. They compound; the
output is high-quality professional prose that is authentically the user
AND well-crafted AND does NOT read as AI-generated.

## Install + populate

1. Install `vault-framework` first (this plugin uses its `.claude/rules/`
   auto-load infrastructure).
2. `cp templates/voice-profile-template.md <vault>/90 System/_voice_profile.md`
3. `cp templates/writing-craft-template.md <vault>/90 System/_writing_craft.md`
4. `cp rules/voice-discipline.md <vault>/.claude/rules/voice-discipline.md`
5. **Populate Layer A.** Collect 5,000+ words of your authored prose
   (sent emails, memos, board material) into a `_voice_corpus/` folder.
   Then run:

   ```
   python scripts/populate-voice-profile.py \
       --corpus <vault>/90 System/_voice_corpus/ \
       --template templates/voice-profile-template.md \
       --output <vault>/90 System/_voice_profile.md
   ```

   The script computes corpus statistics (avg sentence length, common
   openers, em-dash density, sign-off repertoire, bullet usage, register
   markers) and surfaces them as suggestions for the template's
   parameterised sections. You review and edit. The output is a profile
   calibrated to your actual writing.

6. **Verify with a roundtrip.** Pick a 200-word sample from your corpus,
   delete it from the corpus folder, then ask Claude to draft a similar
   message. Compare. Iterate the profile.

## When the rule fires

The `voice-discipline.md` rule auto-loads on these paths:
- `00 Inbox/**/*.docx`, `*.pptx`, `*.md` (when drafting)
- `99 Workspace/_skill_packages/**/*` (when working inside the vault)

And on trigger phrases like "draft an email", "stakeholder update",
"in my voice", "communication to <X>".

It does NOT fire on:
- Audit reports, technical specifications, debriefs
- Raw transcripts or quoted material
- Documents Claude is reading, not authoring

## Composition

- `vault-framework`'s document-generation paths (docx/pptx/memo skills)
  auto-load voice-discipline.
- `vault-skills/save-conversation` checks Layer B (craft) when promoting
  prose to typed zones.
- Multi-language vault setups inherit the M9 caveat from
  `_operating_guide.md`.

## Version

`0.1.0` — initial extraction. Layer A is template-only (no shipped
profile); Layer B ships as a universal craft kernel. The populate script
is stdlib-only.
