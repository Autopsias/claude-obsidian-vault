---
type: system
title: "{{USER_NAME}} — voice profile (template, awaiting population)"
created: "{{DATE}}"
updated: "{{DATE}}"
version: v0.1
freshness: "monthly-or-on-structural-change"
provenance: "Template scaffold. Populate via populate-voice-profile.py from a corpus of {{USER_NAME}}-authored prose (target: ≥5,000 words across ≥10 documents, spanning ≥2 years to capture stable voice DNA)."
related: ["_writing_craft.md", "_voice_corpus/_analysis.md", ".claude/rules/voice-discipline.md"]
compounds_with: "_writing_craft.md — universal cross-language writing craft. Voice is user-specific; craft is universal. Both layers fire on every audience-facing draft per .claude/rules/voice-discipline.md."
applies_to: "Any document Claude drafts for {{USER_NAME}} — memos, emails, board material, Slack messages, presentations, stakeholder communications."
do_not_apply_to: "Audit reports, technical specifications, raw transcripts, machine-readable artefacts."
---

# Voice profile — {{USER_NAME}} (template)

**Critical framing.** This profile is **Layer A** of a two-layer writing
system. It captures *how {{USER_NAME}} writes* — their quirks, sign-offs,
hedge-then-commit, sample-grounded patterns. **Layer B** is
`90 System/_writing_craft.md` — universal cross-language craft (Pyramid
Principle, BLUF, SCQA, storytelling, clarity rules, discourse
construction). Both layers compound and BOTH fire on every audience-facing
draft via `.claude/rules/voice-discipline.md`.

**Calibration base for this layer:** [POPULATE — corpus size + date span +
languages]. The target is the **stable {{USER_NAME}} voice**.

## 1. Voice DNA — single paragraph

[POPULATE — one paragraph capturing the user's voice in the abstract. From
corpus analysis: typical register, causal scaffolding, anecdote use,
hedge-then-commit, career-as-evidence patterns. Example structure: "Direct,
[descriptor], [descriptor]. Sharp judgments wrapped in mild softener —
[example phrases]. [Subject-matter patterns]. Hedge-then-commit. Career-
as-evidence — [user's specific reference patterns]. Conversational register
even in formal settings."]

## 2. Non-negotiable rules

[POPULATE — 5-15 hard rules from corpus analysis. Examples:]
- 2.1. Never "[banned phrase]" — corpus shows zero instances.
- 2.2. Sign-off repertoire: [list from corpus] — NEVER use [outlier].
- 2.3. Em-dash density: [N per 1000 words from corpus]. Above that = AI-tell.
- 2.4. Hedge then commit: [example pattern from corpus].
- 2.5. Sentence length: avg [N] words; cap [M] words.
- 2.6. [User-specific typo conventions, e.g.: "Off course" → "Of course"]
- 2.7. [Etc — drawn from corpus, not guessed]

## 3. Openers — what {{USER_NAME}} typically writes at the top

[POPULATE — list of openers from corpus, with frequency. Example:]
- "[opener 1]" — N occurrences
- "[opener 2]" — N occurrences
- "[opener 3]" — N occurrences

For different audiences: [matrix of audience × opener pattern].

## 4. Rhetorical pivots and frames

[POPULATE — the user's typical mid-paragraph pivots. Example:]
- "I do understand that..." — used to acknowledge before pivoting
- "What I would say is..." — used to assert after acknowledging
- "Having said that..." — used to soften an assertion before the next claim
- [Etc, all drawn from corpus]

## 5. Structural arcs typical of the user

[POPULATE — common patterns. Example:]
- **Acknowledge-pivot-assert** — used for pushback emails
- **Self-correction** — used when reversing a prior position
- **Sharp argument** — used for board / Co-CEO communications
- **Strategic walk-through** — used for stakeholder updates

## 6. Anti-patterns — what to AVOID

[POPULATE — what the user does NOT write. Examples from a real calibration:]
- "Warm regards," — corpus shows zero; AI-tell
- Symmetric N-bullet / N-bullet structures — AI artefact
- "I very much value the relationship" — generic AI fluff
- "Looking ahead, I remain very open to..." — vacant tail
- "Thoughtful and professional process" — AI buzz

## 7. Format guidance by document type

[POPULATE — different formats for different documents:]
- **Short reply (< 100 words):** [pattern]
- **Argumentative email (200-500 words):** [pattern]
- **Memo (500-2000 words):** [pattern]
- **Stakeholder update / board talking points:** [pattern]
- **Slack message:** [pattern]

## 8. Pre-ship voice checklist (15 items)

[POPULATE — drawn from the rules above. Examples:]
- [ ] No banned phrases? (rule §2.1)
- [ ] Sign-off matches repertoire (§2.2)
- [ ] Em-dash density within budget (§2.3)
- [ ] At least one hedge-then-commit (§2.4)
- [ ] Avg sentence length within bound (§2.5)
- [ ] No AI-tell phrases (§6)
- [ ] Format matches document type (§7)
- [ ] [User-specific check]
- [ ] [...]

## 9. Calibration loop

When the profile drifts (the user flags a miss; Claude produces drafts
that need correction): add the failed pattern to `_voice_corpus/miss_log.md`
with the rewrite the user made. After ≥5 logged misses, re-run
`populate-voice-profile.py --update` to refresh the rules.

Triggers for v0.2+ refresh:
- ≥5 logged misses in `miss_log.md`
- New audience class encountered (e.g. new C-suite peer)
- New language added to corpus
- ≥1 year elapsed since last calibration

## 10. Language-specific sections

[POPULATE per language if the corpus is multilingual. Examples:]

### EN

[Phrases, openers, register adjustments specific to English.]

### PT

[Phrases, openers, register adjustments specific to Portuguese. Use of
"vossa", "Atentamente", informal/abbreviated PT contexts.]

### ES

[Phrases, openers, register adjustments specific to Spanish.]

## 11. Curated sample references

[POPULATE — pointers into `_voice_corpus/` showing examples to emulate or
avoid. Example:]
- Sample 01 (`_voice_corpus/01_pushback_en.md`) — acknowledge-pivot-assert
  exemplar
- Sample 02 (`_voice_corpus/02_strategic_pt.md`) — strategic argument PT
- Sample 07 (`_voice_corpus/07_ai_polished_anti.md`) — **ANTI-EXAMPLE**
  what to calibrate AWAY from

## 12. Voice stability finding

[POPULATE — does the corpus show stable voice across time / organisations
/ languages? If yes, note explicitly. The stable voice is the target;
date-specific or org-specific patterns are noise.]

---

## How to populate this template

```bash
# 1. Collect ≥5,000 words of authored prose in _voice_corpus/
# 2. Run the extractor
python scripts/populate-voice-profile.py \
    --corpus _voice_corpus/ \
    --template voice-profile-template.md \
    --output _voice_profile.md \
    --user-name "<Your Name>"

# 3. Review the extracted statistics + suggestions
# 4. Hand-edit the [POPULATE — ...] sections with judgment, not just stats
# 5. Run a roundtrip test: pick a 200-word sample, delete it, ask Claude to
#    draft something similar, compare
```
