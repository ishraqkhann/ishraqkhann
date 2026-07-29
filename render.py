"""
Turns config.py + a bag of live numbers into SVG.

The reference implementation this repo is forked from kept two hand-written SVG
files and patched numbers into them by element id. That works for two themes.
It does not work for three, and it means every layout tweak has to be made
twice by hand.

Here the SVG is generated. config.py is the content, themes.py is the paint,
this file is the typesetter. Adding a theme costs one dict.

Layout model
------------
Everything is a monospace grid. `INFO_COLS` characters wide, one row per line.
Dot leaders are computed so that every value ends on the same column, which is
what gives the card its aligned right edge.
"""

from __future__ import annotations

import datetime

import config
import themes

# Box-drawing horizontal rule. Present in Consolas, DejaVu Sans Mono,
# Liberation Mono, Menlo and SF Mono, and unlike a run of hyphens it tiles into
# a continuous line.
RULE_CHAR = "─"
BAR_FULL = "█"
BAR_EMPTY = "░"

FONT_STACK = (
    "ConsolasFallback,Consolas,'DejaVu Sans Mono',"
    "'Liberation Mono',Menlo,monospace"
)

# Advance width of one character, in px, per 1px of font-size. See the note in
# themes.py for where 0.599 comes from.
CELL_RATIO = 0.599


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------


def esc(text: str) -> str:
    """XML-escape. ASCII portraits are full of & < > and will break the file."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def leader(width: int) -> str:
    """A dot leader of exactly `width` characters, padded with a space either side."""
    if width <= 0:
        return " "
    if width == 1:
        return " "
    if width == 2:
        return "  "
    return " " + ("." * (width - 2)) + " "


def span_len(spans) -> int:
    """
    A span is (class, text) or (class, text, href). Only the text counts toward
    the 60-column grid; the href is presentation.
    """
    return sum(len(span[1]) for span in spans)


# --------------------------------------------------------------------------
# Line composition
#
# A composed line is a list of (class, text) pairs. `class` maps onto a CSS
# class in the generated stylesheet.
# --------------------------------------------------------------------------


def compose_key(key: str):
    """`Languages.Programming` -> highlight each dotted segment separately."""
    out = []
    parts = key.split(".")
    for i, part in enumerate(parts):
        if i:
            out.append(("kk", "."))
        out.append(("k", part))
    return out


def compose_row(key: str, value: str, width: int, href=None):
    head = [("d", ". ")] + compose_key(key) + [("kk", ":")]
    used = span_len(head) + len(value)
    tail = ("v", value, href) if href else ("v", value)
    return head + [("d", leader(width - used))] + [tail]


def compose_rule(title: str, width: int):
    head = f"{RULE_CHAR} {title} " if title else ""
    fill = RULE_CHAR * max(0, width - len(head))
    return [("r", RULE_CHAR + " "), ("t", title), ("r", " " + fill)] if title else [
        ("r", RULE_CHAR * width)
    ]


def compose_header(user: str, host: str, width: int):
    head = [("k", user), ("kk", "@"), ("v", host), ("r", " ")]
    return head + [("r", RULE_CHAR * max(0, width - span_len(head)))]


def compose_raw(spans, live, width: int):
    """
    Expand a config.Raw into a composed line.

    Slack is distributed across the ("dots", weight) slots so that lines with
    two columns keep their separator roughly in place as the numbers grow.
    """
    expanded = []
    dot_slots = []
    for span in spans:
        kind = span[0]
        if kind == "dots":
            weight = span[1] if len(span) > 1 else 1
            dot_slots.append(len(expanded))
            expanded.append([("d", ""), max(1, weight)])
        elif kind in ("live", "add", "del"):
            cls = {"live": "v", "add": "a", "del": "x"}[kind]
            expanded.append([(cls, fmt(live.get(span[1], 0))), 0])
        elif kind == "key":
            for cls, text in compose_key(span[1]):
                expanded.append([(cls, text), 0])
        else:
            cls = {"dim": "d", "plain": "kk"}.get(kind, "kk")
            expanded.append([(cls, span[1]), 0])

    fixed = sum(len(item[0][1]) for item in expanded)
    slack = max(len(dot_slots), width - fixed)

    total_weight = sum(expanded[i][1] for i in dot_slots) or 1
    handed_out = 0
    for n, index in enumerate(dot_slots):
        if n == len(dot_slots) - 1:
            take = slack - handed_out
        else:
            take = max(1, slack * expanded[index][1] // total_weight)
            handed_out += take
        expanded[index][0] = ("d", leader(take))

    return [item[0] for item in expanded]


def compose_xp_bar(live, width: int):
    level = live.get("level", 0)
    current = live.get("xp_current", 0)
    needed = live.get("xp_needed", config.XP_PER_LEVEL)
    cells = config.XP_BAR_CELLS

    filled = 0 if needed <= 0 else min(cells, round(cells * current / needed))
    bar = BAR_FULL * filled + BAR_EMPTY * (cells - filled)
    tail = f"{fmt(current)}/{fmt(needed)} XP"

    head = [("d", ". "), ("k", "Level"), ("kk", " "), ("v", str(level)), ("kk", " ")]
    body = [("bf", BAR_FULL * filled), ("be", BAR_EMPTY * (cells - filled))]
    used = span_len(head) + len(bar) + len(tail) + 2  # brackets
    return (
        head
        + [("d", "[")]
        + body
        + [("d", "]")]
        + [("d", leader(width - used))]
        + [("a", tail)]
    )


def compose_prompt(user: str, host: str):
    return [("k", user), ("kk", "@"), ("v", host), ("kk", ":~$ ")]


def fmt(value):
    return f"{value:,}" if isinstance(value, int) else str(value)


def build_lines(live):
    """config.SECTIONS -> a list of composed lines."""
    width = config.INFO_COLS
    lines = [compose_header(config.PROMPT_USER, config.PROMPT_HOST, width)]

    for item in config.SECTIONS:
        if isinstance(item, config.Blank):
            lines.append([("d", ".")])
        elif isinstance(item, config.Rule):
            lines.append(compose_rule(item.title, width))
        elif isinstance(item, config.Raw):
            lines.append(compose_raw(item.spans, live, width))
        elif isinstance(item, config.XPBar):
            lines.append(compose_xp_bar(live, width))
        elif isinstance(item, config.Row):
            value = item.value
            if isinstance(value, config.LIVE):
                value = fmt(live.get(value.field, ""))
            lines.append(compose_row(item.key, str(value), width, item.href))

    lines.append(compose_prompt(config.PROMPT_USER, config.PROMPT_HOST))
    return lines


# --------------------------------------------------------------------------
# ASCII portrait
# --------------------------------------------------------------------------


def load_portrait(path=None, strict=False):
    """
    Read the portrait, pad/crop it to exactly ASCII_COLS x ASCII_ROWS, and
    report anything that had to be corrected.
    """
    path = path or config.ASCII_ART_FILE
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read().replace("\t", "    ").split("\n")

    while raw and not raw[-1].strip():
        raw.pop()

    problems = []
    for i, line in enumerate(raw):
        if len(line) > config.ASCII_COLS:
            problems.append(
                f"  line {i + 1}: {len(line)} chars, {config.ASCII_COLS} allowed "
                f"(cropped)"
            )
    if len(raw) > config.ASCII_ROWS:
        problems.append(
            f"  {len(raw)} rows, {config.ASCII_ROWS} allowed (cropped)"
        )

    rows = [line[: config.ASCII_COLS].ljust(config.ASCII_COLS) for line in raw]
    rows = rows[: config.ASCII_ROWS]
    while len(rows) < config.ASCII_ROWS:
        rows.append(" " * config.ASCII_COLS)

    if problems:
        message = (
            f"{path} does not fit the {config.ASCII_COLS}x{config.ASCII_ROWS} grid:\n"
            + "\n".join(problems)
        )
        if strict:
            raise ValueError(message)
        print("warning:", message)

    return rows


# --------------------------------------------------------------------------
# SVG assembly
# --------------------------------------------------------------------------


def stylesheet(theme) -> str:
    """
    Two kinds of motion live here.

    Ambient - a slow light sweep down the portrait, a staggered boot reveal, a
    blinking cursor. These are declarative CSS/SMIL and they DO run inside the
    <img> tag GitHub renders a README image in.

    Hover - the portrait resolving into focus, a faster sweep, a chromatic
    edge. These only fire where the SVG is a live document: opened directly,
    or embedded with <object> or inline on your own site. Pointer events never
    reach an SVG inside an <img>, so GitHub will show the ambient layer only.
    Nothing breaks, the hover rules are simply inert there.
    """
    chrome = theme["chrome"]
    return f"""
    @font-face {{
      font-family: 'ConsolasFallback';
      src: local('Consolas'), local('Consolas Bold');
      font-display: swap;
      size-adjust: 109%;
    }}
    text, tspan {{ white-space: pre; }}
    .k  {{ fill: {theme['key']}; }}
    .kk {{ fill: {theme['text']}; }}
    .v  {{ fill: {theme['value']}; }}
    .a  {{ fill: {theme['add']}; }}
    .x  {{ fill: {theme['delete']}; }}
    .d  {{ fill: {theme['dim']}; }}
    .r  {{ fill: {theme['rule']}; }}
    .t  {{ fill: {theme['key']}; }}
    .bf {{ fill: {theme['bar_fill']}; }}
    .be {{ fill: {theme['bar_empty']}; }}

    @keyframes boot {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .ln {{ animation: boot .34s ease-out backwards; }}
    .px {{ animation: boot .3s ease-out backwards; }}

    @keyframes breathe {{
      0%, 100% {{ opacity: .88; }}
      50%      {{ opacity: 1; }}
    }}
    .portrait-base {{
      animation: breathe 7s ease-in-out infinite;
      fill: {theme['ascii']};
    }}

    .portrait-glow {{
      fill: {theme['ascii_glow']};
      opacity: {theme['sweep_opacity']};
    }}

    /* Density tiers. See DENSITY in render.py. */
    .t0 {{ fill-opacity: {theme['tier0']}; }}
    .t1 {{ fill-opacity: {theme['tier1']}; }}
    .t2 {{ fill-opacity: 1; }}

    /* Hover: only reachable where the SVG is a live document, never in an
       img tag. See the note on this function. */
    .portrait {{ cursor: crosshair; }}
    .portrait .hit {{ fill: transparent; pointer-events: all; }}
    .portrait .portrait-base {{ transition: opacity .35s ease; }}
    .portrait .portrait-glow {{ transition: opacity .35s ease; }}
    .portrait .chroma {{ opacity: 0; transition: opacity .35s ease; }}
    .portrait:hover .portrait-base {{ animation: none; opacity: 1; }}
    .portrait:hover .portrait-glow {{ opacity: 1; }}
    .portrait:hover .chroma {{ opacity: .5; }}
    .portrait:hover .sweep-band {{ animation: none; }}

    /* Window buttons. The close button really does close the window - see
       closed_panel() - but only where the SVG is a live document. */
    .tl {{ cursor: pointer; }}
    .tlg {{ opacity: 0; transition: opacity .12s ease; }}
    .lights:hover .tlg {{ opacity: .62; }}
    #reopen {{ cursor: pointer; }}

    /* Links. Same story as hover: live wherever the SVG is a real document,
       inert inside GitHub's img tag. */
    .lnk {{ cursor: pointer; }}
    .lnk tspan {{ transition: fill .15s ease; }}
    .lnk:hover tspan {{ fill: {theme['ascii_glow']}; text-decoration: underline; }}

    @keyframes blink {{ 0%, 49% {{ opacity: 1; }} 50%, 100% {{ opacity: 0; }} }}
    .cursor {{ fill: {theme['cursor']}; animation: blink 1.06s steps(1) infinite; }}
    """


def text_block(lines, x, y0, dy, font_size, cls, stagger, extra=""):
    out = [
        f'<text x="{x}" y="{y0}" font-size="{font_size}px" '
        f'xml:space="preserve"{extra}>'
    ]
    for i, spans in enumerate(lines):
        delay = f"{i * stagger:.3f}s"
        parts = []
        for span in spans:
            cls_name, text = span[0], span[1]
            href = span[2] if len(span) > 2 else None
            piece = (
                f'<tspan class="{cls_name}">{esc(text)}</tspan>'
                if cls_name
                else esc(text)
            )
            if href:
                # SVG <a> around a tspan. Live document only - inside an <img>
                # the link is never traversable. See SETUP.md section 5.
                piece = (
                    f'<a class="lnk" href="{esc(href)}" target="_blank" '
                    f'rel="noopener noreferrer">{piece}</a>'
                )
            parts.append(piece)
        body = "".join(parts)
        out.append(
            f'<tspan class="{cls}" x="{x}" y="{y0 + i * dy}" '
            f'style="animation-delay:{delay}">{body}</tspan>'
        )
    out.append("</text>")
    return "\n".join(out)


# ASCII art encodes brightness as glyph density, but an SVG draws every glyph
# at the same colour - so a mid-density background ends up just as loud as the
# subject. Bucketing characters by density and dropping the opacity of the
# quiet ones restores the tonal range the art was drawn with.
DENSITY = {
    0: " .'`^\",:;-_~=!ilI",
    1: "+*<>?][}{()|\\/rjtfxnuvczYXUJCLQ",
    2: "#%@$&80OZmwqpdbkhaoMWB",
}
_TIER = {ch: tier for tier, chars in DENSITY.items() for ch in chars}


def density_runs(line: str):
    """Collapse a row into (tier, text) runs so we emit tens of spans, not 76."""
    runs = []
    for ch in line:
        tier = _TIER.get(ch, 1)
        if runs and runs[-1][0] == tier:
            runs[-1][1].append(ch)
        else:
            runs.append((tier, [ch]))
    return [(tier, "".join(chars)) for tier, chars in runs]


def portrait_block(rows, x, y0):
    """
    Portrait, drawn three times:
      1. chroma  - two offset copies, invisible until hover
      2. base    - the portrait itself, slowly breathing
      3. glow    - a bright copy revealed only through the moving sweep mask
    """
    dy = themes.ASCII_DY
    size = themes.ASCII_FONT
    height = (len(rows) - 1) * dy + size * 2
    width = int(config.ASCII_COLS * size * CELL_RATIO) + 12

    def layer(cls, offset=0, extra="", tiered=False):
        out = [
            f'<text x="{x + offset}" y="{y0}" font-size="{size}px" '
            f'xml:space="preserve" class="{cls}"{extra}>'
        ]
        for i, line in enumerate(rows):
            if tiered:
                body = "".join(
                    f'<tspan class="t{tier}">{esc(text)}</tspan>'
                    for tier, text in density_runs(line)
                )
            else:
                body = esc(line)
            out.append(
                f'<tspan class="px" x="{x + offset}" y="{y0 + i * dy}" '
                f'style="animation-delay:{i * 0.009:.3f}s">{body}</tspan>'
            )
        out.append("</text>")
        return "\n".join(out)

    band_top = y0 - size * 2
    band_travel = height + size * 4

    return f"""<g class="portrait">
<defs>
  <linearGradient id="sweepGrad" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%"   stop-color="#fff" stop-opacity="0"/>
    <stop offset="35%"  stop-color="#fff" stop-opacity=".85"/>
    <stop offset="50%"  stop-color="#fff" stop-opacity="1"/>
    <stop offset="65%"  stop-color="#fff" stop-opacity=".85"/>
    <stop offset="100%" stop-color="#fff" stop-opacity="0"/>
  </linearGradient>
  <mask id="sweepMask">
    <rect class="sweep-band" x="{x - 10}" y="{band_top}" width="{width}" height="150"
          fill="url(#sweepGrad)">
      <animate attributeName="y"
               values="{band_top - 150};{band_top - 150};{band_top + band_travel};{band_top + band_travel}"
               keyTimes="0;0.10;0.68;1"
               dur="9s" repeatCount="indefinite"/>
    </rect>
  </mask>
</defs>
<g class="chroma">
{layer('portrait-base', offset=-1.5, extra=' fill="#ff2d55"')}
{layer('portrait-base', offset=1.5, extra=' fill="#00d4ff"')}
</g>
{layer('portrait-base', tiered=True)}
<g mask="url(#sweepMask)">
{layer('portrait-glow', tiered=True)}
</g>
<rect class="hit" x="{x - 8}" y="{y0 - size}" width="{width}" height="{height}"/>
</g>"""


# --------------------------------------------------------------------------
# Window chrome
# --------------------------------------------------------------------------


def rounded_top(x, y, w, h, r):
    """A rect with only its top two corners rounded."""
    return (
        f"M{x} {y + r} A{r} {r} 0 0 1 {x + r} {y} H{x + w - r} "
        f"A{r} {r} 0 0 1 {x + w} {y + r} V{y + h} H{x} Z"
    )


# Bare "Helvetica" is deliberately absent: on Windows it resolves through font
# substitution to an oblique face and every label comes out italic.
UI_FONT = (
    "-apple-system,BlinkMacSystemFont,'SF Pro Text','Segoe UI',Roboto,"
    "'Helvetica Neue',Arial,sans-serif"
)


def mac_chrome(theme, x, y, w, h, title=None, body_bg=None):
    """
    A macOS window: rounded corners, a graphite title bar with the three
    traffic lights, a centred semibold title, and a soft drop shadow.
    """
    c = theme["chrome"]
    top, r = c["top"], c["radius"]
    title = c["title"] if title is None else title
    body_bg = theme["bg"] if body_bg is None else body_bg

    # Glyphs sit hidden until the cluster is hovered, exactly like the real ones.
    glyphs = (
        '<path d="M-2.1 -2.1 L2.1 2.1 M2.1 -2.1 L-2.1 2.1"/>',
        '<path d="M-2.6 0 H2.6"/>',
        '<path d="M0 -2.6 V2.6 M-2.6 0 H2.6"/>',
    )
    ids = ("btnClose", "btnMin", "btnZoom")

    lights = "".join(
        f'<g id="{ids[i]}" class="tl">'
        f'<circle cx="{x + 20 + i * 20}" cy="{y + top / 2}" r="6" '
        f'fill="{fill}" stroke="{rim}" stroke-width="0.5"/>'
        f'<circle cx="{x + 20 + i * 20}" cy="{y + top / 2 - 1.8}" r="2.6" '
        f'fill="#ffffff" fill-opacity=".22"/>'
        f'<g class="tlg" transform="translate({x + 20 + i * 20},{y + top / 2})" '
        f'stroke="#4a1010" stroke-width="1.3" stroke-linecap="round" '
        f'fill="none">{glyphs[i]}</g>'
        # Transparent disc so the click target is comfortable, not pixel-perfect.
        f'<circle cx="{x + 20 + i * 20}" cy="{y + top / 2}" r="9" '
        f'fill="transparent"/>'
        f"</g>"
        for i, (fill, rim) in enumerate(themes.TRAFFIC)
    )
    return f"""
<defs>
  <linearGradient id="macBar" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{c['bar_top']}"/>
    <stop offset="100%" stop-color="{c['bar_bottom']}"/>
  </linearGradient>
</defs>
<g filter="url(#drop)">
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{body_bg}"/>
  <path d="{rounded_top(x, y, w, top, r)}" fill="url(#macBar)"/>
  <path d="{rounded_top(x + 0.5, y + 0.5, w - 1, top, r)}" fill="none"
        stroke="{c['highlight']}" stroke-opacity="{c['highlight_opacity']}"/>
  <line x1="{x}" y1="{y + top}" x2="{x + w}" y2="{y + top}"
        stroke="{c['divider']}"/>
  <g class="lights">{lights}</g>
  <text x="{x + w / 2}" y="{y + top / 2 + 4.5}" text-anchor="middle"
        font-family="{UI_FONT}"
        font-size="13px" font-weight="600" fill="{c['title_fill']}"
        >{esc(title)}</text>
  <rect x="{x + 0.5}" y="{y + 0.5}" width="{w - 1}" height="{h - 1}" rx="{r}"
        fill="none" stroke="{theme['border']}" stroke-opacity=".6"/>
</g>"""


def closed_panel(theme, x, y, w, h, note="[ process completed ]"):
    """
    What is left after you click the close button: the same footprint, dashed,
    with the line Terminal.app actually prints when a shell exits. Clicking it
    puts the window back.

    Driven entirely by SMIL <set> elements keyed on click events - no script,
    which matters because these files are served under a
    `default-src 'none'` CSP that would block inline JS anyway.
    """
    cx, cy = x + w / 2, y + h / 2
    return f"""<g id="closed" display="none">
  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{theme['bg']}"
        fill-opacity=".35" stroke="{theme['dim']}" stroke-opacity=".5"
        stroke-width="1.5" stroke-dasharray="8 6"/>
  <text x="{cx}" y="{cy - 4}" text-anchor="middle" font-size="15px"
        fill="{theme['dim']}">{esc(note)}</text>
  <text x="{cx}" y="{cy + 22}" text-anchor="middle" font-size="13px"
        fill="{theme['dim']}" fill-opacity=".7">click anywhere to reopen</text>
  <rect id="reopen" x="{x}" y="{y}" width="{w}" height="{h}" rx="12"
        fill="transparent"/>
  <set attributeName="display" to="inline" begin="btnClose.click" fill="freeze"/>
  <set attributeName="display" to="none" begin="reopen.click" fill="freeze"/>
</g>"""


def xp_chrome(theme, width, height, build_date):
    """Windows XP Luna: title bar, window buttons, taskbar, Start button, clock."""
    c = theme["chrome"]
    top, bottom, frame = c["top"], c["bottom"], c["frame"]
    a, b, d = c["titlebar"]
    t1, t2 = c["taskbar"]
    s1, s2 = c["start"]

    title_y = top / 2 + 5
    btn_y = (top - 18) / 2
    btn_x = width - 4 - 66

    def button(x, fill, glyph, glyph_dx, glyph_dy, close=False):
        stroke = "#ffffff"
        wrap_id = ' id="btnClose"' if close else ""
        return (
            f'<g{wrap_id} class="tl">'
            f'<rect x="{x}" y="{btn_y}" width="20" height="18" rx="3" '
            f'fill="{fill}" stroke="#ffffff" stroke-opacity=".55"/>'
            f'<g stroke="{stroke}" stroke-width="1.6" stroke-linecap="round" '
            f'transform="translate({x + glyph_dx},{btn_y + glyph_dy})">{glyph}</g>'
            f'<rect x="{x - 2}" y="{btn_y - 2}" width="24" height="22" '
            f'fill="transparent"/>'
            f"</g>"
        )

    minimize = button(btn_x, "#3f7ce0", '<path d="M0 6 H8"/>', 6, 6)
    maximize = button(
        btn_x + 22,
        "#3f7ce0",
        '<rect x="0" y="0" width="8" height="7" fill="none"/>',
        6,
        5,
    )
    close = button(
        btn_x + 44,
        "#e0563c",
        '<path d="M0 0 L8 7 M8 0 L0 7"/>',
        6,
        5,
        close=True,
    )

    taskbar_y = height - bottom

    return f"""
<defs>
  <linearGradient id="xpTitle" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{b}"/>
    <stop offset="12%" stop-color="{a}"/>
    <stop offset="55%" stop-color="{a}"/>
    <stop offset="100%" stop-color="{d}"/>
  </linearGradient>
  <linearGradient id="xpTask" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{t2}"/>
    <stop offset="14%" stop-color="{t1}"/>
    <stop offset="100%" stop-color="{t1}"/>
  </linearGradient>
  <linearGradient id="xpStart" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="{s2}"/>
    <stop offset="55%" stop-color="{s1}"/>
    <stop offset="100%" stop-color="#2f7030"/>
  </linearGradient>
</defs>
<path d="M0 {c['radius']} A {c['radius']} {c['radius']} 0 0 1 {c['radius']} 0
         H {width - c['radius']} A {c['radius']} {c['radius']} 0 0 1 {width} {c['radius']}
         V {height} H 0 Z" fill="{theme['border']}"/>
<path d="M0 {c['radius']} A {c['radius']} {c['radius']} 0 0 1 {c['radius']} 0
         H {width - c['radius']} A {c['radius']} {c['radius']} 0 0 1 {width} {c['radius']}
         V {top} H 0 Z" fill="url(#xpTitle)"/>
<circle cx="16" cy="{top / 2}" r="7" fill="#ffffff" fill-opacity=".9"/>
<text x="30" y="{title_y}" font-size="13px" font-family="Tahoma,Verdana,Segoe UI,sans-serif"
      font-weight="bold" fill="#ffffff">{esc(c['title'])}</text>
{minimize}{maximize}{close}
<rect x="{frame}" y="{top}" width="{width - frame * 2}"
      height="{height - top - bottom - frame}" fill="{theme['bg']}"/>
<rect x="0" y="{taskbar_y}" width="{width}" height="{bottom}" fill="url(#xpTask)"/>
<rect x="0" y="{taskbar_y}" width="{width}" height="1.5" fill="#5b9ef5"/>
<rect x="6" y="{taskbar_y + 5}" width="86" height="{bottom - 10}" rx="9"
      fill="url(#xpStart)"/>
<text x="26" y="{taskbar_y + bottom / 2 + 5}" font-size="15px"
      font-family="Tahoma,Verdana,Segoe UI,sans-serif" font-weight="bold" font-style="italic"
      fill="#ffffff">start</text>
<rect x="{width - 116}" y="{taskbar_y + 5}" width="110" height="{bottom - 10}"
      fill="#1a4fc4" fill-opacity=".7"/>
<text x="{width - 106}" y="{taskbar_y + bottom / 2 + 4}" font-size="11px"
      font-family="Tahoma,Verdana,Segoe UI,sans-serif" fill="#ffffff">{esc(build_date)}</text>
"""


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def window_shell(
    theme,
    card_w,
    card_h,
    title,
    body_fn,
    extra_defs="",
    closed_note="[ process completed ]",
    chrome_fn=None,
    body_bg=None,
):
    """
    A complete, standalone macOS window as an SVG document.

    `body_fn(ox, oy)` is handed the top-left of the window's content area and
    returns the SVG for whatever goes inside. Everything else - chrome, shadow,
    the working close button, the stylesheet - is handled here.

    Every window is its own file, so the `win` / `closed` / `btnClose` ids never
    collide even though they are reused across all of them.
    """
    chrome = theme["chrome"]
    pad = chrome.get("pad", 0)
    width, height = card_w + pad * 2, card_h + pad * 2
    ox, oy = pad, pad + chrome["top"]

    if chrome_fn is not None:
        background = chrome_fn(theme, pad, pad, card_w, card_h)
    else:
        background = mac_chrome(theme, pad, pad, card_w, card_h, title, body_bg)

    shadow = (
        f'<filter id="drop" x="-20%" y="-20%" width="140%" height="140%">'
        f'<feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#000000" '
        f'flood-opacity="{chrome.get("shadow_opacity", 0.4)}"/></filter>'
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}px" height="{height}px"
     viewBox="0 0 {width} {height}" font-family="{FONT_STACK}"
     font-size="{themes.INFO_FONT}px" fill="{theme['text']}"
     role="img" aria-label="{esc(title)}">
<title>{esc(title)}</title>
<style><![CDATA[{stylesheet(theme)}]]></style>
<defs>{shadow}{extra_defs}</defs>
<g id="win">
{background}
{body_fn(ox, oy)}
<set attributeName="display" to="none" begin="btnClose.click" fill="freeze"/>
<set attributeName="display" to="inline" begin="reopen.click" fill="freeze"/>
</g>
{closed_panel(theme, pad, pad, card_w, card_h, closed_note)}
</svg>
"""


def terminal_parts(theme, live, portrait):
    """
    The Terminal window, decomposed so it can either stand alone as its own
    file or be dropped onto the desktop in ui.py.

    Returns (card_w, card_h, body_fn) where body_fn(ox, oy) draws the contents
    at an arbitrary origin.
    """
    lines = build_lines(live)
    chrome = theme["chrome"]

    info_span = themes.INFO_Y0 + (len(lines) - 1) * themes.INFO_DY
    ascii_span = themes.ASCII_Y0 + (len(portrait) - 1) * themes.ASCII_DY
    body_h = max(info_span, ascii_span) + 26

    card_w = themes.CARD_W
    card_h = body_h + chrome["top"] + chrome["bottom"]

    def body(ox, oy):
        info = text_block(
            lines,
            ox + themes.INFO_X,
            oy + themes.INFO_Y0,
            themes.INFO_DY,
            themes.INFO_FONT,
            "ln",
            0.018,
        )
        cell = themes.INFO_FONT * CELL_RATIO
        cursor_x = ox + themes.INFO_X + span_len(lines[-1]) * cell
        cursor_y = oy + themes.INFO_Y0 + (len(lines) - 1) * themes.INFO_DY - 12
        cursor = (
            f'<rect class="cursor" x="{cursor_x:.1f}" y="{cursor_y}" '
            f'width="{cell:.1f}" height="15" rx="1"/>'
        )
        portrait_svg = portrait_block(
            portrait, ox + themes.ASCII_X, oy + themes.ASCII_Y0
        )
        return f"{portrait_svg}\n{info}\n{cursor}"

    return card_w, card_h, body


def build(theme, live, portrait=None, build_date=None) -> str:
    portrait = portrait or load_portrait()
    build_date = build_date or datetime.date.today().isoformat()
    lines = build_lines(live)
    chrome = theme["chrome"]

    info_span = themes.INFO_Y0 + (len(lines) - 1) * themes.INFO_DY
    ascii_span = themes.ASCII_Y0 + (len(portrait) - 1) * themes.ASCII_DY
    body_h = max(info_span, ascii_span) + 26

    card_w = themes.CARD_W
    card_h = body_h + chrome["top"] + chrome["bottom"]

    def body(ox, oy):
        info = text_block(
            lines,
            ox + themes.INFO_X,
            oy + themes.INFO_Y0,
            themes.INFO_DY,
            themes.INFO_FONT,
            "ln",
            0.018,
        )
        # Blinking block cursor, parked at the end of the prompt line.
        cell = themes.INFO_FONT * CELL_RATIO
        cursor_x = ox + themes.INFO_X + span_len(lines[-1]) * cell
        cursor_y = oy + themes.INFO_Y0 + (len(lines) - 1) * themes.INFO_DY - 12
        cursor = (
            f'<rect class="cursor" x="{cursor_x:.1f}" y="{cursor_y}" '
            f'width="{cell:.1f}" height="15" rx="1"/>'
        )
        portrait_svg = portrait_block(
            portrait, ox + themes.ASCII_X, oy + themes.ASCII_Y0
        )
        return f"{portrait_svg}\n{info}\n{cursor}"

    chrome_fn = None
    if chrome["kind"] == "xp":
        def chrome_fn(th, x, y, w, h):
            return (
                f'<g filter="url(#drop)" transform="translate({x},{y})">'
                + xp_chrome(th, w, h, build_date)
                + "</g>"
            )

    return window_shell(
        theme,
        card_w,
        card_h,
        theme["chrome"].get("title", "Terminal"),
        body,
        chrome_fn=chrome_fn,
    )


def write_all(live, strict=False):
    """Render the Terminal window in every theme, plus the rest of the desktop."""
    import ui  # imported here so ui.py can import render without a cycle

    portrait = load_portrait(strict=strict)
    build_date = datetime.date.today().isoformat()
    written = []
    for theme in themes.THEMES:
        svg = build(theme, live, portrait=portrait, build_date=build_date)
        with open(theme["file"], "w", encoding="utf-8", newline="\n") as handle:
            handle.write(svg)
        written.append(theme["file"])
    written.extend(ui.write_all(live, portrait, build_date))
    return written


def validate(live):
    """Warn about anything that will render outside the card."""
    lines = build_lines(live)
    issues = []
    for i, spans in enumerate(lines):
        length = span_len(spans)
        if length > config.INFO_COLS:
            text = "".join(t for _, t in spans)
            issues.append(
                f"  info line {i + 1} is {length} chars "
                f"(max {config.INFO_COLS}): {text.strip()[:50]}..."
            )

    info_right = themes.INFO_X + config.INFO_COLS * themes.INFO_FONT * CELL_RATIO
    if info_right > themes.CARD_W - 8:
        issues.append(
            f"  info column reaches x={info_right:.0f}, card is only "
            f"{themes.CARD_W} wide"
        )

    ascii_right = themes.ASCII_X + config.ASCII_COLS * themes.ASCII_FONT * CELL_RATIO
    if ascii_right > themes.INFO_X - 8:
        issues.append(
            f"  portrait reaches x={ascii_right:.0f}, info column starts at "
            f"{themes.INFO_X}"
        )
    return issues
