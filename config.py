"""
The only file you need to edit.

Everything about the card - who you are, what the rows say, how wide the
columns are - lives here. `render.py` turns this into SVG, `today.py` fills in
the live numbers from the GitHub API.

Row helpers
-----------
    row("OS", "macOS, Ubuntu")        -> . OS: ......... macOS, Ubuntu
    row("Languages.Real", "English")  -> dotted keys are highlighted per segment
    rule("Contact")                   -> - Contact ----------------------
    blank()                           -> a spacer line
    LIVE("commits")                   -> replaced by a number fetched at build time

Anything wrapped in LIVE(...) is resolved by today.py. The available keys are
listed in LIVE_FIELDS at the bottom of this file.
"""

from __future__ import annotations

import datetime

# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------

# Note: github.com/ishraqkhan is a different person (Purdue, class of 2019).
# The account with "Founder & CEO @Kodezi" in the bio is ishraqkhann, which
# also matches your X and LinkedIn handles.
GITHUB_USERNAME = "ishraqkhann"

# Drives the "Uptime" row, which ticks up by one day on every scheduled build.
BIRTHDAY = datetime.datetime(2003, 10, 29)

# The prompt shown at the top of the card: `user@host`
PROMPT_USER = "ishraq"
PROMPT_HOST = "kodezi"

# --------------------------------------------------------------------------
# Layout
#
# The card is a monospace grid. These are the two numbers that matter:
#
#   ASCII_COLS x ASCII_ROWS  - the size of your ASCII portrait, in characters
#   INFO_COLS                - how many characters wide each info line may be
#
# If you change ASCII_COLS you must also move INFO_X in render.py. The
# validator in `render.py` will tell you if anything overflows.
# --------------------------------------------------------------------------

ASCII_COLS = 76
ASCII_ROWS = 41
INFO_COLS = 60

ASCII_ART_FILE = "assets/portrait.txt"

# --------------------------------------------------------------------------
# The card body
# --------------------------------------------------------------------------


class LIVE:
    """A value fetched from the GitHub API at build time."""

    __slots__ = ("field", "width")

    def __init__(self, field: str, width: int = 0):
        self.field = field
        self.width = width  # reserved char width, keeps dots from jittering


class Row:
    __slots__ = ("key", "value", "href")

    def __init__(self, key, value, href=None):
        self.key = key
        self.value = value
        # Rendered as an SVG <a>. Live wherever the SVG is a real document;
        # inert inside GitHub's <img>. See SETUP.md section 5.
        self.href = href


class Rule:
    __slots__ = ("title",)

    def __init__(self, title):
        self.title = title


class Blank:
    __slots__ = ()


class Raw:
    """A pre-composed line built from explicit spans. See render.py:compose."""

    __slots__ = ("spans",)

    def __init__(self, *spans):
        self.spans = spans


class XPBar:
    """The level / experience bar. Fun, and a nod to the XP theme."""

    __slots__ = ()


def row(key, value, href=None):
    return Row(key, value, href)


def rule(title):
    return Rule(title)


def blank():
    return Blank()


# Total commits per level. 100 keeps the number climbing at a satisfying pace.
XP_PER_LEVEL = 100
XP_BAR_CELLS = 20


SECTIONS = [
    row("OS", "macOS, Ubuntu, Windows 11"),
    row("Uptime", LIVE("age")),
    row("Host", "Kodezi - Founder & CEO"),
    row("Kernel", "Autonomous software systems"),
    row("Location", "San Francisco, California"),
    blank(),
    row("Languages.Programming", "TypeScript, Python, Rust"),
    row("Languages.Markup", "HTML, CSS, JSON, YAML"),
    row("Languages.Real", "English, Bengali"),
    blank(),
    row("Origin", "Dhaka, Bangladesh -> U.S., 2011"),
    row("Path", "Self-taught. Skipped college."),
    row("Writing", "systems, culture, psychology"),
    rule("Kodezi"),
    row("Product", "the AI CTO for your codebase", "https://kodezi.com"),
    row("Does", "remembers, heals, evolves, governs"),
    row("Users", "4,000,000+ developers"),
    rule("Contact"),
    row("Email", "ishraq@kodezi.com", "mailto:ishraq@kodezi.com"),
    row("Web", "ishraqkhan.com", "https://ishraqkhan.com"),
    row("X", "@ishraqkhann", "https://x.com/ishraqkhann"),
    row("LinkedIn", "ishraqkhann", "https://www.linkedin.com/in/ishraqkhann/"),
    row("GitHub", "@ishraqkhann", "https://github.com/ishraqkhann"),
    rule("GitHub Stats"),
    Raw(
        ("dim", ". "),
        ("key", "Repos"),
        ("plain", ":"),
        ("dots", 2),
        ("live", "repos"),
        ("plain", " {"),
        ("key", "Contributed"),
        ("plain", ": "),
        ("live", "contributed"),
        ("plain", "} | "),
        ("key", "Stars"),
        ("plain", ":"),
        ("dots", 3),
        ("live", "stars"),
    ),
    Raw(
        ("dim", ". "),
        ("key", "Commits"),
        ("plain", ":"),
        ("dots", 3),
        ("live", "commits"),
        ("plain", " | "),
        ("key", "Followers"),
        ("plain", ":"),
        ("dots", 2),
        ("live", "followers"),
    ),
    Raw(
        ("dim", ". "),
        ("key", "Lines of Code"),
        ("plain", ":"),
        ("dots", 1),
        ("live", "loc_net"),
        ("plain", " ( "),
        ("add", "loc_added"),
        ("plain", "++, "),
        ("del", "loc_deleted"),
        ("plain", "-- )"),
    ),
    XPBar(),
]


# --------------------------------------------------------------------------
# Links (used by the README, not the card)
# --------------------------------------------------------------------------

LINKS = {
    "website": "https://ishraqkhan.com",
    "kodezi": "https://kodezi.com",
    "email": "ishraq@kodezi.com",
    "x": "https://x.com/ishraqkhann",
    "linkedin": "https://www.linkedin.com/in/ishraqkhann/",
    "github": f"https://github.com/{GITHUB_USERNAME}",
}


# --------------------------------------------------------------------------
# Which repositories count toward the stats
# --------------------------------------------------------------------------

OWNER_AFFILIATIONS = ["OWNER", "COLLABORATOR", "ORGANIZATION_MEMBER"]
OWNED_ONLY = ["OWNER"]

# Repositories left out of the commit and lines-of-code totals.
#
# Two kinds of repository wreck these numbers. Auto-commit repos contribute
# tens of thousands of machine-made commits; vendored or generated dumps
# contribute millions of lines somebody else wrote. Neither says anything about
# you, and both invite the wrong kind of scrutiny on a profile.
#
# Full "owner/name", exactly as GitHub spells it. Excluded repos are neither
# walked nor counted, so adding one here also makes the nightly build faster.
EXCLUDE_REPOS = {
    # "ishraqkhann/auto-p2",     # 16,797 commits - 93% of the total
    # "ishraqkhann/AutoCommit",  # 901 commits
    # "Kodezi/Chronos",          # +5,282,295 lines in 5 commits
}

# Number of comment lines at the top of the LOC cache file.
CACHE_COMMENT_SIZE = 7


LIVE_FIELDS = (
    "age",
    "repos",
    "contributed",
    "stars",
    "commits",
    "followers",
    "loc_net",
    "loc_added",
    "loc_deleted",
    "level",
    "xp_current",
    "xp_needed",
)
