# Daily notes discipline

`80 Daily/YYYY-MM-DD.md` is opened at session start (per operating guide
bootstrap step 4). Daily notes are a **discoverability aid**, not the immutable
forensic surface — that role belongs to `99 Workspace/_session_handoff_archive/`.

## Structure

Each daily note carries:

1. A `## Session Summary` section with a wikilink to today's session-handoff
   archive entry (`99 Workspace/_session_handoff_archive/YYYY-MM-DDTHHMM.md`).
   The archive is the authoritative record; the daily note is the convenient
   surface.
2. Free-form daily activity (calendar references, ad-hoc notes, decisions
   made outside formal session context).
3. Optional links to key files touched today.

## Why two surfaces

The archive entry is append-only and immutable; the daily note is editable
and discoverable via the Obsidian Daily Notes plugin / calendar view. They
are NOT redundant — the archive is for audit; the daily note is for finding
the archive entry.

If they drift, the archive wins for facts.
