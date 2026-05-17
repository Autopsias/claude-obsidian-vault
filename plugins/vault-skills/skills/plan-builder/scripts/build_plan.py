#!/usr/bin/env python3
"""
Build a self-contained HTML plan dashboard from a JSON spec.

Usage:
    python build_plan.py <spec.json> <output.html>

The script reads a plan spec JSON, validates it, then assembles the final HTML
by injecting generated fragments into the base template's marker comments.

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
    """HTML-escape text content."""
    return html.escape(str(s), quote=False) if s is not None else ""

def attr(s):
    """HTML-escape attribute values (with quotes)."""
    return html.escape(str(s), quote=True) if s is not None else ""

def encode_pre(s):
    """Encode text for safe embedding inside a <pre> block. < > & all need escaping."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def today_iso():
    return date.today().isoformat()

# --------------------------------------------------------------------------
# Fragment generators
# --------------------------------------------------------------------------
def gen_session_strip(sessions):
    """Generate the sticky session navigation strip (chips, one per session)."""
    chips = []
    for s in sessions:
        sid = s["id"]
        title_text = f"{sid.upper()} — {s['title']} · {s.get('model','Sonnet')}"
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
    """Generate category filter chips inside the dashboard."""
    chips = ['<div class="cat-filter active" data-cat="all">All</div>',
             '<div class="cat-filter" data-cat="sessions">Session Plan</div>']
    for c in categories:
        chips.append(f'<div class="cat-filter" data-cat="{attr(c["key"])}">{esc(c["label"])}</div>')
    return '\n        '.join(chips)

def gen_cats_array_js(categories):
    """Generate the CATS array literal (without `const CATS =` prefix; template already has that)."""
    lines = ["[",
             "        { key: 'sessions', label: 'Session Plan', type: 'session' },"]
    for c in categories:
        lines.append(f"        {{ key: '{c['key']}', label: \"{esc(c['label'])}\", type: 'item' }},")
    lines.append("      ]")
    return '\n'.join(lines)

# Palette rotation for category accent colors. Skip 'sessions' which always uses purple.
ACCENT_VARS = ['var(--accent)', 'var(--blocked)', 'var(--sonnet)', 'var(--doing)',
               'var(--p1)', 'var(--p2)', 'var(--purple)', 'var(--opus)', 'var(--deferred)']

def gen_category_colors_css(categories):
    """Generate CSS rules assigning each category an accent color."""
    lines = ['  /* category accent palette */',
             '  .cat-row[data-cat="sessions"] { --cat-accent: var(--purple); }']
    for i, c in enumerate(categories):
        accent = ACCENT_VARS[i % len(ACCENT_VARS)]
        lines.append(f'  .cat-row[data-cat="{c["key"]}"] {{ --cat-accent: {accent}; }}')
    return '\n'.join(lines)

def gen_item_article(item, item_to_session):
    """Generate one item card."""
    iid = item["id"]
    sid = item_to_session.get(iid)
    session_link = (
        f'<span class="session-link"><strong>Session:</strong> <a href="#{attr(sid)}">{esc(sid.upper())}</a></span>'
        if sid else
        '<span class="session-link"><strong>Session:</strong> <em style="color:var(--text-subtle);font-style:italic;">trigger-deferred</em></span>'
    )
    pri = item.get("priority", "P3")
    eff = item.get("effort", "M")
    desc = item.get("description", "")
    why = item.get("why", "")
    owner = item.get("owner", "")
    target = item.get("target", "")
    touches = item.get("touches", "")
    updated = item.get("updated", today_iso())
    return f'''  <article class="item" id="{attr(iid)}" data-status="TODO" data-priority="{attr(pri)}" data-cat="{attr(item["category"])}" data-updated="{attr(updated)}">
    <header class="item-head">
      <span class="id-tag">{esc(iid.upper())}</span>
      <h3 class="title">{esc(item["title"])}</h3>
      <span class="pill status-TODO">TODO</span>
      <span class="chip priority-{attr(pri)}">{esc(pri)}</span>
      <span class="chip">Effort: {esc(eff)}</span>
    </header>
    <p class="desc">{esc(desc)}</p>
    {f'<p class="why"><strong>Why:</strong> {esc(why)}</p>' if why else ''}
    <div class="meta-row">
      {session_link}
      {f'<span><strong>Owner:</strong> {esc(owner)}</span>' if owner else ''}
      {f'<span><strong>Target:</strong> {esc(target)}</span>' if target else ''}
      {f'<span><strong>Touches:</strong> <code>{esc(touches)}</code></span>' if touches else ''}
    </div>
    <details class="notes">
      <summary>Notes (0)</summary>
      <div class="notes-content"><span class="empty">No notes yet.</span></div>
    </details>
  </article>'''

def gen_category_section(category, items, item_to_session):
    """Generate a category section with all its item cards."""
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

def closeout_text_for_prompt(items, next_session):
    """Generate the structured CLOSEOUT block embedded in each session prompt."""
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
    """Generate the visible per-session closeout block (mirrors what's in the prompt)."""
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

def gen_session_article(session, sessions_list, idx):
    """Generate one session card with its prompt and closeout."""
    sid = session["id"]
    model = session.get("model", "Sonnet")
    model_lower = model.lower()
    effort = session.get("effort", "")
    why_model = session.get("why_model", "")
    items = session.get("items", [])

    # Find next session
    next_session = None
    next_title = None
    if idx + 1 < len(sessions_list):
        nxt = sessions_list[idx + 1]
        next_session = nxt["id"]
        next_title = nxt["title"]

    item_links = " · ".join(f'<a href="#{i}">{i.upper()}</a>' for i in items)

    # Prompt: user-supplied body + auto-appended closeout
    prompt_body = session.get("prompt", "").rstrip()
    full_prompt = prompt_body + closeout_text_for_prompt(items, next_session)
    prompt_encoded = encode_pre(full_prompt)

    visible_closeout = gen_visible_closeout(sid, items, next_session, next_title)
    updated = session.get("updated", today_iso())

    return f'''  <article class="session" id="{attr(sid)}" data-status="TODO" data-updated="{attr(updated)}">
    <header class="item-head">
      <span class="id-tag id-session">{esc(sid.upper())}</span>
      <h3 class="title">{esc(session["title"])}</h3>
      <span class="pill status-TODO">TODO</span>
      <span class="chip model-{attr(model_lower)}">{esc(model)}</span>
      {f'<span class="chip">{esc(effort)}</span>' if effort else ''}
    </header>
    {f'<p class="model-rec"><strong>Why {esc(model)}:</strong> {esc(why_model)}</p>' if why_model else ''}
    <p class="session-items"><strong>Items:</strong> {item_links}</p>
    <div class="prompt-block">
      <div class="prompt-header"><span class="prompt-label">Prompt to paste into a fresh Cowork session</span><button class="copy-btn" data-target="prompt-{attr(sid)}">Copy</button></div>
<pre class="prompt-text" id="prompt-{attr(sid)}">{prompt_encoded}</pre>
    </div>
{visible_closeout}    <details class="notes"><summary>Notes (0)</summary><div class="notes-content"><span class="empty">No notes yet.</span></div></details>
  </article>
'''

def gen_sessions_block(sessions):
    """Generate all session articles."""
    return '\n'.join(gen_session_article(s, sessions, i) for i, s in enumerate(sessions))

# --------------------------------------------------------------------------
# Plan Achievement infographics (5 templates)
# --------------------------------------------------------------------------
INFOGRAPHIC_RENDERERS = {}  # type -> JS function string

def infographic_phase_journey_data_js(info):
    """Inject PHASES + ANCHORS for phase-journey template."""
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
    """Generate the Plan Achievement HTML section. Same shell for all 5 templates;
    the SVG container is filled by JS based on INFOGRAPHIC_TYPE."""
    info = spec["infographic"]
    title_html = info.get("title", "Plan Achievement")
    eyebrow = info.get("eyebrow", "Plan Achievement · Visual Story")
    narrative = info.get("narrative", "")

    # Pick SVG viewBox based on template (custom uses spec-supplied)
    viewbox = info.get("viewBox") or {
        "phase-journey":   "0 0 1200 240",
        "maturity-ladder": "0 0 800 460",
        "hub-spoke":       "0 0 1000 480",
        "before-after":    "0 0 1100 320",
        "pillars":         "0 0 1100 380",
        "custom":          "0 0 1200 320",
    }.get(info["type"], "0 0 1200 240")

    # For custom type, embed the user-supplied SVG markup directly inside the <svg> shell.
    # Accept either svg_inline (raw string) or svg_inline_file (path to standalone .svg).
    inner_svg = ""
    if info["type"] == "custom":
        if info.get("svg_inline_file"):
            svg_path = Path(info["svg_inline_file"])
            if not svg_path.is_absolute():
                # Resolve relative to the spec file's directory if available, else CWD
                svg_path = Path.cwd() / svg_path
            if svg_path.exists():
                inner_svg = svg_path.read_text()
                # Strip leading XML/HTML comments — keep just the SVG content
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

  {f'<div class="achievement-narrative"><strong>The story:</strong> {esc(narrative)}</div>' if narrative else ''}
</section>'''

def load_infographic_renderers_js():
    """Load JS render functions for all 5 infographic templates from assets/infographics/."""
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

# --------------------------------------------------------------------------
# JS helper that picks the right renderer based on INFOGRAPHIC_TYPE
# --------------------------------------------------------------------------
RENDER_DISPATCH_JS = """
    // Dispatcher: pick the right renderer based on INFOGRAPHIC_TYPE
    // Renderers and data constants are in the same IIFE scope so they share a closure.
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
    }
"""

# --------------------------------------------------------------------------
# Main build
# --------------------------------------------------------------------------
def build(spec, out_path, project_root=None):
    validate_spec(spec)

    template = TEMPLATE_PATH.read_text()

    # Inject a "PLAN_LOCATION" comment at the top of <main> so any future Claude
    # opening the file sees where it lives + how to find related project context.
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

    # Build item-to-session map (for back-links)
    item_to_session = {}
    for s in spec["sessions"]:
        for iid in s["items"]:
            item_to_session[iid] = s["id"]

    # Title + meta
    template = template.replace("{{PLAN_TITLE}}", esc(spec["title"]))
    meta_line = spec.get("subtitle", "")
    if "meta" in spec:
        meta_line = spec["meta"]
    if not meta_line:
        meta_line = f"{len(spec['sessions'])} sessions · {len(spec['items'])} items"
    template = template.replace("{{PLAN_META_LINE}}", meta_line)

    # First session info (for Up Next default render — JS overrides)
    first_sess = spec["sessions"][0] if spec["sessions"] else {"id": "s01", "title": "First session", "model": "Sonnet", "effort": ""}
    template = template.replace("{{FIRST_SESSION_TITLE}}",
                                f"{first_sess['id'].upper()} — {esc(first_sess['title'])}")
    template = template.replace("{{FIRST_SESSION_MODEL}}", esc(first_sess.get("model", "Sonnet")))
    template = template.replace("{{FIRST_SESSION_EFFORT}}", esc(first_sess.get("effort", "")))
    template = template.replace("{{FIRST_SESSION_ID}}", attr(first_sess["id"]))

    # Session plan section-blurb + comment-block count (FU-01 fix 2026-05-14: was hardcoded stale strings)
    session_plan_blurb = f"{len(spec['sessions'])} sessions · {len(spec['items'])} items"
    template = template.replace("{{SESSION_PLAN_BLURB}}", session_plan_blurb)
    template = template.replace("{{SESSION_TOTAL_COUNT}}", str(len(spec["sessions"])))
    template = template.replace("{{ITEM_TOTAL_COUNT}}", str(len(spec["items"])))

    # Generate fragments
    session_strip = gen_session_strip(spec["sessions"])
    cat_chips = gen_category_filter_chips(spec["categories"])
    cats_array = gen_cats_array_js(spec["categories"])
    cat_colors = gen_category_colors_css(spec["categories"])
    plan_achievement = gen_plan_achievement_section(spec)
    sessions_html = gen_sessions_block(spec["sessions"])
    cat_sections = "\n".join(gen_category_section(c, spec["items"], item_to_session) for c in spec["categories"])

    # Infographic — data + renderers all injected at INSERT_INFOGRAPHIC_RENDERERS marker
    # so they share the IIFE closure scope. Renderers reference data constants directly.
    info_type = spec["infographic"]["type"]
    info_data_js = INFOGRAPHIC_DATA_JS[info_type](spec["infographic"])
    # Convert window.render_* declarations to local function declarations so they live in IIFE scope
    renderers_raw = load_infographic_renderers_js()
    renderers_local = re.sub(r'window\.render_(\w+)\s*=\s*function', r'function render_\1', renderers_raw)
    infographic_full_js = info_data_js + "\n" + renderers_local + "\n" + RENDER_DISPATCH_JS

    # Replace markers
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
    """Register the plan in the project's _plans_index.md so future Claude sessions can find it.
    Returns the snippet to suggest adding to CLAUDE.md."""
    project_root = Path(project_root).resolve()
    index_path = project_root / "_plans_index.md"
    rel_path = out_path.resolve().relative_to(project_root) if out_path.resolve().is_relative_to(project_root) else out_path.resolve()

    title = spec["title"]
    today = today_iso()
    n_sessions = len(spec["sessions"])
    n_items = len(spec["items"])

    # Create index if missing, else append/update entry
    if index_path.exists():
        body = index_path.read_text()
    else:
        body = ("# Active Plans\n\n"
                "This file lists all plan dashboards in this project. Each plan is a self-contained\n"
                "HTML file built by the `plan-builder` skill. To execute a session: open the plan,\n"
                "find the session card, copy its prompt, paste into a fresh Cowork session. To\n"
                "update progress: read the plan's Operating Manual at the top of the file.\n\n"
                "## Plans\n\n")

    # Append/update entry — keyed by file path
    entry = f"- **[{title}]({rel_path})** · {n_sessions} sessions · {n_items} items · created {today}\n"
    # Remove existing entry for this file if present
    pattern = re.escape(f"]({rel_path})")
    body = re.sub(rf'^- \*\*\[[^\]]+\]\({re.escape(str(rel_path))}\).*\n', '', body, flags=re.MULTILINE)
    body = body.rstrip() + "\n" + entry

    index_path.write_text(body)

    # Snippet for CLAUDE.md / handoff
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
                        help="Register the plan in <PROJECT_ROOT>/_plans_index.md so future Claude sessions can find it. "
                             "Recommended: pass the project root the user is working in.")
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
