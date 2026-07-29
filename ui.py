"""
The rest of the desktop.

`render.py` draws the Terminal window. This module draws everything around it:
the menu bar, the Dock, and the AppKit-style windows that the README opens with
`<details>` — About This Mac, Kodezi, Notes.

Each one is a standalone SVG with working window chrome, so each gets its own
close button for free. They are laid out in absolute coordinates rather than a
character grid, and they use the system font stack instead of a monospace one,
because they are pretending to be AppKit rather than a terminal.
"""

from __future__ import annotations

import base64
import datetime
import io
import os

import config
import render
import themes

UI_FONT = render.UI_FONT
MONO = render.FONT_STACK
esc = render.esc

DESKTOP_W = themes.CARD_W + 40  # match the Terminal window's total width


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------


def text(x, y, body, size=13, fill="#fff", weight=None, anchor=None,
         family=UI_FONT, opacity=None, href=None, cls=None):
    attrs = [
        f'x="{x}"', f'y="{y}"', f'font-size="{size}px"',
        f'font-family="{family}"', f'fill="{fill}"',
    ]
    if weight:
        attrs.append(f'font-weight="{weight}"')
    if anchor:
        attrs.append(f'text-anchor="{anchor}"')
    if opacity is not None:
        attrs.append(f'fill-opacity="{opacity}"')
    if cls:
        attrs.append(f'class="{cls}"')
    out = f'<text {" ".join(attrs)}>{esc(body)}</text>'
    if href:
        out = (
            f'<a class="lnk" href="{esc(href)}" target="_blank" '
            f'rel="noopener noreferrer">{out}</a>'
        )
    return out


def rect(x, y, w, h, r=0, fill="none", stroke=None, opacity=None, extra=""):
    attrs = [f'x="{x}"', f'y="{y}"', f'width="{w}"', f'height="{h}"',
             f'rx="{r}"', f'fill="{fill}"']
    if stroke:
        attrs.append(f'stroke="{stroke}"')
    if opacity is not None:
        attrs.append(f'fill-opacity="{opacity}"')
    return f'<rect {" ".join(attrs)}{extra}/>'


def hrule(x, y, w, colour):
    return f'<line x1="{x}" y1="{y}" x2="{x + w}" y2="{y}" stroke="{colour}"/>'


# The Apple mark, drawn rather than typed - the glyph is not in most fonts and
# renders as tofu when it is missing.
APPLE_PATH = (
    "M12.02 3.36c.63-.78 1.06-1.85.94-2.93-.91.04-2.02.62-2.67 1.39-.58.68"
    "-1.09 1.78-.95 2.83 1.02.08 2.05-.52 2.68-1.29z M16.5 12.9c-.02-2.2 "
    "1.8-3.26 1.88-3.31-1.02-1.5-2.62-1.7-3.18-1.72-1.35-.14-2.64.8-3.32.8"
    "-.69 0-1.74-.78-2.86-.76-1.47.02-2.83.85-3.58 2.17-1.53 2.65-.39 6.57 "
    "1.1 8.72.73 1.05 1.6 2.23 2.74 2.19 1.1-.04 1.52-.71 2.85-.71s1.71.71 "
    "2.87.69c1.19-.02 1.94-1.07 2.66-2.13.84-1.22 1.19-2.4 1.21-2.46-.03"
    "-.01-2.32-.89-2.34-3.53z"
)


def apple(x, y, size, fill):
    s = size / 24.0
    return (
        f'<g transform="translate({x},{y}) scale({s:.4f})" fill="{fill}">'
        f'<path d="{APPLE_PATH}"/></g>'
    )


def button(x, y, w, h, label, ui, href=None, primary=False):
    fill = ui["accent"] if primary else ui["btn"]
    fg = "#ffffff" if primary else ui["btn_fg"]
    body = (
        rect(x, y, w, h, 6, fill, None if primary else ui["sep"])
        + text(x + w / 2, y + h / 2 + 4.5, label, 13, fg, 500, "middle")
    )
    if href:
        body = (
            f'<a class="lnk" href="{esc(href)}" target="_blank" '
            f'rel="noopener noreferrer">{body}</a>'
        )
    return body


def spec_rows(x_label, x_value, y, dy, rows, ui, size=13):
    """A right-aligned label / left-aligned value list, as in About This Mac."""
    out = []
    for i, (label, value) in enumerate(rows):
        yy = y + i * dy
        out.append(text(x_label, yy, label, size, ui["dim"], 400, "end"))
        out.append(text(x_value, yy, value, size, ui["fg"], 500))
    return "\n".join(out)


def ticking_digit(x, y, digits, dur, size, fill, uid):
    """
    A digit that steps through `digits` once every `dur` seconds.

    There is no clock in SVG. SMIL cannot read the wall clock — `wallclock()`
    is in the spec but no browser implements it — and script is blocked, so a
    digit that shows the true current time is not possible in a README. What is
    possible is a slot machine: stack the glyphs, clip to one cell, and step
    the stack with a discrete animateTransform. That runs inside an <img>.

    Only the seconds use this. Seconds nobody can falsify; hours and minutes
    would be visibly wrong, so those stay at build time.
    """
    cell = size * 1.75
    values = ";".join(f"0,{-i * cell:.1f}" for i in range(len(digits)))
    glyphs = "".join(
        f'<text x="0" y="{i * cell:.1f}" font-size="{size}px" fill="{fill}" '
        f'font-family="{UI_FONT}" font-weight="500" '
        f'style="font-variant-numeric:tabular-nums">{d}</text>'
        for i, d in enumerate(digits)
    )
    return (
        f'<defs><clipPath id="clip{uid}">'
        f'<rect x="-1" y="{-size * 0.86:.1f}" width="{size * 0.66:.1f}" '
        f'height="{size * 1.12:.1f}"/></clipPath></defs>'
        f'<g transform="translate({x:.1f},{y:.1f})" clip-path="url(#clip{uid})">'
        f'<g><animateTransform attributeName="transform" type="translate" '
        f'calcMode="discrete" values="{values}" dur="{dur}s" '
        f'repeatCount="indefinite"/>{glyphs}</g></g>'
    )


def ticking_seconds(x, y, size, fill, uid=""):
    """Two digits, 00 through 59, stepping once a second. Tens on a 60s loop,
    ones on a 10s loop — they start together so they stay in phase."""
    return (
        ticking_digit(x, y, "012345", 60, size, fill, f"{uid}st")
        + ticking_digit(x + size * 0.6, y, "0123456789", 10, size, fill,
                        f"{uid}so")
    )


def app_icon(x, y, size, grad_id, c1, c2, glyph, radius=None):
    """A rounded-square app tile with a gradient and a drawn glyph."""
    r = radius if radius is not None else size * 0.23
    return (
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{c1}"/>'
        f'<stop offset="100%" stop-color="{c2}"/></linearGradient></defs>'
        f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="{r}" '
        f'fill="url(#{grad_id})"/>'
        f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{size - 1}" '
        f'height="{size - 1}" rx="{r}" fill="none" stroke="#ffffff" '
        f'stroke-opacity=".18"/>'
        f'<g transform="translate({x + size / 2},{y + size / 2})">{glyph}</g>'
    )


# --------------------------------------------------------------------------
# Menu bar
# --------------------------------------------------------------------------


def menubar(theme, build_date, clock="22:47"):
    ui = theme["ui"]
    w, h = DESKTOP_W, 30
    pad = 8
    total_h = h + pad * 2

    translucent = "#000000" if theme["name"] != "light" else "#ffffff"
    menus = ["File", "Edit", "View", "Window", "Help"]

    items = [
        apple(16, pad + 6, 17, ui["fg"]),
        text(44, pad + h / 2 + 4.5, "Ishraq Khan", 13.5, ui["fg"], 700),
    ]
    x = 158
    for name in menus:
        items.append(text(x, pad + h / 2 + 4.5, name, 13, ui["fg"], 400,
                          opacity=0.85))
        x += len(name) * 7.6 + 22

    # Right side: control-centre pills, battery, clock.
    right = DESKTOP_W - 18
    clock_text = f"{build_date}  {clock}"
    items.append(text(right, pad + h / 2 + 4.5, clock_text, 13, ui["fg"], 400,
                      anchor="end", opacity=0.9))

    bx = right - (len(clock_text) * 7.0) - 26
    # battery
    items.append(rect(bx - 22, pad + h / 2 - 6, 24, 12, 3.5, "none", ui["fg"]))
    items.append(rect(bx - 20.5, pad + h / 2 - 4.5, 18, 9, 2, ui["fg"]))
    items.append(rect(bx + 3, pad + h / 2 - 2.5, 2, 5, 1, ui["fg"]))
    # wifi arcs
    wx = bx - 42
    items.append(
        f'<g transform="translate({wx},{pad + h / 2 + 4})" fill="none" '
        f'stroke="{ui["fg"]}" stroke-width="1.6" stroke-linecap="round">'
        f'<path d="M-8 -7 A 11 11 0 0 1 8 -7"/>'
        f'<path d="M-4.5 -3.5 A 6.5 6.5 0 0 1 4.5 -3.5"/>'
        f'<circle cx="0" cy="0.5" r="1.4" fill="{ui["fg"]}" stroke="none"/></g>'
    )

    body = (
        f'<rect x="0" y="{pad}" width="{w}" height="{h}" rx="9" '
        f'fill="{translucent}" fill-opacity="{0.5 if theme["name"] != "light" else 0.6}"/>'
        f'<rect x="0.5" y="{pad + 0.5}" width="{w - 1}" height="{h - 1}" rx="9" '
        f'fill="none" stroke="{ui["sep"]}" stroke-opacity=".5"/>'
        + "\n".join(items)
    )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}px" height="{total_h}px"
     viewBox="0 0 {w} {total_h}" font-family="{UI_FONT}"
     role="img" aria-label="menu bar">
<title>menu bar</title>
<style><![CDATA[
  text {{ dominant-baseline: auto; }}
  .lnk {{ cursor: pointer; }}
]]></style>
{body}
</svg>
"""


# --------------------------------------------------------------------------
# Dock
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Dock apps
#
# Each entry falls back to a drawn glyph, but if `assets/icons/<key>.png`
# exists it is embedded instead — base64, inline. It has to be inline: these
# SVGs are served under `default-src 'none'; img-src data:`, so a <image href>
# pointing at any URL is blocked, while a data: URI is allowed.
#
# Drop files in at 512x512 and they will be masked into the macOS rounded
# square automatically. See SETUP.md section 8.
# --------------------------------------------------------------------------

ICON_DIR = "assets/icons"

# Drawn in a 100x100 box and scaled to whatever the dock needs. Vector rather
# than PNG for the same reason as the wallpaper: an inlined raster costs ~50 KB
# of base64 per icon per file, a path costs a few hundred bytes and never goes
# soft when GitHub downsamples the hero.
ICON_ART = {
    "kodezi": (
        # Deep indigo tile, K/> mark in the pink -> violet -> blue gradient.
        '<linearGradient id="{u}bg" x1="0" y1="0" x2="0.7" y2="1">'
        '<stop offset="0%" stop-color="#3b3269"/>'
        '<stop offset="45%" stop-color="#231b47"/>'
        '<stop offset="100%" stop-color="#15102f"/></linearGradient>'
        '<linearGradient id="{u}mk" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#ffa8d8"/>'
        '<stop offset="38%" stop-color="#c77df0"/>'
        '<stop offset="70%" stop-color="#8b5cf6"/>'
        '<stop offset="100%" stop-color="#3b5bfd"/></linearGradient>',
        '<g fill="url(#{u}mk)">'
        '<path d="M17 24 H28 V47 L45 24 H58 L38 51 L59 78 H45 L28 55 V78 H17 Z"/>'
        '<path d="M64 24 H75 L58 78 H47 Z"/>'
        '<path d="M78 24 H90 L100 51 L80 78 H68 L86 51 Z"/>'
        "</g>"
    ),
    "linkedin": (
        '<linearGradient id="{u}bg" x1="0" y1="0" x2="0.4" y2="1">'
        '<stop offset="0%" stop-color="#1f7ac4"/>'
        '<stop offset="55%" stop-color="#0a66c2"/>'
        '<stop offset="100%" stop-color="#04529e"/></linearGradient>',
        '<g fill="#f0f3f6">'
        '<circle cx="29" cy="28" r="8"/>'
        '<rect x="21" y="42" width="16" height="36" rx="1.5"/>'
        '<path d="M46 42 H61 V47 C64 42 70 40 75 40 C86 40 92 47 92 60 V78 '
        "H76 V63 C76 57 74 54 69 54 C64 54 62 57 62 63 V78 H46 Z\"/>"
        "</g>"
    ),
    "email": (
        '<linearGradient id="{u}bg" x1="0" y1="0" x2="0.3" y2="1">'
        '<stop offset="0%" stop-color="#8fd3ff"/>'
        '<stop offset="50%" stop-color="#4aa8f7"/>'
        '<stop offset="100%" stop-color="#1a83ea"/></linearGradient>'
        '<linearGradient id="{u}ev" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#ffffff"/>'
        '<stop offset="100%" stop-color="#dbe8f5"/></linearGradient>',
        '<rect x="17" y="30" width="66" height="42" rx="7" fill="url(#{u}ev)"/>'
        '<path d="M17 37 L50 58 L83 37" fill="none" stroke="#9fc3e4" '
        'stroke-width="3.2" stroke-linejoin="round"/>'
        '<path d="M17 37 L50 58 L83 37 L83 34 A5 5 0 0 0 78 30 H22 '
        'A5 5 0 0 0 17 34 Z" fill="#ffffff"/>'
    ),
    "globe": (
        '<linearGradient id="{u}bg" x1="0" y1="0" x2="0.2" y2="1">'
        '<stop offset="0%" stop-color="#ffffff"/>'
        '<stop offset="100%" stop-color="#e8eef4"/></linearGradient>'
        '<linearGradient id="{u}dial" x1="0" y1="0" x2="0.4" y2="1">'
        '<stop offset="0%" stop-color="#3fb9f5"/>'
        '<stop offset="100%" stop-color="#1878d8"/></linearGradient>',
        '<circle cx="50" cy="50" r="34" fill="url(#{u}dial)"/>'
        + "".join(
            '<rect x="49.2" y="{y}" width="1.6" height="{hh}" fill="#ffffff" '
            'fill-opacity=".85" transform="rotate({a} 50 50)"/>'.format(
                a=a, y=18 if a % 90 == 0 else 19, hh=7 if a % 90 == 0 else 4.5)
            for a in range(0, 360, 15)
        )
        + '<path d="M69 31 L54 54 L46 46 Z" fill="#f4453a"/>'
        '<path d="M31 69 L46 46 L54 54 Z" fill="#ffffff"/>'
        '<circle cx="50" cy="50" r="2.6" fill="#ffffff"/>'
    ),
    "x": (
        '<linearGradient id="{u}bg" x1="0" y1="0" x2="0.3" y2="1">'
        '<stop offset="0%" stop-color="#3a3a3d"/>'
        '<stop offset="30%" stop-color="#141416"/>'
        '<stop offset="100%" stop-color="#000000"/></linearGradient>'
        '<linearGradient id="{u}xg" x1="0" y1="0" x2="0.3" y2="1">'
        '<stop offset="0%" stop-color="#ffffff"/>'
        '<stop offset="100%" stop-color="#c8ccd0"/></linearGradient>',
        '<path d="M26 24 H41 L54 43 L69 24 H82 L61 51 L84 78 H69 L54 58 '
        'L38 78 H25 L47 50 Z" fill="url(#{u}xg)"/>'
    ),
}


def drawn_icon(key, x, y, size, uid):
    """One of ICON_ART, as a macOS tile: gradient body, gloss, hairline rim."""
    art = ICON_ART.get(key)
    if art is None:
        return ""
    defs, body = art
    r = 100 * 0.224
    s = size / 100.0
    return (
        "<defs>" + defs.format(u=uid)
        + '<clipPath id="{u}clip"><rect x="0" y="0" width="100" height="100" '
          'rx="{r}"/></clipPath>'.format(u=uid, r=r)
        + '<linearGradient id="{u}gloss" x1="0" y1="0" x2="0" y2="1">'
          '<stop offset="0%" stop-color="#ffffff" stop-opacity=".34"/>'
          '<stop offset="42%" stop-color="#ffffff" stop-opacity=".06"/>'
          '<stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>'
          "</linearGradient>".format(u=uid)
        + "</defs>"
        + '<g transform="translate({x},{y}) scale({s:.5f})">'.format(x=x, y=y, s=s)
        + '<rect width="100" height="100" rx="{r}" fill="url(#{u}bg)"/>'.format(
            r=r, u=uid)
        + '<g clip-path="url(#{u}clip)">'.format(u=uid) + body.format(u=uid)
        + '<rect width="100" height="46" rx="{r}" fill="url(#{u}gloss)"/>'.format(
            r=r, u=uid)
        + "</g>"
        + '<rect x="0.6" y="0.6" width="98.8" height="98.8" rx="{r}" '
          'fill="none" stroke="#ffffff" stroke-opacity=".26" '
          'stroke-width="1.2"/>'.format(r=r)
        + "</g>"
    )


DOCK_APPS = [
    ("globe", "Website"),
    ("kodezi", "Kodezi"),
    ("email", "Email"),
    ("linkedin", "LinkedIn"),
    ("x", "X"),
]

DOCK_LINKS = {
    "globe": config.LINKS["website"],
    "kodezi": config.LINKS["kodezi"],
    "email": "mailto:" + config.LINKS["email"],
    "linkedin": config.LINKS["linkedin"],
    "x": config.LINKS["x"],
}

_ICON_CACHE = {}


def icon_data_uri(key):
    """`assets/icons/<key>.png` as a data: URI, if one has been dropped in."""
    if key in _ICON_CACHE:
        return _ICON_CACHE[key]
    uri = None
    for ext, mime in (("png", "image/png"), ("jpg", "image/jpeg"),
                      ("jpeg", "image/jpeg"), ("webp", "image/webp")):
        path = os.path.join(ICON_DIR, key + "." + ext)
        if os.path.exists(path):
            with open(path, "rb") as handle:
                blob = base64.b64encode(handle.read()).decode("ascii")
            uri = "data:" + mime + ";base64," + blob
            break
    _ICON_CACHE[key] = uri
    return uri


def dock_tile(key, x, y, size, uid):
    """Supplied artwork if there is any, otherwise the drawn vector."""
    uri = icon_data_uri(key)
    if uri:
        r = size * 0.224
        return (
            '<defs><clipPath id="m{u}"><rect x="{x}" y="{y}" width="{s}" '
            'height="{s}" rx="{r:.1f}"/></clipPath></defs>'
            '<image href="{uri}" x="{x}" y="{y}" width="{s}" height="{s}" '
            # No rim here. Supplied artwork already carries its own edge, and
            # a second one just draws a halo around icons whose art does not
            # reach the tile bounds.
            'preserveAspectRatio="xMidYMid slice" clip-path="url(#m{u})"/>'.format(
                u=uid, x=x, y=y, s=size, r=r, uri=uri)
        )
    return drawn_icon(key, x, y, size, uid)


# --------------------------------------------------------------------------
# About This Mac
# --------------------------------------------------------------------------


def about(theme, live, portrait):
    ui = theme["ui"]
    card_w, card_h = 860, 470
    ch = card_h - theme["chrome"]["top"]      # usable content height

    rows = [
        ("Role", "Founder & CEO, Kodezi"),
        ("Origin", "Dhaka, Bangladesh"),
        ("Moved", "United States, 2011"),
        ("Education", "Self-taught. Skipped college."),
        ("Location", "San Francisco, California"),
        ("Languages", "English, Bengali"),
        ("Writes about", "Systems, engineering culture, psychology"),
        ("Uptime", str(live.get("age", ""))),
    ]

    def body(ox, oy):
        parts = []
        # The ASCII portrait again, small, standing in for the Mac hero image.
        px, py = ox + 44, oy + 40
        scale = 0.52
        parts.append(
            f'<g transform="translate({px},{py}) scale({scale})" '
            f'opacity=".92">'
            + render.portrait_block(portrait, 0, 0)
            + "</g>"
        )

        tx = ox + 330
        parts.append(text(tx, oy + 76, "Ishraq Khan", 30, ui["fg"], 700))
        parts.append(
            text(tx, oy + 100, "Founder & CEO · Kodezi", 14, ui["dim"], 500)
        )
        parts.append(hrule(tx, oy + 120, card_w - 330 - 44, ui["sep"]))
        parts.append(
            spec_rows(tx + 116, tx + 132, oy + 152, 27, rows, ui)
        )
        parts.append(
            button(tx, oy + ch - 62, 132, 30, "ishraqkhan.com", ui,
                   config.LINKS["website"])
        )
        parts.append(
            button(tx + 146, oy + ch - 62, 116, 30, "kodezi.com", ui,
                   config.LINKS["kodezi"], primary=True)
        )
        return "\n".join(parts)

    return render.window_shell(
        theme, card_w, card_h, "About This Mac", body,
        closed_note="[ closed ]", body_bg=ui["bg"],
    )


# --------------------------------------------------------------------------
# Kodezi.app
# --------------------------------------------------------------------------


def kodezi(theme, live):
    ui = theme["ui"]
    card_w, card_h = 860, 446
    ch = card_h - theme["chrome"]["top"]

    products = ["Kodezi OS", "CLI", "Code", "Create", "Chronos"]
    bullets = [
        "Remembers — long-term project memory across the whole lifecycle.",
        "Heals — finds and fixes bugs autonomously, then documents them.",
        "Evolves — refines, optimises, enforces best practice as you go.",
        "Governs — security, standards and drift, watched continuously.",
    ]

    def body(ox, oy):
        parts = [
            app_icon(ox + 44, oy + 40, 84, "kodeziIcon", "#7b6cff", "#4b34d6",
                     f'<text x="0" y="14" text-anchor="middle" font-size="46" '
                     f'fill="#ffffff" font-family="{UI_FONT}" '
                     f'font-weight="700">K</text>'),
            text(ox + 148, oy + 72, "Kodezi", 28, ui["fg"], 700),
            text(ox + 148, oy + 96, "The AI CTO for your codebase", 15,
                 ui["dim"], 500),
            text(ox + 148, oy + 120, "4,000,000+ developers", 13,
                 ui["accent"], 600),
            hrule(ox + 44, oy + 152, card_w - 88, ui["sep"]),
            text(ox + 44, oy + 182,
                 "It doesn't autocomplete.", 16, ui["fg"], 600),
        ]
        for i, line in enumerate(bullets):
            parts.append(
                text(ox + 44, oy + 212 + i * 25, "·", 15, ui["accent"], 700)
            )
            parts.append(
                text(ox + 60, oy + 212 + i * 25, line, 14, ui["dim"], 400)
            )

        cx = ox + 44
        for name in products:
            wdt = len(name) * 7.4 + 24
            parts.append(rect(cx, oy + ch - 104, wdt, 26, 13, ui["panel"],
                              ui["sep"]))
            parts.append(
                text(cx + wdt / 2, oy + ch - 86, name, 12.5, ui["fg"],
                     500, "middle")
            )
            cx += wdt + 10

        parts.append(
            button(ox + 44, oy + ch - 58, 150, 30, "Open kodezi.com", ui,
                   config.LINKS["kodezi"], primary=True)
        )
        return "\n".join(parts)

    return render.window_shell(
        theme, card_w, card_h, "Kodezi", body,
        closed_note="[ quit ]", body_bg=ui["bg"],
    )


# --------------------------------------------------------------------------
# Notes
# --------------------------------------------------------------------------


def notes(theme, build_date):
    ui = theme["ui"]
    card_w, card_h = 860, 434
    ch = card_h - theme["chrome"]["top"]

    topics = [
        ("System design", "How systems earn the right to last."),
        ("Engineering culture", "What teams reward, and what that produces."),
        ("Psychology of building", "Why technical decisions are rarely technical."),
    ]

    def body(ox, oy):
        parts = [
            text(ox + 44, oy + 54, build_date, 12, ui["dim"], 400),
            text(ox + 44, oy + 84, "What I write about", 24, ui["fg"], 700),
            hrule(ox + 44, oy + 104, card_w - 88, ui["sep"]),
        ]
        for i, (head, sub) in enumerate(topics):
            yy = oy + 140 + i * 52
            parts.append(
                f'<circle cx="{ox + 52}" cy="{yy - 5}" r="3.5" '
                f'fill="{ui["accent"]}"/>'
            )
            parts.append(text(ox + 68, yy, head, 15.5, ui["fg"], 600))
            parts.append(text(ox + 68, yy + 20, sub, 13.5, ui["dim"], 400))

        parts.append(hrule(ox + 44, oy + ch - 112, card_w - 88, ui["sep"]))
        parts.append(
            text(ox + 44, oy + ch - 80,
                 "If you're building systems that last — in tech, music, or",
                 14.5, ui["fg"], 500)
        )
        parts.append(
            text(ox + 44, oy + ch - 58,
                 "creative work — I'd love to connect.", 14.5, ui["fg"], 500)
        )
        return "\n".join(parts)

    return render.window_shell(
        theme, card_w, card_h, "Notes", body,
        closed_note="[ closed ]", body_bg=ui["bg"],
    )


# --------------------------------------------------------------------------
# The desktop
#
# One image: wallpaper, menu bar, the Terminal window sitting open on it, and
# the Dock. This is the hero of the README.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Wallpaper
#
# Drawn, not photographed. The obvious move is a PNG, but these files are
# served under `default-src 'none'`, so a wallpaper cannot be linked - it has to
# be base64-inlined into every desktop SVG. A full-bleed raster at this size is
# 1-2 MB, which becomes ~2.5 MB of base64, twice over for the two themes, in a
# file GitHub re-fetches on every view. Gradients and bezier sheets cost about
# four kilobytes and stay sharp at any scale.
#
# Drop `assets/wallpaper.png` in and it is used instead. See SETUP.md section 9.
# --------------------------------------------------------------------------

WALLPAPER = {
    "dark": {
        "base": ["#6d5430", "#4a3f38", "#33333c", "#3f4c62"],
        "sheets": [
            ("#c99a4d", "#f3ead9"),
            ("#b9ad96", "#f7f1e7"),
            ("#efe5d3", "#c9bba4"),
            ("#4a4972", "#7787a8"),
            ("#7b95ae", "#d2dee5"),
        ],
        "veil": "#000000",
        "veil_opacity": 0.10,
        "glass": "#0b0b12",
        "glass_opacity": 0.26,
        "sheen_top": 0.20,
        "sheen_bottom": 0.07,
        "rim": 0.30,
        "menu_fg": "#ffffff",
    },
    "light": {
        "base": ["#caa464", "#c6b9a4", "#b9bcc4", "#93a8c0"],
        "sheets": [
            ("#e2b768", "#fdf7ec"),
            ("#d8cfbc", "#ffffff"),
            ("#fbf5e9", "#ddd1bb"),
            ("#7d7ca8", "#a3b1cb"),
            ("#a6bcd0", "#eef4f8"),
        ],
        "veil": "#ffffff",
        "veil_opacity": 0.14,
        "glass": "#ffffff",
        "glass_opacity": 0.30,
        "sheen_top": 0.46,
        "sheen_bottom": 0.16,
        "rim": 0.62,
        "menu_fg": "#16202c",
    },
}

# Each sheet is (fill path, fold path, gradient vector, palette index).
#
# The fill is a closed shape; the fold is only the curved edge of it. They are
# separate because the closed path runs along the canvas borders too, and
# stroking that would draw hard lines down the sides of the screen. Only the
# fold gets the bright edge.
SHEETS = [
    ("M -60 -60 H 780 C 650 220, 320 420, -60 600 Z",
     "M 780 -60 C 650 220, 320 420, -60 600",
     (0, 0, 0.5, 1), 0),
    ("M 600 -60 H 1460 C 1410 260, 1120 500, 610 560 "
     "C 700 350, 685 110, 600 -60 Z",
     "M 1460 -60 C 1410 260, 1120 500, 610 560 C 700 350, 685 110, 600 -60",
     (0.15, 0, 0.9, 1), 1),
    ("M -60 660 C 330 530, 780 670, 1100 1020 L -60 1020 Z",
     "M -60 660 C 330 530, 780 670, 1100 1020",
     (0, 0, 1, 1), 2),
    ("M 540 1020 C 590 700, 830 540, 1210 500 L 1210 1020 Z",
     "M 540 1020 C 590 700, 830 540, 1210 500",
     (0, 0.2, 0.8, 1), 3),
    ("M 960 1020 C 1040 630, 1225 515, 1460 470 L 1460 1020 Z",
     "M 960 1020 C 1040 630, 1225 515, 1460 470",
     (0.1, 0, 1, 1), 4),
]


def wallpaper_defs(wp, uid="w"):
    out = [
        f'<linearGradient id="{uid}base" x1="0" y1="0" x2="0.75" y2="1">'
        + "".join(
            f'<stop offset="{i * 100 // (len(wp["base"]) - 1)}%" stop-color="{c}"/>'
            for i, c in enumerate(wp["base"])
        )
        + "</linearGradient>"
    ]
    for i, (_, _fold, vec, idx) in enumerate(SHEETS):
        c1, c2 = wp["sheets"][idx]
        x1, y1, x2, y2 = vec
        out.append(
            f'<linearGradient id="{uid}s{i}" x1="{x1}" y1="{y1}" x2="{x2}" '
            f'y2="{y2}"><stop offset="0%" stop-color="{c1}"/>'
            f'<stop offset="100%" stop-color="{c2}"/></linearGradient>'
        )
    return "".join(out)


def wallpaper_paint(wp, w, h, uid="w"):
    """
    The wallpaper itself. Scaled from the 1318x910 space the curves were drawn
    in, so the composition survives any canvas size.
    """
    sx, sy = w / 1318.0, h / 910.0
    parts = [f'<rect width="{w}" height="{h}" fill="url(#{uid}base)"/>',
             f'<g transform="scale({sx:.5f},{sy:.5f})">']

    # Fills first, softened as one group. Blurring the whole stack rather than
    # each shape keeps the boundaries between sheets from hardening.
    parts.append('<g filter="url(#silk)">')
    for i, (d, _fold, _v, _p) in enumerate(SHEETS):
        parts.append(f'<path d="{d}" fill="url(#{uid}s{i})"/>')
    parts.append("</g>")

    # Then the folds, crisp, over the top.
    for _d, fold, _v, _p in SHEETS:
        parts.append(
            f'<path d="{fold}" fill="none" stroke="#ffffff" '
            f'stroke-opacity=".55" stroke-width="1.5"/>'
        )
    parts.append("</g>")
    parts.append(
        f'<rect width="{w}" height="{h}" fill="{wp["veil"]}" '
        f'fill-opacity="{wp["veil_opacity"]}"/>'
    )
    return "".join(parts)


def glass(uid, x, y, w, h, r, wp, backdrop, shadow=True):
    """
    Frosted glass, built in layers, because one translucent rect reads as grey
    plastic and that is what the first attempt looked like.

      1. the wallpaper again, clipped to this shape and heavily blurred
      2. a tint, to give the pane a body colour
      3. a vertical sheen - bright at the top, nothing in the middle, a little
         bounce at the bottom
      4. a hairline along the very top edge, the highlight real glass catches
      5. a full rim, dimmer than the top edge
      6. a soft shadow underneath, so it sits above the desktop

    SVG has no `backdrop-filter`, and the `BackgroundImage` filter input the
    spec once defined was never implemented anywhere - redrawing the wallpaper
    and blurring it is the only way to get a true backdrop. Filters run before
    clipping, so the blur samples the whole wallpaper and the edges stay even.
    """
    out = []
    if shadow:
        out.append(
            '<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
            'fill="#000000" fill-opacity=".28" filter="url(#dockshadow)"/>'
            .format(x=x, y=y + 3, w=w, h=h, r=r)
        )
    out.append(
        '<defs><clipPath id="{u}c"><rect x="{x}" y="{y}" width="{w}" '
        'height="{h}" rx="{r}"/></clipPath>'
        '<linearGradient id="{u}sheen" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#ffffff" stop-opacity="{s1}"/>'
        '<stop offset="46%" stop-color="#ffffff" stop-opacity="0"/>'
        '<stop offset="88%" stop-color="#ffffff" stop-opacity="0"/>'
        '<stop offset="100%" stop-color="#ffffff" stop-opacity="{s2}"/>'
        "</linearGradient></defs>".format(
            u=uid, x=x, y=y, w=w, h=h, r=r,
            s1=wp["sheen_top"], s2=wp["sheen_bottom"])
    )
    out.append(
        '<g clip-path="url(#{u}c)" filter="url(#glassblur)">{b}</g>'.format(
            u=uid, b=backdrop)
    )
    out.append(
        '<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{g}" '
        'fill-opacity="{o}"/>'.format(
            x=x, y=y, w=w, h=h, r=r, g=wp["glass"], o=wp["glass_opacity"])
    )
    out.append(
        '<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" '
        'fill="url(#{u}sheen)"/>'.format(x=x, y=y, w=w, h=h, r=r, u=uid)
    )
    out.append(
        '<rect x="{x1}" y="{y1}" width="{w1}" height="{h1}" rx="{r}" '
        'fill="none" stroke="#ffffff" stroke-opacity="{o}" '
        'stroke-width="1"/>'.format(
            x1=x + 0.5, y1=y + 0.5, w1=w - 1, h1=h - 1, r=r, o=wp["rim"])
    )
    out.append(
        '<path d="M {a} {b} H {c}" stroke="#ffffff" stroke-opacity="{o}" '
        'stroke-width="1.4" stroke-linecap="round"/>'.format(
            a=x + r * 0.72, b=y + 1.2, c=x + w - r * 0.72,
            o=min(1.0, wp["rim"] + 0.34))
    )
    return "".join(out)


def wallpaper_image():
    """`assets/wallpaper.*` as a data URI, if one has been dropped in."""
    for ext, mime in (("png", "image/png"), ("jpg", "image/jpeg"),
                      ("jpeg", "image/jpeg"), ("webp", "image/webp")):
        path = os.path.join("assets", "wallpaper." + ext)
        if os.path.exists(path):
            with open(path, "rb") as handle:
                blob = base64.b64encode(handle.read()).decode("ascii")
            return "data:" + mime + ";base64," + blob, os.path.getsize(path)
    return None, 0


def desktop_menubar(theme, wp, w, day_label, clock, backdrop):
    """The macOS menu bar: full width, flush to the top, actual frosted glass."""
    h = 26
    fg = wp["menu_fg"]
    menus = ["Finder", "File", "Edit", "View", "Go", "Window", "Help"]
    parts = [
        # Extends above the canvas so the rounded rect's top corners never show.
        glass("mb", 0, -20, w, h + 20, 0, wp, backdrop, shadow=False),
        apple(14, 5, 15, fg),
    ]
    x = 40
    for i, name in enumerate(menus):
        parts.append(
            text(x, h / 2 + 4.3, name, 12.5, fg, 700 if i == 0 else 400)
        )
        x += len(name) * (7.6 if i == 0 else 7.0) + 20

    right = w - 14
    size = 12.5
    dw = size * 0.6
    stamp = day_label + "  " + clock + ":"
    sec_x = right - dw * 2
    parts.append(text(sec_x, h / 2 + 4.3, stamp, size, fg, 500, anchor="end"))
    parts.append(ticking_seconds(sec_x, h / 2 + 4.3, size, fg, "mb"))

    bx = sec_x - len(stamp) * 6.2 - 18
    parts.append(rect(bx - 24, h / 2 - 5.5, 22, 11, 3, "none", fg))
    parts.append(rect(bx - 22.5, h / 2 - 4, 16, 8, 1.5, fg))
    parts.append(rect(bx - 1, h / 2 - 2, 2, 4, 1, fg))

    wx = bx - 40
    parts.append(
        '<g transform="translate(%s,%s)" fill="none" stroke="%s" '
        'stroke-width="1.5" stroke-linecap="round">'
        '<path d="M-7.5 -6.5 A 10 10 0 0 1 7.5 -6.5"/>'
        '<path d="M-4 -3 A 5.6 5.6 0 0 1 4 -3"/>'
        '<circle cx="0" cy="0.5" r="1.3" fill="%s" stroke="none"/></g>'
        % (wx, h / 2 + 4, fg, fg)
    )
    sx2 = wx - 26
    parts.append(
        '<g transform="translate(%s,%s)" fill="none" stroke="%s" '
        'stroke-width="1.5" stroke-linecap="round">'
        '<circle cx="-1" cy="-1" r="4.6"/><path d="M2.5 2.5 L6 6"/></g>'
        % (sx2, h / 2, fg)
    )
    cx2 = sx2 - 24
    parts.append(
        '<g transform="translate(%s,%s)" fill="none" stroke="%s" '
        'stroke-width="1.5" stroke-linecap="round">'
        '<path d="M-5 -3 H5 M-5 3 H5"/>'
        '<circle cx="-1.5" cy="-3" r="1.8" fill="%s"/>'
        '<circle cx="2" cy="3" r="1.8" fill="%s"/></g>'
        % (cx2, h / 2, fg, fg, fg)
    )
    return "".join(parts)


def desktop_dock(theme, wp, w, y, backdrop):
    """The Dock: frosted glass, centred at the foot of the screen."""
    size, gap, pad = 56, 17, 17
    n = len(DOCK_APPS)
    bar_w = n * size + (n - 1) * gap + pad * 2
    bar_h = size + pad * 2
    x0 = (w - bar_w) / 2

    parts = [glass("dk", x0, y, bar_w, bar_h, 25, wp, backdrop)]
    for i, (key, label) in enumerate(DOCK_APPS):
        ix, iy = x0 + pad + i * (size + gap), y + pad
        tile = dock_tile(key, ix, iy, size, "dk%d" % i)
        href = DOCK_LINKS.get(key)
        if href:
            tile = ('<a class="lnk" href="%s" target="_blank" '
                    'rel="noopener noreferrer">%s</a>' % (esc(href), tile))
        parts.append('<g class="dockicon" filter="url(#iconshadow)">%s</g>' % tile)
        parts.append(
            '<circle cx="%s" cy="%s" r="2" fill="%s" fill-opacity=".55"/>'
            % (ix + size / 2, y + bar_h + 9, wp["menu_fg"])
        )
    return "".join(parts)


def desktop(theme, live, portrait, build_date, clock=None):
    wp = WALLPAPER["light" if theme["name"] == "light" else "dark"]
    card_w, card_h, body_fn = render.terminal_parts(theme, live, portrait)

    stamp = datetime.datetime.now()
    day_label = stamp.strftime("%a %d %b").replace(" 0", " ")
    clock = clock or stamp.strftime("%H:%M")

    menu_h = 26
    win_x = 84
    win_y = menu_h + 58
    w = card_w + win_x * 2
    # No dock in the hero. It used to be drawn here, but the README also lays
    # the same five icons out underneath as real anchors - and only those can
    # be clicked, because GitHub renders this file as an <img>. Two docks, one
    # of them dead, looked exactly like the mistake it was. The window now just
    # sits on the desktop with some wallpaper showing below it.
    h = win_y + card_h + 64

    photo, _bytes = wallpaper_image()
    if photo:
        wall_body = (
            '<image href="%s" x="0" y="0" width="%s" height="%s" '
            'preserveAspectRatio="xMidYMid slice"/>'
            '<rect width="%s" height="%s" fill="%s" fill-opacity="%s"/>'
            % (photo, w, h, w, h, wp["veil"], wp["veil_opacity"])
        )
        defs_extra = ""
    else:
        wall_body = wallpaper_paint(wp, w, h)
        defs_extra = wallpaper_defs(wp)

    # One definition, three references. A base64 wallpaper repeated three times
    # tripled the size of this file; <use> costs 30 bytes a go.
    defs_extra += '<g id="wall">%s</g>' % wall_body
    paint = '<use href="#wall"/>'

    terminal = (
        render.mac_chrome(theme, win_x, win_y, card_w, card_h,
                          theme["chrome"]["title"])
        + body_fn(win_x, win_y + theme["chrome"]["top"])
    )

    cx, cy = win_x + card_w / 2, win_y + card_h / 2
    closed = (
        '<g id="closed" display="none">'
        '<rect x="%s" y="%s" width="%s" height="%s" rx="12" fill="#000000" '
        'fill-opacity=".26" stroke="#ffffff" stroke-opacity=".4" '
        'stroke-width="1.5" stroke-dasharray="8 6"/>' % (win_x, win_y, card_w, card_h)
        + text(cx, cy - 2, "[ process completed ]", 15, "#ffffff", 500,
               "middle", family=MONO)
        + text(cx, cy + 24, "click anywhere to reopen", 13, "#ffffff", 400,
               "middle", family=MONO, opacity=0.75)
        + '<rect id="reopen" x="%s" y="%s" width="%s" height="%s" rx="12" '
          'fill="transparent"/>' % (win_x, win_y, card_w, card_h)
        + '<set attributeName="display" to="inline" begin="btnClose.click" fill="freeze"/>'
        '<set attributeName="display" to="none" begin="reopen.click" fill="freeze"/>'
        "</g>"
    )

    style = render.stylesheet(theme) + """
  .dockicon { transition: transform .18s cubic-bezier(.2,.9,.3,1.2);
              transform-origin: center bottom; }
  .dockicon:hover { transform: translateY(-9px) scale(1.16); }
"""

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="%(w)spx" height="%(h)spx"\n'
        '     viewBox="0 0 %(w)s %(h)s" font-family="%(mono)s"\n'
        '     font-size="%(fs)spx" fill="%(text)s"\n'
        '     role="img" aria-label="Ishraq Khan - macOS desktop, terminal open">\n'
        "<title>ishraq@kodezi</title>\n"
        "<style><![CDATA[%(style)s]]></style>\n"
        "<defs>%(defs)s"
        '<filter id="silk" x="-20%%" y="-20%%" width="140%%" height="140%%">'
        '<feGaussianBlur stdDeviation="26"/></filter>'
        '<filter id="dockshadow" x="-40%%" y="-80%%" width="180%%" height="300%%">'
        '<feGaussianBlur stdDeviation="15"/></filter>'
        '<filter id="iconshadow" x="-30%%" y="-30%%" width="160%%" height="170%%">'
        '<feDropShadow dx="0" dy="3" stdDeviation="3.5" flood-color="#000000" '
        'flood-opacity=".34"/></filter>'
        '<filter id="glassblur" x="-50%%" y="-50%%" width="200%%" height="200%%">'
        '<feGaussianBlur stdDeviation="22"/></filter>'
        '<filter id="drop" x="-25%%" y="-25%%" width="150%%" height="150%%">'
        '<feDropShadow dx="0" dy="22" stdDeviation="30" flood-color="#000000" '
        'flood-opacity=".42"/></filter>'
        "</defs>\n"
        "%(paint)s\n%(menu)s\n"
        '<g id="win">\n%(term)s\n'
        '<set attributeName="display" to="none" begin="btnClose.click" fill="freeze"/>\n'
        '<set attributeName="display" to="inline" begin="reopen.click" fill="freeze"/>\n'
        "</g>\n%(closed)s\n</svg>\n"
        % {
            "w": w, "h": h, "mono": MONO, "fs": themes.INFO_FONT,
            "text": theme["text"], "style": style, "defs": defs_extra,
            "paint": paint,
            "menu": desktop_menubar(theme, wp, w, day_label, clock, paint),
            "term": terminal, "closed": closed,
        }
    )


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


# The dock strip: one glass bar sliced into five images.
#
# GitHub will not let the dock inside the hero be clicked, and it will not let
# CSS position anything over an image. The only way to get a dock that is both
# clickable and looks like one bar is to cut the bar into five files and set
# them flush against each other in the Markdown, with no whitespace between the
# tags - whitespace between inline elements renders as a visible gap.
#
# Each slice carries its own pre-blurred crop of the wallpaper, so the frosted
# backdrop runs continuously across all five.

STRIP_SEG_W = 76
STRIP_H = 92
STRIP_ICON = 56
STRIP_R = 24


def _strip_backdrop_slices():
    """
    Slice a blurred crop of the wallpaper into five, one per segment.

    Blurred here in Pillow rather than with an SVG filter: the crop is tiny, a
    baked blur costs nothing at render time, and it guarantees every slice is
    blurred identically. An feGaussianBlur per file would sample each slice
    separately and band at the joins.
    """
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        return [None] * len(DOCK_APPS)

    src = None
    for ext in ("webp", "png", "jpg", "jpeg"):
        path = os.path.join("assets", "wallpaper." + ext)
        if os.path.exists(path):
            src = path
            break
    if src is None:
        return [None] * len(DOCK_APPS)

    n = len(DOCK_APPS)
    total_w = STRIP_SEG_W * n
    img = Image.open(src).convert("RGB")

    # Take the band from just under where the Terminal window sits, so the
    # glass is showing roughly the part of the wallpaper it would if the dock
    # were still drawn into the desktop.
    band_h = int(img.height * 0.11)
    top = int(img.height * 0.80)
    left = (img.width - int(img.width * 0.30)) // 2
    crop = img.crop((left, top, left + int(img.width * 0.30), top + band_h))
    crop = crop.resize((total_w * 3, STRIP_H * 3), Image.LANCZOS)
    crop = crop.filter(ImageFilter.GaussianBlur(radius=26))
    crop = crop.resize((total_w, STRIP_H), Image.LANCZOS)

    out = []
    for i in range(n):
        seg = crop.crop((i * STRIP_SEG_W, 0, (i + 1) * STRIP_SEG_W, STRIP_H))
        buf = io.BytesIO()
        seg.save(buf, "WEBP", quality=90, method=6)
        out.append("data:image/webp;base64,"
                   + base64.b64encode(buf.getvalue()).decode("ascii"))
    return out


def strip_segment(index, key, backdrop, wp):
    """One slice of the dock. Rounded only on the outer edge of the end pieces."""
    n = len(DOCK_APPS)
    w, h, r = STRIP_SEG_W, STRIP_H, STRIP_R
    first, last = index == 0, index == n - 1

    # Draw a rect that is wider than the slice and let the viewBox crop it, so
    # only the outer corners of the end pieces are ever rounded.
    x = 0 if first else -r - 2
    rw = w + (0 if first else r + 2) + (0 if last else r + 2)

    icon_x = (w - STRIP_ICON) / 2
    icon_y = (h - STRIP_ICON) / 2

    bg = ('<image href="%s" x="0" y="0" width="%s" height="%s"/>' % (backdrop, w, h)
          if backdrop else
          '<rect x="0" y="0" width="%s" height="%s" fill="#8f93a0"/>' % (w, h))

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="%(w)spx" height="%(h)spx" '
        'viewBox="0 0 %(w)s %(h)s" role="img" aria-label="%(k)s">'
        '<title>%(k)s</title>'
        '<defs><clipPath id="c"><rect x="%(x)s" y="0" width="%(rw)s" '
        'height="%(h)s" rx="%(r)s"/></clipPath>'
        '<linearGradient id="sh" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%%" stop-color="#ffffff" stop-opacity="%(s1)s"/>'
        '<stop offset="46%%" stop-color="#ffffff" stop-opacity="0"/>'
        '<stop offset="88%%" stop-color="#ffffff" stop-opacity="0"/>'
        '<stop offset="100%%" stop-color="#ffffff" stop-opacity="%(s2)s"/>'
        '</linearGradient>'
        '<filter id="is" x="-30%%" y="-30%%" width="160%%" height="170%%">'
        '<feDropShadow dx="0" dy="3" stdDeviation="3.5" flood-color="#000000" '
        'flood-opacity=".34"/></filter></defs>'
        '<g clip-path="url(#c)">'
        '%(bg)s'
        '<rect x="%(x)s" y="0" width="%(rw)s" height="%(h)s" fill="%(g)s" '
        'fill-opacity="%(go)s"/>'
        '<rect x="%(x)s" y="0" width="%(rw)s" height="%(h)s" fill="url(#sh)"/>'
        '<rect x="%(x).1f" y="0.5" width="%(rw)s" height="%(h1).1f" rx="%(r)s" '
        'fill="none" stroke="#ffffff" stroke-opacity="%(rim)s"/>'
        '<path d="M %(hx).1f 1.2 H %(hx2).1f" stroke="#ffffff" '
        'stroke-opacity="%(rim2).2f" stroke-width="1.4"/>'
        '</g>'
        '<g filter="url(#is)">%(icon)s</g>'
        "</svg>"
        % {
            "w": w, "h": h, "h1": h - 1, "r": r, "x": x, "rw": rw, "k": key,
            "bg": bg, "g": wp["glass"], "go": wp["glass_opacity"],
            "s1": wp["sheen_top"], "s2": wp["sheen_bottom"], "rim": wp["rim"],
            "rim2": min(1.0, wp["rim"] + 0.34),
            "hx": (r * 0.72) if first else 0,
            "hx2": (w - r * 0.72) if last else w,
            "icon": dock_tile(key, icon_x, icon_y, STRIP_ICON, "s%d" % index),
        }
    )


def icon_file(key, size=128):
    """One dock icon on its own, transparent, for use outside the strip."""
    pad = size * 0.08
    inner = size - pad * 2
    tile = dock_tile(key, pad, pad, inner, "ic" + key)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="%(s)spx" '
        'height="%(s)spx" viewBox="0 0 %(s)s %(s)s" role="img" '
        'aria-label="%(k)s"><title>%(k)s</title>'
        '<defs><filter id="sh" x="-30%%" y="-30%%" width="160%%" '
        'height="170%%"><feDropShadow dx="0" dy="%(dy).1f" '
        'stdDeviation="%(sd).1f" flood-color="#000000" '
        'flood-opacity=".3"/></filter></defs>'
        '<g filter="url(#sh)">%(tile)s</g></svg>'
        % {"s": size, "k": key, "dy": size * 0.03, "sd": size * 0.035,
           "tile": tile}
    )


def write_all(live, portrait, build_date):
    """Render every desktop element for the mac themes. Returns file paths."""
    written = []
    wp = WALLPAPER["light"]
    slices = _strip_backdrop_slices()
    for i, (key, _label) in enumerate(DOCK_APPS):
        for name, svg in (
            ("icon_%s.svg" % key, icon_file(key)),
            ("dock%d_%s.svg" % (i, key), strip_segment(i, key, slices[i], wp)),
        ):
            with open(name, "w", encoding="utf-8", newline=chr(10)) as handle:
                handle.write(svg)
            written.append(name)

    for theme in (themes.DARK, themes.LIGHT):
        suffix = theme["name"]
        pieces = {
            f"desktop_{suffix}.svg": desktop(theme, live, portrait, build_date),
            f"about_{suffix}.svg": about(theme, live, portrait),
            f"kodezi_{suffix}.svg": kodezi(theme, live),
            f"notes_{suffix}.svg": notes(theme, build_date),
        }
        for name, svg in pieces.items():
            with open(name, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(svg)
            written.append(name)
    return written
