---
type: template
title: "{{Title}}"
aliases: []
status: unprocessed
topics: []
created: "{{date}}"
updated: "{{date}}"
# Temporal frontmatter (REQUIRED for type:source — per P-4 of the operating guide).
# Two clocks: `updated` is transaction-time (when the file was last touched on disk);
# `document_date` is valid-time (when the source content was authored/published).
# They MUST be tracked separately — a whitespace edit today must not make a 2023
# source outrank a 2026 source in "latest" queries.
# See _operating_guide.md P-4 "Temporal frontmatter" block and the
# "`document_date` vs `last_updated` — the two clocks of a file" reference paragraph.
document_date: "{{date}}"   # REQUIRED. Authoring/publication date of the source.
                            # Distinct from `updated` (file-system mtime).
                            # Default at creation: today. Backfill from the
                            # document's own metadata, filename date prefix, or
                            # a document_version → date mapping when known.
is_latest_version: true     # REQUIRED. Boolean. true = this is the current/live
                            # version; false = archived or superseded. Default
                            # at creation: true. Flip to false at the moment of
                            # supersession, paired with promoting the new version.
                            # Used by Latest Only.base (Route A in P-3 routing
                            # matrix) to filter the current-version view.
author: ""
published: ""
source_type: ""            # Vocabulary examples: transcript | report | presentation |
                           # email | article | contract | model | analysis | briefing
source_url: ""
entities: []
projects: []
companies: []
people: []
related: []
# Optional versioning fields (add when source has multiple versions):
# document_version: ""    # e.g. "v30", "3.2", "final" — used by Version Chain.base
# previous_version: ""    # [[predecessor note name]] — chain navigation
# family: ""              # family slug for Version Chain.base By Family view
#                         # (e.g. "6pager") — optional; add to each member of
#                         # a version family to activate groupBy in that view
---

# {{Title}}

## Summary



## Key Takeaways



## Entities Mentioned



## Notes
