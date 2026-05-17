---
paths:
  - "00 Inbox/**/*.md"
---

# Inbox discipline

`00 Inbox/` is the vault's quick-capture zone — untyped, frontmatter-light
notes. Auto-write OK without per-file approval (subject to
`auto-write-discipline.md`).

## Lifecycle

1. **Capture.** Drop a note as `00 Inbox/YYYY-MM-DD-<slug>.md`. Frontmatter
   may be minimal (`type: inbox` or absent). Body is freeform.
2. **Triage.** A handoff-freshness check flags items >7 days old at the
   weekly/daily check. Triage moves: promote to a typed zone via the
   promotion ritual (P-10), merge into an existing note, or delete.
3. **Promote** via `propose-cleanup` once the note has decision-relevant
   content; quality filter per the promotion quality guide.

Inbox notes do NOT count toward Bases coverage (they are explicitly excluded
in the verifier's allow-list of expected-empty types).
