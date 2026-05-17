---
type: template
title: "{{date}} - {{Topic}}"
aliases: []
status: complete
topics: []
created: "{{date}}"
updated: "{{date}}"
date: "{{date}}"
# Temporal frontmatter (REQUIRED for type:meeting — per P-4 of the operating guide,
# post-S02 amendment 2026-05-11). MVP schema — same two fields as type:source.
#
# Meetings use the MVP rather than the full decision bitemporal split because:
# 1. Meetings are nearly always additive (they don't supersede each other).
#    is_latest_version: false is only set when a re-run meeting's debrief
#    explicitly retires the earlier one.
# 2. document_date derives canonically from the filename YYYY-MM-DD prefix,
#    making it cheap to populate.
# 3. The MVP enables the As-Of Base (BT-05) to span meetings, sources, and
#    decisions symmetrically — all three have document_date.
#
# CANONICAL ANCHOR: Filename YYYY-MM-DD prefix = document_date. Always match them.
# A meeting titled 2026-04-24 MUST have document_date: 2026-04-24. The date
# encoded in the filename is the authoritative valid-time anchor.
#
# See _operating_guide.md P-4 "MVP block and asymmetric-schema rationale" paragraph.
document_date: "{{date}}"   # REQUIRED. Meeting date. Must match the YYYY-MM-DD
                            # prefix of the filename exactly. Valid-time anchor
                            # for the As-Of.base point-in-time query (Route B).
is_latest_version: true     # REQUIRED. Nearly always true for meetings.
                            # Flip to false only when a re-run meeting's debrief
                            # explicitly retires this one. Most meeting updates
                            # are additive edits to this same note.
people: []
companies: []
projects: []
source_refs: []             # [[wikilinks]] to source documents referenced in meeting
next_actions: []
related: []
---

# {{date}} - {{Topic}}

## Attendees



## Key Discussion Points



## Decisions Made



## Action Items

- [ ] 

## Notes
