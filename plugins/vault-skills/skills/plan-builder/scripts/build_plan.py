#!/usr/bin/env python3
"""
Build a self-contained HTML plan dashboard from a JSON spec (Aurora edition).

Usage:
    python build_plan.py <spec.json> <output.html> [--register-in <project-root>]

The script reads a plan spec JSON, validates it, then assembles the final HTML
by injecting generated fragments into the base template's marker comments.

The Aurora edition emits a DUAL-LAYER card structure:
  * HUMAN layer (prominent): id, title, status pill, plain-English `human_summary`,
    `deliverable` callout, "Why this matters" italic line.
  * AGENT layer (collapsible <details class="agent-spec">): description, agent
    instructions, schema, mockup, code excerpt, owner / target / touches.

All new spec fields are OPTIONAL — old specs continue to build identically
except for the visual refresh.

See ../references/schemas.md for the spec schema.
"""
import json
import sys
import re
import html
from pathlib import Path
from datetime import date

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_PATH = SKILL_DIR / "assets" / "base-template.html"

# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def validate_spec(spec):
    """Raise ValueError with a clear message if spec is invalid."""
    required_top = ["title", "categories", "items", "sessions", "infographic"]
    for k in required_top:
        if k not in spec:
            raise ValueError(f"Missing required top-level field: {k!r}")

    if not isinstance(spec["categories"], list) or not spec["categories"]:
        raise ValueError("'categories' must be a non-empty list")

    cat_keys = {c["key"] for c in spec["categories"]}
    for c in spec["categories"]:
        for f in ["key", "label"]:
            if f not in c:
                raise ValueError(f"Category missing '{f}': {c}")

    item_ids = set()
    for it in spec["items"]:
        for f in ["id", "title", "category"]:
            if f not in it:
                raise ValueError(f"Item missing '{f}': {it}")
        if it["category"] not in cat_keys:
            raise ValueError(f"Item {it['id']} references unknown category {it['category']!r}")
        if it["id"] in item_ids:
            raise ValueError(f"Duplicate item id: {it['id']}")
        item_ids.add(it["id"])

    session_ids = set()
    for s in spec["sessions"]:
        for f in ["id", "title", "model", "items"]:
            if f not in s:
                raise ValueError(f"Session missing '{f}': {s}")
        if s["id"] in session_ids:
            raise ValueError(f"Duplicate session id: {s['id']}")
        session_ids.add(s["id"])
        for iid in s["items"]:
            if iid not in item_ids:
                raise ValueError(f"Session {s['id']} references unknown item {iid!r}")
        thinking = s.get("thinking")
        if thinking and normalize_thinking(thinking) not in THINKING_CANON:
            raise ValueError(
                f"Session {s['id']} has invalid thinking effort {thinking!r}; "
                f"use one of Low / Medium / High / Extra / Max"
            )

    info = spec["infographic"]
    valid_types = ["phase-journey", "maturity-ladder", "hub-spoke", "before-after", "pillars", "custom"]
    if info.get("type") not in valid_types:
        raise ValueError(f"infographic.type must be one of {valid_types}, got {info.get('type')!r}")
    if info.get("type") == "custom":
        if "svg_inline" not in info and "svg_inline_file" not in info:
            raise ValueError("custom infographic requires 'svg_inline' (raw SVG markup) or 'svg_inline_file' (path)")
        if "groups" not in info:
            raise ValueError("custom infographic requires 'groups' (list of {id, items[]} for data binding)")
        for g in info["groups"]:
            for f in ["id", "items"]:
                if f not in g:
                    raise ValueError(f"custom group missing '{f}': {g}")

    return True

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def esc(s):
    return html.escape(str(s), quote=False) if s is not None else ""

def attr(s):
    return html.escape(str(s), quote=True) if s is not None else ""

def encode_pre(s):
    """Encode text for safe embedding inside a <pre> block."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def today_iso():
    return date.today().isoformat()

# --------------------------------------------------------------------------
# Model + thinking-effort helpers (Cowork model + Effort Control picker)
# --------------------------------------------------------------------------
# Each session card recommends a Cowork *model* (e.g. "Opus 4.8", "Sonnet 4.6")
# and a *thinking-effort* level the user sets in Cowork's Effort Control picker.
# Model strings are free-form labels; we derive a CSS *family* (opus / sonnet /
# haiku) for chip color + arc dot so any version label renders correctly.
MODEL_FAMILIES = ("opus", "sonnet", "haiku")

def model_family(model):
    """Map any model label to a CSS family for chip color + arc dot."""
    m = (model or "").lower()
    for f in MODEL_FAMILIES:
        if f in m:
            return f
    return "sonnet"

# Cowork Effort Control picker labels. Adaptive thinking decides WHETHER to
# think; effort guides HOW MUCH. Synonyms (API / Claude Code tokens) normalize
# to the Cowork picker label so authors can write either vocabulary.
THINKING_CANON = ["Low", "Medium", "High", "Extra", "Max"]
THINKING_SYNONYMS = {
    "low": "Low",
    "medium": "Medium", "med": "Medium",
    "high": "High",
    "extra": "Extra", "xhigh": "Extra", "x-high": "Extra",
    "extra high": "Extra", "extrahigh": "Extra", "extra-high": "Extra",
    "max": "Max", "maximum": "Max",
}

def normalize_thinking(value):
    """Return the canonical Cowork picker label, or '' if unset.
    Unknown values are returned trimmed (validate_spec catches typos)."""
    if not value:
        return ""
    key = str(value).strip().lower()
    if key in THINKING_SYNONYMS:
        return THINKING_SYNONYMS[key]
    for c in THINKING_CANON:
        if c.lower() == key:
            return c
    return str(value).strip()

# --------------------------------------------------------------------------
# Strip + filter chip + category fragments
# --------------------------------------------------------------------------
def gen_session_strip(sessions):
    chips = []
    for s in sessions:
        sid = s["id"]
        model = s.get('model', 'Sonnet')
        thinking = normalize_thinking(s.get('thinking', ''))
        title_text = f"{sid.upper()} — {s['title']} · {model}" + (f" · {thinking} effort" if thinking else "")
        chips.append(
            f'  <a href="#{attr(sid)}" class="strip-chip" data-session="{attr(sid)}" '
            f'data-status="TODO" title="{attr(title_text)}">{esc(sid.upper())}</a>'
        )
    return (
        '<nav class="session-strip" aria-label="Session navigation" data-role="auto-render">\n'
        '  <span class="strip-label">Sessions</span>\n'
        + '\n'.join(chips) + '\n'
        '</nav>'
    )

def gen_category_filter_chips(categories):
    chips = ['<div class="cat-filter active" data-cat="all">All</div>',
             '<div class="cat-filter" data-cat="sessions">Session plan</div>']
    for c in categories:
        chips.append(f'<div class="cat-filter" data-cat="{attr(c["key"])}">{esc(c["label"])}</div>')
    return '\n        '.join(chips)

def gen_cats_array_js(categories):
    lines = ["[",
             "        { key: 'sessions', label: 'Session Plan', type: 'session' },"]
    for c in categories:
        lines.append(f"        {{ key: '{c['key']}', label: \"{esc(c['label'])}\", type: 'item' }},")
    lines.append("      ]")
    return '\n'.join(lines)

# Palette rotation for category accent colors. Skip 'sessions' which always uses session/terra.
ACCENT_VARS = ['var(--galp)', 'var(--terra)', 'var(--sonnet)', 'var(--doing)',
               'var(--done)', 'var(--p1)', 'var(--p2)', 'var(--opus)', 'var(--deferred)']

def gen_category_colors_css(categories):
    lines = ['  .cat-row[data-cat="sessions"] { --cat-accent: var(--session); }']
    for i, c in enumerate(categories):
        accent = ACCENT_VARS[i % len(ACCENT_VARS)]
        lines.append(f'  .cat-row[data-cat="{c["key"]}"] {{ --cat-accent: {accent}; }}')
    return '\n'.join(lines)

# --------------------------------------------------------------------------
# Dual-layer agent-spec content blocks
# --------------------------------------------------------------------------
def gen_code_block(content_field, label):
    """Render a code/schema/mockup code excerpt as a dark code-block.
    `content_field` may be a string (raw code) or a dict with optional keys:
      - code (str): the actual code
      - lang (str): language hint shown in the header (e.g. 'json', 'sql', 'ts')
      - caption (str): optional caption line
    Returns empty string if no usable content.
    """
    if not content_field:
        return ""
    if isinstance(content_field, str):
        code, lang, caption = content_field, "", ""
    elif isinstance(content_field, dict):
        code = content_field.get("code", "")
        lang = content_field.get("lang", "")
        caption = content_field.get("caption", "")
    else:
        return ""
    if not code:
        return ""
    lang_label = lang.upper() if lang else label.upper()
    caption_html = f'<figcaption style="color:var(--text-muted);font-size:11.5px;font-style:italic;margin-top:6px;">{esc(caption)}</figcaption>' if caption else ""
    return f'''<div class="code-block">
      <div class="code-block-head"><span class="agent-tag">{esc(label)}</span><span>{esc(lang_label)}</span></div>
      <pre>{encode_pre(code)}</pre>
    </div>{caption_html}'''

def gen_mockup_block(mockup):
    """Render a mockup as <figure class="mockup">.
    `mockup` may be a string (raw SVG/HTML/ASCII) or a dict:
      - svg (str): inline SVG markup
      - ascii (str): ASCII / text mockup, rendered in <pre>
      - img (str): image URL
      - caption (str): optional caption
    """
    if not mockup:
        return ""
    if isinstance(mockup, str):
        # Detect SVG by leading tag
        m = mockup.lstrip()
        if m.startswith("<svg") or m.startswith("<?xml"):
            inner = mockup
            return f'<figure class="mockup"><span class="agent-tag" style="float:left">MOCKUP</span>{inner}</figure>'
        else:
            return f'<figure class="mockup"><span class="agent-tag" style="float:left">MOCKUP · ASCII</span><pre>{encode_pre(mockup)}</pre></figure>'
    if isinstance(mockup, dict):
        caption = mockup.get("caption", "")
        cap_html = f'<figcaption>{esc(caption)}</figcaption>' if caption else ""
        if mockup.get("svg"):
            return f'<figure class="mockup"><span class="agent-tag" style="float:left">MOCKUP</span>{mockup["svg"]}{cap_html}</figure>'
        if mockup.get("img"):
            alt = attr(mockup.get("alt", "mockup"))
            return f'<figure class="mockup"><span class="agent-tag" style="float:left">MOCKUP</span><img src="{attr(mockup["img"])}" alt="{alt}"/>{cap_html}</figure>'
        if mockup.get("ascii"):
            return f'<figure class="mockup"><span class="agent-tag" style="float:left">MOCKUP · ASCII</span><pre>{encode_pre(mockup["ascii"])}</pre>{cap_html}</figure>'
    return ""

def gen_agent_instructions(instr):
    """Render agent_instructions as an ordered list. Accepts list[str] or str."""
    if not instr:
        return ""
    if isinstance(instr, str):
        return f'<p>{esc(instr)}</p>'
    if isinstance(instr, list):
        lis = "\n        ".join(f'<li>{esc(x)}</li>' for x in instr)
        return f'<ol>\n        {lis}\n      </ol>'
    return ""

# --------------------------------------------------------------------------
# Item card — dual layer
# --------------------------------------------------------------------------
def gen_item_article(item, item_to_session):
    iid = item["id"]
    sid = item_to_session.get(iid)
    session_link = (
        f'<span class="session-link"><strong>Session:</strong> <a href="#{attr(sid)}">{esc(sid.upper())}</a></span>'
        if sid else
        '<span class="session-link"><strong>Session:</strong> <em style="color:var(--text-subtle);font-style:italic;">trigger-deferred</em></span>'
    )
    pri = item.get("priority", "P3")
    eff = item.get("effort", "M")
    title = item["title"]
    human_summary = item.get("human_summary", "")
    deliverable = item.get("deliverable", "")
    desc = item.get("description", "")
    why = item.get("why", "")
    owner = item.get("owner", "")
    target = item.get("target", "")
    touches = item.get("touches", "")
    updated = item.get("updated", today_iso())

    # AGENT spec body — only render if at least one technical field is present
    agent_pieces = []
    if desc and not human_summary:
        # If there's no human_summary but a description, surface description in human layer instead — see below.
        pass
    elif desc:
        agent_pieces.append(f'<h4>Detail</h4><p>{esc(desc)}</p>')
    instr = item.get("agent_instructions")
    if instr:
        agent_pieces.append('<h4>Agent instructions</h4>' + gen_agent_instructions(instr))
    sch = gen_code_block(item.get("schema"), "SCHEMA")
    if sch:
        agent_pieces.append('<h4>Schema</h4>' + sch)
    mk = gen_mockup_block(item.get("mockup"))
    if mk:
        agent_pieces.append('<h4>Mockup</h4>' + mk)
    code = gen_code_block(item.get("code"), "CODE")
    if code:
        agent_pieces.append('<h4>Code excerpt</h4>' + code)
    if touches:
        agent_pieces.append(f'<h4>Files / areas touched</h4><p><code>{esc(touches)}</code></p>')
    agent_spec = ""
    if agent_pieces:
        agent_spec = f'''
    <details class="agent-spec" data-role="agent-spec">
      <summary><span class="notes-label">Agent spec</span> <span class="agent-tag">FOR CLAUDE</span></summary>
      <div class="agent-spec-body">
      {"".join(agent_pieces)}
      </div>
    </details>'''

    # HUMAN layer: prefer human_summary, fallback to description.
    summary_block = ""
    if human_summary:
        summary_block = f'<p class="human-summary">{esc(human_summary)}</p>'
    elif desc:
        summary_block = f'<p class="human-summary">{esc(desc)}</p>'

    deliverable_block = ""
    if deliverable:
        deliverable_block = f'<div class="deliverable"><strong>When done</strong>{esc(deliverable)}</div>'

    why_block = f'<p class="why"><strong>Why:</strong> {esc(why)}</p>' if why else ''

    meta_parts = [session_link]
    if owner:  meta_parts.append(f'<span><strong>Owner:</strong> {esc(owner)}</span>')
    if target: meta_parts.append(f'<span><strong>Target:</strong> {esc(target)}</span>')
    # Touches is moved into agent-spec when there's an agent_spec; if not, leave it visible.
    if touches and not agent_pieces:
        meta_parts.append(f'<span><strong>Touches:</strong> <code>{esc(touches)}</code></span>')

    return f'''  <article class="item" id="{attr(iid)}" data-status="TODO" data-priority="{attr(pri)}" data-cat="{attr(item["category"])}" data-updated="{attr(updated)}">
    <header class="item-head">
      <span class="id-tag">{esc(iid.upper())}</span>
      <h3 class="title">{esc(title)}</h3>
      <span class="pill status-TODO">TODO</span>
      <span class="chip priority-{attr(pri)}">{esc(pri)}</span>
      <span class="chip">Effort: {esc(eff)}</span>
    </header>
    {summary_block}
    {deliverable_block}
    {why_block}
    <div class="meta-row">
      {"".join(meta_parts)}
    </div>{agent_spec}
    <details class="notes">
      <summary><span class="notes-label">Notes (0)</span></summary>
      <div class="notes-content"><span class="empty">No notes yet.</span></div>
    </details>
  </article>'''

def gen_category_section(category, items, item_to_session):
    cat_items = [it for it in items if it["category"] == category["key"]]
    if not cat_items:
        return ""
    blurb = category.get("description", "")
    item_cards = '\n'.join(gen_item_article(it, item_to_session) for it in cat_items)
    return f'''<section class="category" data-cat="{attr(category["key"])}">
  <h2 class="section">{esc(category["label"])}
    {f'<span class="section-blurb">{esc(blurb)}</span>' if blurb else ''}
  </h2>
{item_cards}
</section>
'''

# --------------------------------------------------------------------------
# Session closeouts — same as before
# --------------------------------------------------------------------------
def closeout_text_for_prompt(items, next_session):
    item_list = ", ".join(i.upper() for i in items)
    next_line = (
        f"(5) Hand off to next session: {next_session.upper()}. Append a one-line orientation to the project's session-handoff file."
        if next_session else
        "(5) This is the LAST session in the plan. Mark the plan as fully complete in the project's session-handoff file."
    )
    return f"""

CLOSEOUT — that's it. The dashboard, donuts, arc, categories, and last-updated stamp all auto-recompute from data-status when the page loads. Do NOT touch counters, dashboard spans, comment blocks, or visualizations.

(1) For each completed item ({item_list}): on its <article id="…">, change data-status TODO→DONE, update the visible <span class="pill"> text to DONE, set data-updated to today's ISO date, append a note inside the item's <div class="notes-content"> as <p class="note"><strong>YYYY-MM-DD:</strong> outcome</p>.

(2) Mark this session DONE: same protocol on the session article.

(3) Update the project's session-handoff file with the outcome.

(4) Log every write per the project's auto-write discipline.

{next_line}

If anything is unclear before starting, ask. The Operating Manual at the top of the file is the source of truth — read it if in doubt."""

def gen_visible_closeout(sid, items, next_session, next_title):
    item_links = " · ".join(f'<a href="#{i}">{i.upper()}</a>' for i in items)
    n = len(items)
    item_word = "item" if n == 1 else "items"
    next_li = (
        f'        <li><strong>Hand off:</strong> next session is <a href="#{next_session}">{next_session.upper()}{f" — {esc(next_title)}" if next_title else ""}</a> — note in the project\'s session-handoff file.</li>\n'
        if next_session else
        '        <li><strong>Hand off:</strong> last session in the plan. Mark plan complete in the session-handoff file.</li>\n'
    )
    return f'''    <div class="session-closeout">
      <strong class="closeout-title">Closeout — apply at session end</strong>
      <ol>
        <li><strong>Mark {n} {item_word} DONE</strong> ({item_links}): on each <code>&lt;article&gt;</code> change <code>data-status</code> TODO→DONE, update the pill text, set <code>data-updated</code> to today, and add a one-line note.</li>
        <li><strong>Mark this session DONE:</strong> same protocol on <a href="#{sid}">{sid.upper()}</a> (this card).</li>
        <li><strong>Update</strong> the project's session-handoff file with the outcome.</li>
        <li><strong>Log writes</strong> per the project's auto-write discipline.</li>
{next_li}      </ol>
      <p class="manual-note" style="margin-top:8px">Counters, donuts, arc, and last-updated stamp all auto-recompute on page load — don't touch them.</p>
    </div>
'''

# --------------------------------------------------------------------------
# Session card — dual layer with prominent action bar
# --------------------------------------------------------------------------
def session_purpose_fallback(session_title, item_ids, items_by_id):
    """Build a substantive plain-English purpose paragraph when no human_summary
    is provided on the session.

    Strategy: pull each item's `human_summary` (preferred) or `description`
    (fallback). Concatenate into a paragraph that actually explains WHAT the
    session does, not just lists titles. If items carry no narrative content,
    fall back to a title-list — better than nothing.
    """
    items = [items_by_id[iid] for iid in item_ids if iid in items_by_id]
    if not items:
        return f"Pick up the work in {session_title}."

    # Per-item rich text: prefer human_summary, then description, last resort title.
    rich = []
    has_narrative = False
    for it in items:
        if it.get("human_summary"):
            rich.append(it["human_summary"].strip())
            has_narrative = True
        elif it.get("description"):
            # Take first sentence to keep length sane.
            d = it["description"].strip()
            first = re.split(r"(?<=[.!?])\s+", d, maxsplit=1)[0]
            rich.append(first if first.endswith((".", "!", "?")) else first + ".")
            has_narrative = True
        else:
            rich.append(f'"{it["title"]}".')

    if has_narrative:
        # Join the per-item narrative into one paragraph. The serif rendering at
        # 26px will give it the right editorial weight.
        return " ".join(rich)

    # Pure title-list fallback when no item carries narrative content.
    titles = [it["title"] for it in items]
    if len(titles) == 1:
        return f'Bring "{titles[0]}" across the finish line.'
    if len(titles) == 2:
        return f'Cover "{titles[0]}" and "{titles[1]}".'
    head = ", ".join(f'"{t}"' for t in titles[:2])
    return f'Cover {len(titles)} items: {head}, and {len(titles)-2} more.'



def gen_session_article(session, sessions_list, idx, items_by_id=None):
    sid = session["id"]
    total = len(sessions_list)
    model = session.get("model", "Sonnet")
    fam = model_family(model)
    thinking = normalize_thinking(session.get("thinking", ""))
    effort = session.get("effort", "")
    why_model = session.get("why_model", "")
    items = session.get("items", [])
    human_summary = session.get("human_summary", "")
    deliverable = session.get("deliverable", "")
    agent_instr = session.get("agent_instructions")
    items_by_id = items_by_id or {}

    next_session = None
    next_title = None
    if idx + 1 < total:
        nxt = sessions_list[idx + 1]
        next_session = nxt["id"]
        next_title = nxt["title"]

    item_links = " · ".join(f'<a href="#{i}">{i.upper()}</a>' for i in items)
    prompt_body = session.get("prompt", "").rstrip()
    full_prompt = prompt_body + closeout_text_for_prompt(items, next_session)
    prompt_encoded = encode_pre(full_prompt)
    visible_closeout = gen_visible_closeout(sid, items, next_session, next_title)
    updated = session.get("updated", today_iso())

    # ALWAYS render the human-purpose block. Use human_summary if provided;
    # otherwise auto-build a plain-English sentence from the items in scope.
    purpose_text = human_summary or session_purpose_fallback(session.get("title", sid), items, items_by_id)
    eyebrow_label = "What we’re doing" if human_summary else "What this session covers"
    summary_block = (
        f'<div class="purpose-eyebrow">{eyebrow_label}</div>'
        f'<p class="session-summary">{esc(purpose_text)}</p>'
    )

    deliverable_block = f'<div class="deliverable"><strong>By end of session you’ll have</strong>{esc(deliverable)}</div>' if deliverable else ''
    rec_label = f"Why {esc(model)}" + (f" · {esc(thinking)} effort" if thinking else "")
    why_model_block = f'<p class="model-rec"><strong>{rec_label}:</strong> {esc(why_model)}</p>' if why_model else ''

    step = f"Session {idx + 1} of {total}"

    next_btn = ""
    if next_session:
        next_btn = f'<a href="#{next_session}" class="btn-secondary" title="Jump to {next_session.upper()}">Open next {esc(next_session.upper())} →</a>'

    picker_str = esc(model) + (f" · {esc(thinking)} effort" if thinking else "")
    actions_html = f'''    <div class="session-actions">
      <span class="actions-label">Start session</span>
      <button class="btn-primary" data-target="prompt-{attr(sid)}">Copy prompt</button>
      <a href="#{sid}" class="btn-secondary">Jump to card</a>
      {next_btn}
      <span class="picker-hint" style="margin-left:auto;">set Cowork picker → <strong>{picker_str}</strong>, then paste →</span>
    </div>'''

    agent_pieces = []
    if agent_instr:
        agent_pieces.append('<h4>Agent instructions</h4>' + gen_agent_instructions(agent_instr))
    agent_pieces.append(f'''<h4>Full prompt (sent to Claude)</h4>
        <div class="prompt-block">
          <div class="prompt-header">
            <span class="prompt-label">Prompt</span>
            <button class="copy-btn" data-target="prompt-{attr(sid)}">Copy</button>
          </div>
<pre class="prompt-text" id="prompt-{attr(sid)}">{prompt_encoded}</pre>
        </div>''')
    agent_pieces.append("<h4>Closeout (mirrors what’s appended to the prompt)</h4>" + visible_closeout)

    agent_spec = f'''
    <details class="agent-spec" data-role="agent-spec">
      <summary><span class="notes-label">Agent spec · prompt + closeout</span> <span class="agent-tag">FOR CLAUDE</span></summary>
      <div class="agent-spec-body">
      {"".join(agent_pieces)}
      </div>
    </details>'''

    return f'''  <article class="session" id="{attr(sid)}" data-status="TODO" data-model-family="{attr(fam)}" data-thinking="{attr(thinking)}" data-updated="{attr(updated)}">
    <div class="session-step">{esc(step)}</div>
    <header class="item-head">
      <span class="id-tag id-session">{esc(sid.upper())}</span>
      <h3 class="title">{esc(session["title"])}</h3>
      <span class="pill status-TODO">TODO</span>
      <span class="chip model-chip model-{attr(fam)}" data-model-family="{attr(fam)}">{esc(model)}</span>
      {f'<span class="chip chip-thinking" data-effort="{attr(thinking)}">{esc(thinking)} effort</span>' if thinking else ''}
      {f'<span class="chip chip-effort">{esc(effort)}</span>' if effort else ''}
    </header>
    {summary_block}
    {deliverable_block}
    <p class="session-items"><strong>Items in scope:</strong> {item_links}</p>
    {why_model_block}
{actions_html}
{agent_spec}
    <details class="notes"><summary><span class="notes-label">Notes (0)</span></summary><div class="notes-content"><span class="empty">No notes yet.</span></div></details>
  </article>
'''


def gen_sessions_block(sessions, items_by_id=None):
    return '\n'.join(gen_session_article(s, sessions, i, items_by_id) for i, s in enumerate(sessions))

# --------------------------------------------------------------------------
# Plan Achievement infographics (5 templates) — unchanged from previous version
# --------------------------------------------------------------------------
def infographic_phase_journey_data_js(info):
    phases = info.get("phases", [])
    anchor_now = info.get("anchor_now", {"name": "Now", "tagline": ""})
    anchor_goal = info.get("anchor_goal", {"name": "Goal", "tagline": ""})
    phases_js = json.dumps(phases, indent=6).replace('\n', '\n    ')
    return f"""    const INFOGRAPHIC_TYPE = 'phase-journey';
    const PHASES = {phases_js};
    const ANCHOR_NOW  = {json.dumps(anchor_now)};
    const ANCHOR_GOAL = {json.dumps(anchor_goal)};
"""

def infographic_maturity_ladder_data_js(info):
    levels = info.get("levels", [])
    anchor_bottom = info.get("anchor_bottom", {"name": "Now", "tagline": ""})
    anchor_top = info.get("anchor_top", {"name": "Goal", "tagline": ""})
    return f"""    const INFOGRAPHIC_TYPE = 'maturity-ladder';
    const LEVELS = {json.dumps(levels, indent=6).replace(chr(10), chr(10) + '    ')};
    const ANCHOR_BOTTOM = {json.dumps(anchor_bottom)};
    const ANCHOR_TOP    = {json.dumps(anchor_top)};
"""

def infographic_hub_spoke_data_js(info):
    hub = info.get("hub", {"name": "Goal", "tagline": ""})
    spokes = info.get("spokes", [])
    return f"""    const INFOGRAPHIC_TYPE = 'hub-spoke';
    const HUB = {json.dumps(hub)};
    const SPOKES = {json.dumps(spokes, indent=6).replace(chr(10), chr(10) + '    ')};
"""

def infographic_before_after_data_js(info):
    before = info.get("before", {"name": "Before", "bullets": []})
    after = info.get("after", {"name": "After", "bullets": []})
    workstreams = info.get("workstreams", [])
    return f"""    const INFOGRAPHIC_TYPE = 'before-after';
    const BEFORE = {json.dumps(before)};
    const AFTER = {json.dumps(after)};
    const WORKSTREAMS = {json.dumps(workstreams, indent=6).replace(chr(10), chr(10) + '    ')};
"""

def infographic_pillars_data_js(info):
    roof = info.get("roof", {"name": "Goal"})
    pillars = info.get("pillars", [])
    foundation = info.get("foundation", {"name": "Current capability"})
    return f"""    const INFOGRAPHIC_TYPE = 'pillars';
    const ROOF = {json.dumps(roof)};
    const PILLARS = {json.dumps(pillars, indent=6).replace(chr(10), chr(10) + '    ')};
    const FOUNDATION = {json.dumps(foundation)};
"""

def infographic_custom_data_js(info):
    groups = info.get("groups", [])
    renderer_js = info.get("renderer_js", "")
    return f"""    const INFOGRAPHIC_TYPE = 'custom';
    const GROUPS = {json.dumps(groups, indent=6).replace(chr(10), chr(10) + '    ')};
    const CUSTOM_RENDERER_JS = {json.dumps(renderer_js)};
"""

INFOGRAPHIC_DATA_JS = {
    "phase-journey":   infographic_phase_journey_data_js,
    "maturity-ladder": infographic_maturity_ladder_data_js,
    "hub-spoke":       infographic_hub_spoke_data_js,
    "before-after":    infographic_before_after_data_js,
    "pillars":         infographic_pillars_data_js,
    "custom":          infographic_custom_data_js,
}

def gen_plan_achievement_section(spec):
    info = spec["infographic"]
    title_html = info.get("title", "Plan Achievement")
    eyebrow = info.get("eyebrow", "Plan Achievement · Visual Story")
    narrative = info.get("narrative", "")

    viewbox = info.get("viewBox") or {
        "phase-journey":   "0 0 1200 240",
        "maturity-ladder": "0 0 800 460",
        "hub-spoke":       "0 0 1000 480",
        "before-after":    "0 0 1100 320",
        "pillars":         "0 0 1100 380",
        "custom":          "0 0 1200 320",
    }.get(info["type"], "0 0 1200 240")

    inner_svg = ""
    if info["type"] == "custom":
        if info.get("svg_inline_file"):
            svg_path = Path(info["svg_inline_file"])
            if not svg_path.is_absolute():
                svg_path = Path.cwd() / svg_path
            if svg_path.exists():
                inner_svg = svg_path.read_text()
                inner_svg = re.sub(r'^<!--.*?-->', '', inner_svg, flags=re.DOTALL).strip()
            else:
                inner_svg = f'<text x="20" y="40" fill="red">SVG file not found: {svg_path}</text>'
        else:
            inner_svg = info.get("svg_inline", "")

    return f'''<!-- PLAN ACHIEVEMENT INFOGRAPHIC — human-only visual story -->
<section class="plan-achievement" id="plan-achievement" data-role="human-display">
  <div class="achievement-header">
    <div>
      <div class="achievement-eyebrow">{esc(eyebrow)}</div>
      <div class="achievement-title">{title_html}</div>
    </div>
    <div class="achievement-meta">
      <div class="achievement-counter">
        <div class="achievement-num" id="ach-overall-pct">0%</div>
        <div class="achievement-num-label">overall</div>
      </div>
    </div>
  </div>

  <svg class="phase-journey" id="phase-journey" viewBox="{viewbox}" preserveAspectRatio="xMidYMid meet"
       aria-label="Plan achievement infographic">{inner_svg}</svg>

  {f'<div class="achievement-narrative"><strong>The story</strong>{esc(narrative)}</div>' if narrative else ''}
</section>'''

def load_infographic_renderers_js():
    out = []
    info_dir = SKILL_DIR / "assets" / "infographics"
    for name in ["phase-journey", "maturity-ladder", "hub-spoke", "before-after", "pillars", "custom"]:
        p = info_dir / f"{name}.js"
        if p.exists():
            out.append(f"// === {name} renderer ===\n" + p.read_text())
        else:
            out.append(f"// === {name} renderer (stub — file not found at {p}) ===\n"
                       f"function render_{name.replace('-','_')}(svg, _) {{ "
                       f"svg.innerHTML = '<text x=\"50\" y=\"50\" fill=\"red\">{name} renderer missing</text>'; }}")
    return "\n\n".join(out)

RENDER_DISPATCH_JS = """
    function renderPhaseJourney(itemsArr) {
      const svg = document.getElementById('phase-journey');
      if (!svg) return;
      const type = (typeof INFOGRAPHIC_TYPE !== 'undefined') ? INFOGRAPHIC_TYPE : 'phase-journey';
      const renderers = {
        'phase-journey':   typeof render_phase_journey   !== 'undefined' ? render_phase_journey   : null,
        'maturity-ladder': typeof render_maturity_ladder !== 'undefined' ? render_maturity_ladder : null,
        'hub-spoke':       typeof render_hub_spoke       !== 'undefined' ? render_hub_spoke       : null,
        'before-after':    typeof render_before_after    !== 'undefined' ? render_before_after    : null,
        'pillars':         typeof render_pillars         !== 'undefined' ? render_pillars         : null,
        'custom':          typeof render_custom          !== 'undefined' ? render_custom          : null,
      };
      const fn = renderers[type];
      if (typeof fn === 'function') {
        fn(svg, itemsArr);
      } else {
        svg.innerHTML = '<text x="20" y="40" fill="currentColor">Unknown infographic type: ' + type + '</text>';
      }

      // Overall % big number
      const pctEl = document.getElementById('ach-overall-pct');
      if (pctEl) {
        const total = itemsArr.length;
        let done = 0;
        itemsArr.forEach(it => { if ((it.dataset.status || 'TODO') === 'DONE') done++; });
        const pct = total > 0 ? Math.round((done/total)*100) : 0;
        pctEl.textContent = pct + '%';
      }
    }
"""

# --------------------------------------------------------------------------
# Main build
# --------------------------------------------------------------------------
def build(spec, out_path, project_root=None):
    validate_spec(spec)

    template = TEMPLATE_PATH.read_text()

    abs_path = str(out_path.resolve())
    if project_root:
        try:
            rel_path = str(out_path.resolve().relative_to(Path(project_root).resolve()))
        except ValueError:
            rel_path = abs_path
    else:
        rel_path = abs_path
    project_hint = (f"Project root: {project_root}. See <code>_plans_index.md</code> in that root for all plans in this project."
                    if project_root else "No project root registered. Plan stands alone.")
    location_comment = (
        f'\n<!-- ====================================================================\n'
        f'     PLAN_LOCATION: {abs_path}\n'
        f'     RELATIVE_PATH: {rel_path}\n'
        f'     {project_hint}\n'
        f'     For Claude: the Operating Manual below describes what to edit.\n'
        f'     ==================================================================== -->\n'
    )
    template = template.replace("<main>\n", f"<main>{location_comment}\n", 1)

    item_to_session = {}
    for s in spec["sessions"]:
        for iid in s["items"]:
            item_to_session[iid] = s["id"]

    template = template.replace("{{PLAN_TITLE}}", esc(spec["title"]))
    meta_line = spec.get("subtitle", "")
    if "meta" in spec:
        meta_line = spec["meta"]
    if not meta_line:
        meta_line = f"{len(spec['sessions'])} sessions · {len(spec['items'])} items"
    template = template.replace("{{PLAN_META_LINE}}", meta_line)

    first_sess = spec["sessions"][0] if spec["sessions"] else {"id": "s01", "title": "First session", "model": "Sonnet", "effort": ""}
    template = template.replace("{{FIRST_SESSION_TITLE}}",
                                f"{first_sess['id'].upper()} — {esc(first_sess['title'])}")
    fs_model = esc(first_sess.get("model", "Sonnet"))
    fs_thinking = normalize_thinking(first_sess.get("thinking", ""))
    fs_effort = esc(first_sess.get("effort", ""))
    fs_meta = " · ".join(p for p in [fs_model, (f"{esc(fs_thinking)} effort" if fs_thinking else ""), fs_effort] if p)
    template = template.replace("{{FIRST_SESSION_META}}", fs_meta)
    template = template.replace("{{FIRST_SESSION_ID}}", attr(first_sess["id"]))

    session_plan_blurb = f"{len(spec['sessions'])} sessions · {len(spec['items'])} items"
    template = template.replace("{{SESSION_PLAN_BLURB}}", session_plan_blurb)
    template = template.replace("{{SESSION_TOTAL_COUNT}}", str(len(spec["sessions"])))

    session_strip = gen_session_strip(spec["sessions"])
    cat_chips = gen_category_filter_chips(spec["categories"])
    cats_array = gen_cats_array_js(spec["categories"])
    cat_colors = gen_category_colors_css(spec["categories"])
    plan_achievement = gen_plan_achievement_section(spec)
    items_by_id = {it["id"]: it for it in spec["items"]}
    sessions_html = gen_sessions_block(spec["sessions"], items_by_id)
    cat_sections = "\n".join(gen_category_section(c, spec["items"], item_to_session) for c in spec["categories"])

    info_type = spec["infographic"]["type"]
    info_data_js = INFOGRAPHIC_DATA_JS[info_type](spec["infographic"])
    renderers_raw = load_infographic_renderers_js()
    renderers_local = re.sub(r'window\.render_(\w+)\s*=\s*function', r'function render_\1', renderers_raw)
    infographic_full_js = info_data_js + "\n" + renderers_local + "\n" + RENDER_DISPATCH_JS

    template = template.replace("<!-- INSERT_SESSION_STRIP -->", session_strip)
    template = template.replace("<!-- INSERT_PLAN_ACHIEVEMENT -->", plan_achievement)
    template = template.replace("<!-- INSERT_CATEGORY_FILTER_CHIPS -->", cat_chips)
    template = template.replace("<!-- INSERT_SESSIONS -->", sessions_html)
    template = template.replace("<!-- INSERT_CATEGORY_SECTIONS -->", cat_sections)
    template = template.replace("/* INSERT_INFOGRAPHIC_DATA */", "/* (infographic data injected at INSERT_INFOGRAPHIC_RENDERERS marker) */")
    template = re.sub(
        r'/\* INSERT_INFOGRAPHIC_RENDERERS[^*]*\*/',
        lambda m: infographic_full_js, template
    )
    template = template.replace("/* INSERT_CATS_ARRAY */ []", cats_array)
    template = template.replace("/* INSERT_CATEGORY_COLORS */", cat_colors)

    out_path.write_text(template)
    return out_path

def register_plan_in_project(out_path, spec, project_root):
    project_root = Path(project_root).resolve()
    index_path = project_root / "_plans_index.md"
    rel_path = out_path.resolve().relative_to(project_root) if out_path.resolve().is_relative_to(project_root) else out_path.resolve()

    title = spec["title"]
    today = today_iso()
    n_sessions = len(spec["sessions"])
    n_items = len(spec["items"])

    if index_path.exists():
        body = index_path.read_text()
    else:
        body = ("# Active Plans\n\n"
                "This file lists all plan dashboards in this project. Each plan is a self-contained\n"
                "HTML file built by the `plan-builder` skill. To execute a session: open the plan,\n"
                "find the session card, click 'Copy prompt', paste into a fresh Cowork session. To\n"
                "update progress: read the plan's Operating Manual at the top of the file.\n\n"
                "## Plans\n\n")

    entry = f"- **[{title}]({rel_path})** · {n_sessions} sessions · {n_items} items · created {today}\n"
    body = re.sub(rf'^- \*\*\[[^\]]+\]\({re.escape(str(rel_path))}\).*\n', '', body, flags=re.MULTILINE)
    body = body.rstrip() + "\n" + entry
    index_path.write_text(body)

    snippet = (f"**Active plan:** [{title}]({rel_path}) · "
               f"{n_sessions} sessions · execute via plan-builder protocol · "
               f"see also `_plans_index.md`")
    return index_path, snippet


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build a plan HTML dashboard from a JSON spec.")
    parser.add_argument("spec", help="Path to plan spec JSON file")
    parser.add_argument("output", help="Path to output HTML file")
    parser.add_argument("--register-in", metavar="PROJECT_ROOT",
                        help="Register the plan in <PROJECT_ROOT>/_plans_index.md.")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    out_path = Path(args.output)
    spec = json.loads(spec_path.read_text())
    build(spec, out_path, project_root=args.register_in)
    print(f"Built {out_path} ({out_path.stat().st_size:,} bytes)")

    if args.register_in:
        index_path, snippet = register_plan_in_project(out_path, spec, args.register_in)
        print(f"Registered in {index_path}")
        print()
        print("=" * 72)
        print("Suggest pasting this into the project's CLAUDE.md or session-handoff file:")
        print("=" * 72)
        print(snippet)
        print("=" * 72)

if __name__ == "__main__":
    main()
