---
description: Refresh _hot.md — the ≤2 KB always-fresh orientation surface read FIRST at every session start.
argument-hint: "[--write] [--canonical-plan=path]"
---

# /hot

You are running the `hot` slash command from the `vault-framework` plugin.
The goal is to refresh `99 Workspace/_hot.md` — the ≤2 KB orientation
surface that gets read FIRST at every session start, before
`_session_handoff.md`.

## Why _hot.md exists

Karpathy pattern: cheap to read, expensive when stale. The session handoff
is the forensic surface — every open thread, every micro-decision, full
detail. But it's 15 KB on a good day. _hot.md is the ≤2 KB summary that
gives the whole session context in ~5 seconds:

1. **Canonical plan** + progress counter (e.g. "8/12 sessions DONE · 14/21
   items DONE")
2. **Up Next** — the next session's items, named
3. **One in-flight risk** — the thing most likely to derail this week
4. **One open question for the user** — what needs their input next

That's it. No history. No backlog. No archive pointers. If you wouldn't
read it in 5 seconds at session start, it doesn't go in _hot.md.

## Process

1. **Read the canonical active plan** from `_plans_index.md` — the entry
   that is un-archived, un-superseded, un-completed.
2. **Compute the progress counter** from the plan's article `data-status`
   attributes (count DONE vs total).
3. **Identify the next Up Next session** — first article whose
   `data-status` is not DONE.
4. **Surface one in-flight risk** — read the prior `_session_handoff.md`
   for any "in-flight risk" or "observation window" marker. If none,
   summarise the riskiest forward-looking trigger from the plan.
5. **Surface one open question for the user** — read the prior handoff for
   any "Awaiting [user]" or "Open question" marker. If none, lift it from
   the plan's "stakeholder check-in" or "blocker" annotations.
6. **Write _hot.md** with the frontmatter contract:

   ```yaml
   ---
   name: Hot cache
   description: Always-fresh, ≤2 KB orientation surface. Rewritten at every session close. Read FIRST at session start (before _session_handoff.md). Carries: canonical plan + progress, Up Next session items, one in-flight risk, one open question.
   type: hot-cache
   cadence: per-session
   last_updated: YYYY-MM-DD
   ---
   ```

7. **Verify size** — `wc -c _hot.md` must be ≤ 2048 bytes (target: ≤ 1800).
   If over, compress: drop adjective text, prefer named pointers
   (`See _session_handoff.md §risk`) over inline detail.

## Size budget guidance

```
Frontmatter        ~ 300 B
Canonical plan     ~ 200 B  (plan name + counter + next session name)
Up Next            ~ 400 B  (3-5 bulleted item names)
In-flight risk     ~ 500 B  (the headline + 1-sentence why-it-matters)
Open question      ~ 400 B  (the question + what input is needed)
Slack              ~ 250 B
                  -------
Total              ~ 2 KB
```

If your section runs long, trim it — the file is hostile to long sections
by design.

## What NOT to put in _hot.md

- Anything in the session handoff (this isn't a second copy)
- Cross-reference lists (`See [[X]], [[Y]], [[Z]]`)
- Multi-paragraph context
- Anything that was true yesterday but won't be true tomorrow
- Forward triggers more than a week out — those live in the plan, not hot

## Output

After writing the file, surface back to the user:

> "Refreshed `_hot.md` — N bytes. Canonical plan: <name>. Up Next: <session>.
> One risk surfaced. One open question for you."
