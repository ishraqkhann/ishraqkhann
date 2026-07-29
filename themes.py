"""
Palettes and window chrome for each card variant.

Three themes ship by default:

    dark   - GitHub dark. The default.
    light  - GitHub light. Swapped in automatically by <picture> in the README.
    xp     - Windows XP Luna. Full window chrome, taskbar, Start button, and a
             literal XP bar. Because "XP mode" deserved both readings.

Adding a fourth theme means adding one dict here. `render.py` does the rest.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Geometry shared by every theme
#
# The monospace cell is ~9.6px wide at font-size 16. That number is not a
# guess: Consolas has a 0.55em advance, and the @font-face in render.py
# applies size-adjust:109% so that 16 * 0.55 * 1.09 = 9.59px. When Consolas is
# missing and the browser falls back to DejaVu Sans Mono / Liberation Mono
# (0.602em advance) the cell is 9.63px. Those two numbers agreeing to within
# half a pixel is the whole reason the size-adjust is there.
# --------------------------------------------------------------------------

CARD_W = 1150

# The portrait is 76 columns wide, so it gets a smaller font than the text.
# At 11px a cell is 11 * 0.599 = 6.59px wide; a 13px line-height keeps the cell
# at very close to 1:2, which is the ratio ASCII art is drawn for. 76 columns
# therefore occupy 501px and 41 rows occupy 533px.
ASCII_X = 24
ASCII_Y0 = 40
ASCII_DY = 13
ASCII_FONT = 11

INFO_X = 547
INFO_Y0 = 40
INFO_DY = 20
INFO_FONT = 16


# macOS window chrome. `pad` is the margin left around the card so the drop
# shadow has somewhere to fall.
_MAC = {
    "kind": "mac",
    "top": 36,
    "bottom": 0,
    "radius": 12,
    "pad": 20,
    "title": "ishraq@kodezi — -zsh — 136×29",
}

MAC_DARK = dict(
    _MAC,
    bar_top="#3d3d40",
    bar_bottom="#2b2b2e",
    divider="#1c1c1e",
    title_fill="#a1a1a6",
    highlight="#ffffff",
    highlight_opacity=0.09,
    shadow_opacity=0.55,
)

MAC_LIGHT = dict(
    _MAC,
    bar_top="#f7f7f7",
    bar_bottom="#e3e3e3",
    divider="#c6c6c6",
    title_fill="#4b4b4f",
    highlight="#ffffff",
    highlight_opacity=0.85,
    shadow_opacity=0.22,
)

# macOS system-UI surfaces, used by the non-terminal windows in ui.py.
# These are Apple's own greys rather than GitHub's, because these windows are
# pretending to be AppKit, not a terminal.
UI_DARK = {
    "bg": "#1e1e20",
    "panel": "#2c2c2e",
    "fg": "#f5f5f7",
    "dim": "#98989d",
    "sep": "#38383a",
    "accent": "#0a84ff",
    "btn": "#3a3a3c",
    "btn_fg": "#f5f5f7",
}

UI_LIGHT = {
    "bg": "#f2f2f5",
    "panel": "#ffffff",
    "fg": "#1d1d1f",
    "dim": "#6e6e73",
    "sep": "#d8d8de",
    "accent": "#0071e3",
    "btn": "#ffffff",
    "btn_fg": "#1d1d1f",
}

# The three traffic lights, in order. (fill, rim)
TRAFFIC = (
    ("#ff5f57", "#e0443e"),
    ("#febc2e", "#d79b26"),
    ("#28c840", "#1dad2b"),
)


DARK = {
    "name": "dark",
    "file": "dark_mode.svg",
    "bg": "#161b22",
    "border": "#30363d",
    "text": "#c9d1d9",
    "ascii": "#c9d1d9",
    "ascii_glow": "#58a6ff",
    "key": "#ffa657",
    "value": "#a5d6ff",
    "add": "#3fb950",
    "delete": "#f85149",
    "dim": "#616e7f",
    "rule": "#6e7681",
    "cursor": "#58a6ff",
    "bar_fill": "#3fb950",
    "bar_empty": "#55606d",
    "sweep_opacity": 0.55,
    "tier0": 0.20,
    "tier1": 0.46,
    "ui": UI_DARK,
    "chrome": MAC_DARK,
}


LIGHT = {
    "name": "light",
    "file": "light_mode.svg",
    "bg": "#ffffff",
    "border": "#d0d7de",
    "text": "#24292f",
    "ascii": "#24292f",
    "ascii_glow": "#0969da",
    "key": "#953800",
    "value": "#0a3069",
    "add": "#1a7f37",
    "delete": "#cf222e",
    "dim": "#8c959f",
    "rule": "#afb8c1",
    "cursor": "#0969da",
    "bar_fill": "#1a7f37",
    "bar_empty": "#d0d7de",
    "sweep_opacity": 0.28,
    "tier0": 0.22,
    "tier1": 0.50,
    "ui": UI_LIGHT,
    "chrome": MAC_LIGHT,
}


# The XP theme keeps a black console interior - that is what a Command Prompt
# window actually looked like - and wraps it in Luna blue chrome.
XP = {
    "name": "xp",
    "file": "xp_mode.svg",
    "bg": "#000000",
    "border": "#0058ee",
    "text": "#c0c0c0",
    "ascii": "#c0c0c0",
    "ascii_glow": "#ffffff",
    "key": "#ffff55",
    "value": "#55ffff",
    "add": "#55ff55",
    "delete": "#ff5555",
    "dim": "#808080",
    "rule": "#808080",
    "cursor": "#c0c0c0",
    "bar_fill": "#3ea23e",
    "bar_empty": "#1a1a1a",
    "sweep_opacity": 0.45,
    "tier0": 0.22,
    "tier1": 0.48,
    "ui": UI_DARK,
    "chrome": {
        "kind": "xp",
        "top": 34,      # title bar
        "bottom": 38,   # taskbar
        "radius": 8,
        "pad": 20,
        "shadow_opacity": 0.45,
        "frame": 4,
        "title": "ishraq@kodezi - Command Prompt",
        "titlebar": ("#0058ee", "#3f8cf3", "#0058ee"),
        "taskbar": ("#245edc", "#3f8cf3"),
        "start": ("#3c8b37", "#6ac25f"),
    },
}


THEMES = [DARK, LIGHT, XP]
