---
name: save-conversation
description: "Promote a valuable mid-conversation analysis, snippet, or decision into a typed vault note. Take the current chat content, auto-classify the destination zone (60 Concepts, 50 Sources/_analysis, 70 Decisions, 10 People, 20 Companies, or 00 Inbox when uncertain), apply the P-10 three-question quality filter, propose title and frontmatter, present one accept/reject/edit question, and on approval write the file and log it. Trigger phrases — '/save', '/save [title]', 'save this', 'save this to the vault', 'save this conversation', 'save this analysis', 'promote this to [zone]', 'capture this in the vault', 'this is worth keeping'. Use whenever a substantive analysis surfaces in chat that Ricardo will want to find again — Karpathy: good answers shouldn't disappear into chat history. Do NOT use for P-10 promotion of an existing 99 Workspace file (use the promote skill), kb maintenance or audits (kb-curator), execution-work tracking (plan-builder), or systemic improvements / lessons (kb-curator promote-lesson)."
---

# save-conversation

Turns a valuable chat turn — analysis, decision rationale, concept explanation, person-fact, snippet — into a properly-typed vault note. One-shot interaction: auto-classify → quality-filter → propose → write → log.

**Built for the gap between three existing rituals:**

- `promote` skill — promotes an existing `99 Workspace/` file to a typed zone. Requires the file to already exist.
- `kb-curator promote-lesson` — promotes a systemic improvement (rule, pattern, lesson) to `_lessons.md`.
- `plan-builder` — multi-session execution work.

`/save` covers the remaining case: **a useful artefact lives only in chat history, not in a file**. Without this skill it evaporates when the session closes.

---

## Phase 0 — content selection

What gets saved is the **substantive answer immediately preceding the `/save` trigger** — typically Claude's most recent assistant turn, or a specific block Ricardo points to.

If Ricardo says `/save` with no argument: save the most recent Claude turn that contains analysis-worthy content (not a clarification question, not a short acknowledgement).

If Ricardo says `/save <title>`: same selection, but use `<title>` as the seed for the filename / `name:` frontmatter field.

If Ricardo says `save the part about <X>` or `save this analysis on <Y>`: scan recent turns for the topic and extract that block.

If selection is ambiguous (multiple plausible blocks), ask **one** clarifying question: "Save the block about *<topic-A>* or *<topic-B>*?"

---

## Phase 1 — auto-classify the destination zone (FN-10)

Score the selected content against the zone heuristics below. Pick the highest-scoring zone. **If two zones tie, or if the top score is weak, jump straight to Phase 3 (low-confidence → Inbox).**

### Zone heuristics

| Signals | Target zone | Default `type:` |
|---|---|---|
| Algorithm, pattern, framework, principle, named concept ("the X rule"), "how X works", architecture explanation, conceptual definition, ≥1 wikilink to existing `60 Concepts/` page | `60 Concepts/` | `concept` |
| Audit, analysis, comparison, gap study, framework review, market scan, competitive read, research synthesis, deep-dive on a topic | `50 Sources/_analysis/` | `analysis` |
| "We decided", "Ricardo chose", "the call is", "agreed to", "approved", explicit rationale + accept/reject framing, anything that closes a question | `70 Decisions/` | `decision` |
| Biography, role description, background on a named person, "who is X", relationship map, stakeholder profile | `10 People/<Name>.md` | `person` |
| Company description, what they do, how they're structured, named org background | `20 Companies/<Name>.md` | `company` |
| Meeting debrief, attendees + notes + actions, "in the meeting", "the call covered" | `40 Meetings/<YYYY-MM-DD>_<slug>.md` | `meeting` |
| Anything else, OR multiple zones plausible, OR confidence weak | `00 Inbox/` | `inbox` |

### Strong vs weak signal

- **Strong** — the content uses the zone's signature vocabulary in a structurally appropriate way (e.g., a `70 Decisions/` candidate has both an explicit decision verb and a reasoned rationale).
- **Weak** — the zone matches one keyword but the rest of the content drifts elsewhere (e.g., an analysis that mentions "we decided X" in one paragraph but is otherwise a comparative scan → still `50 Sources/_analysis/`, not `70 Decisions/`).

When in doubt, the **default is `00 Inbox/`** (FN-12). Wrong-zone placement is hard to fix once Bases queries assume zone correctness; Inbox is the right uncertainty-sink.

### Special routing rules

- If the chat content is a Cowork-session retrospective, hand off to the canonical `improve` skill instead — do not save as `50 Sources/_analysis/`.
- If the content is a systemic rule / pattern / lesson distilled from session experience, hand off to `kb-curator promote-lesson` — do not save as `60 Concepts/`.
- If the content is a multi-session plan, hand off to `plan-builder` — do not save as `00 Inbox/`.
- Surface these handoffs to Ricardo as: "*This looks more like a <X> than a <save> — want to invoke `<skill>` instead?*"

---

## Phase 2 — apply the P-10 three-question quality filter (FN-11)

Before writing to a **typed** zone (10 / 20 / 40 / 50 / 60 / 70), run the filter from `90 System/_promotion_quality_guide.md`. **Skip the filter for Inbox writes — Inbox is the triage zone, no quality bar.**

Answer all three honestly before asking Ricardo:

1. **Is this still true?** Cross-check against `30 Projects/Peninsula.md` and the most recent debrief in `40 Meetings/`. If the content is contradicted or stale, flag it — do not silently downgrade.
2. **Will this affect tomorrow's decisions?** If the content is a one-shot fact lookup, a casual aside, or a recap of something already documented, the honest answer is no.
3. **Is this encoded elsewhere?** Grep / Smart Connections lookup for substantially identical content. If a typed-zone note already covers it, surface the existing path and ask: merge, supersede, or skip.

### On filter failure

If **any** answer is "no, archive instead" or "duplicate":
- **Default route → `00 Inbox/` with `type: inbox`.** Let Ricardo triage on next session.
- Note the filter outcome in the proposal preamble (one sentence — "P-10 Q2 failed: this is a recap of `40 Meetings/2026-05-12_susana.md` — routing to Inbox").
- Do **not** silently switch zones without telling Ricardo.

This is FN-11: the P-10 filter never blocks a save outright — it downgrades typed-zone routing to Inbox. Ricardo can still override on the Modify branch of the AskUserQuestion.

---

## Phase 3 — confidence check (FN-12 — low-confidence → Inbox)

Even when zone heuristics + P-10 both pass, route to **Inbox** if any of these uncertainty signals fire:

| Signal | Rationale |
|---|---|
| Two zones tied for top score in Phase 1 | Wrong-zone placement is hard to fix; Inbox is the safe default |
| Ricardo's most recent message contains: "maybe", "not sure", "could be", "I think", "perhaps", "talvez", "não tenho a certeza" | Explicit verbal uncertainty — Ricardo isn't ready to codify yet |
| Content is < 200 words AND not a `70 Decisions/` candidate | Probably not "lasting value" — Inbox triage will catch it if it grows |
| Phase 1 picked `10 People/` or `20 Companies/` but no clear entity name appears in the content | Routing assumes a specific stem; ambiguous match → Inbox |
| The chat thread is exploratory ("let's brainstorm", "what if", "kicking around ideas") rather than concluded | Premature codification = typed-zone churn |
| P-10 filter answered "no" to **any** of the three questions (Phase 2) | Already covered above; restated here for completeness |

When routing to Inbox under low confidence, populate frontmatter with `type: inbox` and `confidence: 0.2` (per the `_operating_guide.md` P-4 confidence rubric: 0.2 = speculation). Mention the trigger signal in the proposal preamble.

---

## Phase 4 — propose title + frontmatter

### Title

- Use `<title>` if Ricardo passed one with the trigger.
- Otherwise distill the first 60 chars of a one-line summary of the content.
- For dated artefacts (decisions, meetings, analyses), prefix with `YYYY-MM-DD_`.
- Slug: lowercase, underscores, no spaces.

### Frontmatter contract

All zones get the minimum block:

```yaml
---
name: <human-readable name>
description: <one sentence — used by retrieval to disambiguate>
type: <inbox|concept|analysis|decision|person|company|meeting>
last_updated: YYYY-MM-DD
document_date: YYYY-MM-DD
provenance: "Saved from chat via /save, YYYY-MM-DD session"
---
```

**Zone-specific additions** (per `90 System/_operating_guide.md` P-4):

- `50 Sources/_analysis/`, `40 Meetings/`, `70 Decisions/`: add `is_latest_version: true` and (decisions only) `effective_date: YYYY-MM-DD`.
- `60 Concepts/`: add `claim_type: inference` (the default for `60 Concepts/`).
- `10 People/`, `20 Companies/`, `40 Meetings/`, `50 Sources/`, `70 Decisions/`: default `claim_type: evidence`.
- All typed zones: add `confidence: 0.7` (default — corroborated secondary) unless a higher / lower value is justified by the source quality.
- `00 Inbox/` low-confidence routing: `confidence: 0.2`, no `claim_type` (Inbox is pre-typed).

### Tags (optional)

Extract 2–4 tags from the content — workstream names, counterparty names, framework names. Tags are optional; skip if nothing obvious surfaces. Format: `tags: [tag1, tag2, tag3]`.

---

## Phase 5 — ask Ricardo (single AskUserQuestion)

Present **one** AskUserQuestion with exactly three options. Write it so Ricardo can decide in under 15 seconds:

- **Header (≤12 chars)**: "Save?"
- **Question body**: One line in the format **"Save as `<Zone>/<Title>.md`? — y / n / edit"** followed by:
  - The one-line proposal preamble (route + reasoning, e.g., "Auto-classified `50 Sources/_analysis/` — strong audit/comparison signals. P-10 PASS." or "Routed to `00 Inbox/` — P-10 Q2 failed [recap of existing meeting]. Triage at next session.")
  - The full proposed frontmatter block in a code fence
  - The first 120 chars of body content so Ricardo can verify the right block was selected

- **Option 1 (Recommended) — Accept**: "Write now and log."
- **Option 2 — Reject**: "Skip — content stays in chat history only."
- **Option 3 — Edit**: "Pause and change title / zone / frontmatter, then re-present."

Use `AskUserQuestion` exactly once per save. Do not bundle multiple saves into one question — work one at a time.

---

## Phase 6 — on accept: write + log

1. **Write the target file.**
   - Body = the selected chat content, lightly cleaned (drop trailing meta-commentary like "let me know if you want…", strip Claude self-references).
   - Frontmatter as proposed.
   - For Inbox writes, body can be raw — Inbox is by design rough.

2. **Log to `99 Workspace/_auto_writes.md` via the hash-chain script.** Per `.claude/rules/auto-write-discipline.md`:
   ```bash
   python3 "90 System/_audit_chain.py" \
     --vault <YOUR_VAULT_PATH> \
     append --verb write --path "<target_path>" \
     --reason "/save: <one-line — auto-classified <zone> · P-10 outcome>"
   ```
   Fallback: if the chain script is unavailable, append a plain line and note the gap (chain verifier ignores unsigned lines).

3. **For typed-zone writes that update the catalog**, append the new row to `_index.md` via the FN-09 promotion hook:
   ```bash
   python3 "90 System/_build_index.py" --append "<target_path>"
   ```
   Skip for `00 Inbox/` writes — Inbox notes don't count toward the catalog.

4. **Acknowledge to Ricardo** in one line: "Saved → `<Zone>/<Title>.md`. Logged." If routed to Inbox, add: "Triage at next session via the handoff freshness flag."

---

## Phase 7 — on reject / edit

**Reject:**
- No file written, no log entry. Tell Ricardo: "Skipped — content stays in chat history only."
- Optional: offer to retry with a different zone or title — but only once.

**Edit:**
- Ask Ricardo what to change (free text — title, zone, frontmatter, tags, body trim).
- Re-draft the proposal.
- Re-present the AskUserQuestion **once more**. If Ricardo rejects or edits again, surface the friction and offer to skip — never loop more than twice.

---

## Worked examples

### Example 1 — strong typed-zone match

Chat just produced a 600-word analysis comparing three architectures for a Galp workstream. Ricardo types `/save`.

- Phase 1: signals "analysis", "comparison", "trade-offs", "scored against" → strong `50 Sources/_analysis/`.
- Phase 2: P-10 — still true (no contradicting debrief), affects tomorrow (architecture choice is open), not encoded elsewhere → PASS.
- Phase 3: no uncertainty signals.
- Phase 4: title `2026-05-17_architecture_comparison.md`; `type: analysis`; `claim_type: evidence`; `confidence: 0.7`; tags `[architecture, workstream-X]`.
- Phase 5: AskUserQuestion → Accept.
- Phase 6: write, log, append to `_index.md`.

### Example 2 — low-confidence → Inbox

Ricardo is brainstorming and types `/save this might be useful`. Content is a 150-word riff on a possible framework.

- Phase 1: ambiguous — could be `60 Concepts/` or `00 Inbox/`.
- Phase 3 fires: "might", < 200 words, exploratory.
- Phase 4: title `2026-05-17-framework_riff.md`; `type: inbox`; `confidence: 0.2`.
- Phase 5: AskUserQuestion preamble notes "Routed to Inbox — exploratory + < 200 words."
- Phase 6: write to `00 Inbox/`, log. Skip `_index.md` append.

### Example 3 — handoff to another skill

Ricardo says `/save` after a long thread that distilled into a new rule about how Claude should handle a pattern.

- Phase 1 special routing: this is a systemic rule, not analysis → propose `kb-curator promote-lesson` instead.
- Surface to Ricardo: "This looks like a systemic lesson, not a one-off note — invoke `kb-curator promote-lesson` instead?"
- If Ricardo says yes → hand off, no file written.
- If Ricardo insists on saving as a note → continue with `60 Concepts/` routing.

---

## What `/save` does NOT do

- **Does not** promote an existing `99 Workspace/` file — use `promote` skill.
- **Does not** rewrite existing typed-zone notes — use direct Edit.
- **Does not** trigger a P-10 propose-cleanup batch — use `kb-curator propose-cleanup`.
- **Does not** create plans — use `plan-builder`.
- **Does not** save lessons or rules — use `kb-curator promote-lesson`.
- **Does not** loop autonomously — exactly one `AskUserQuestion` per invocation; re-present at most once on Edit.
- **Does not** write to `_archive/` — that's a P-10 archival outcome, not a save outcome.

---

## Why this skill exists

Karpathy, on the LLM-Wiki pattern: *"Good answers can be filed back into the wiki as new pages... these are valuable and shouldn't disappear into chat history."*

The Galp Vault has `promote` (for files), `kb-curator promote-lesson` (for rules), and `plan-builder` (for execution). It had no general path for **"this analysis was valuable — file it"**. Without one, mid-conversation analyses evaporate on session close and re-emerge as duplicated work weeks later.

`/save` is the cheapest possible interaction that closes that gap: classify → filter → ask once → write. The defaults are conservative (Inbox on any ambiguity) because wrong-zone placement is harder to fix than triaging an extra Inbox note next session.

---

## Cross-references

- `90 System/_promotion_quality_guide.md` — the three-question P-10 quality filter (FN-11 reuses it verbatim).
- `90 System/_operating_guide.md` — P-10 promotion ritual (this skill is the conversation-side complement), P-4 frontmatter contract (zone defaults + confidence rubric), P-7 autonomy boundary.
- `.claude/rules/auto-write-discipline.md` — hash-chain log entry format.
- `.claude/rules/inbox-discipline.md` — Inbox lifecycle (capture → triage → promote / merge / delete).
- `.claude/skills/promote/SKILL.md` — sibling skill for `99 Workspace/ → typed zone` promotion.
- `.claude/skills/kb-curator/SKILL.md` — `promote-lesson` for systemic improvements.
- `90 System/_audit_chain.py` — chain script for `_auto_writes.md` entry append.
- `90 System/_build_index.py` — `--append PATH` hook for `_index.md` row update (typed-zone saves only).
- `99 Workspace/_audit_2026-05-16_framework_review.md` — P0.3 source of this skill's brief.
