---
type: template
title: "Decision - {{Summary}}"
aliases: []
status: active
topics: []
created: "{{date}}"
updated: "{{date}}"
date: "{{date}}"
# Bitemporal frontmatter (REQUIRED for type:decision — per P-4 of the operating guide).
# type:decision uses the FULL bitemporal split. This is needed to correctly answer
# "what decision was in force on date X?" under back-dating, scheduled cutovers,
# and retroactive amendments — all of which occur on complex project decision timelines.
#
# TWO-CLOCK MODEL FOR DECISIONS:
#   document_date  = transaction-time: when the decision was RECORDED in the system
#   effective_date = valid-time: when the decision APPLIES IN THE WORLD
#     • can pre-date document_date (retroactive, back-dated to prior period)
#     • can post-date document_date (scheduled future cutover, "effective Day 1 2027")
#     • can equal document_date ("decided and effective immediately")
#
#   superseded_date = transaction-time of supersession: when the system RECORDED
#                     that THIS decision was replaced — NOT the effective_date of
#                     the successor. These two dates must not be conflated.
#   superseded_by  = wikilink to the successor decision
#   previous_version = wikilink to the direct predecessor (for linear chain navigation)
#
# POINT-IN-TIME QUERY: "what decision was in force on date X?"
#   Filter: effective_date <= X AND (superseded_date > X OR superseded_date is empty)
#   AND (if a successor exists: successor's effective_date > X)
#
# See _operating_guide.md P-4 "effective_date vs superseded_date — the two clocks
# of a decision" reference paragraph for the full rationale and edge cases.
document_date: "{{date}}"     # REQUIRED. Date the decision was authored/recorded.
                              # Transaction-time anchor. Distinct from effective_date.
effective_date: "{{date}}"   # REQUIRED. Valid-time start — when the decision
                              # applies in the world. May differ from document_date.
                              # May equal document_date ("decided and effective immediately").
superseded_by: ""             # REQUIRED. [[WikilinkToSuccessor]] when superseded;
                              # empty string ("") while current. Flip from "" to a
                              # wikilink at the moment a successor decision is promoted.
superseded_date: ""           # REQUIRED. ISO date the supersession was recorded
                              # (transaction-time of the supersession event itself).
                              # Empty string ("") while current.
previous_version: ""          # REQUIRED. [[WikilinkToPredecessor]] in the linear chain;
                              # empty string ("") for the chain's first entry.
                              # Distinct from `replaces:` (list, may span multiple).
context: ""
project: ""
stakeholders: []
replaces: []                  # List of [[wikilinks]] to parallel decisions being
                              # collapsed into this one. Distinct from previous_version.
related: []
---

# Decision - {{Summary}}

## Context

Why this decision was needed.

## Decision

What was decided.

## Rationale

Why this option was chosen over alternatives.

## Consequences

What follows from this decision.

## Alternatives Considered
