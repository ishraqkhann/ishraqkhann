# How the card works

A GitHub Action runs `today.py` every night. It pulls your stats from the GitHub
GraphQL API, regenerates every window of the desktop from one template, and
commits whatever changed. The README assembles them.

Forked from [Andrew6rant/Andrew6rant](https://github.com/Andrew6rant/Andrew6rant),
then rewritten so the SVGs are generated rather than hand-maintained.

```
config.py                 you edit this. identity, rows, grid size
themes.py                 palettes, window chrome, macOS UI surfaces
render.py                 the typesetter + the Terminal window
ui.py                     the desktop, menu bar, Dock, wallpaper, app windows
today.py                  the GitHub API layer and entry point
assets/portrait.txt       your ASCII portrait, 76 x 41
tools/photo_to_ascii.py   photo -> assets/portrait.txt
preview.html              open all of it locally, with hover and clicks live
cache/<sha256>.txt        per-repo lines-of-code cache
cache/stats.json          last successful fetch, used as a fallback
```

The one that matters is `desktop_dark.svg` / `desktop_light.svg`: a whole macOS
desktop in a single image — wallpaper, menu bar, the Terminal window sitting
open on it, and the Dock. That is the README's hero, and currently the only
window it shows.

`about_*.svg`, `kodezi_*.svg` and `notes_*.svg` are still generated but are not
referenced by the README right now. Each is a standalone window with its own
working close button. To bring one back, wrap it in a `<details>` block —
`<details>` is the only interactivity GitHub permits, and it survives the
sanitiser.

**XP mode has been retired.** The theme dict is still in `themes.py`; it is just
no longer in `THEMES`, so nothing renders it. Put `XP` back in that list to
revive it.

---

## 1. First-time setup

**The repository has to be named after your account.** A profile README only
renders if the repo is `ishraqkhann/ishraqkhann`. Any other name and it is just
a normal repo.

**Create a fine-grained personal access token** at
_Settings → Developer settings → Personal access tokens → Fine-grained_, with
access to **all repositories**:

| Scope | Permission |
| --- | --- |
| Account | `Followers: read`, `Starring: read` |
| Repository | `Commit statuses: read`, `Contents: read`, `Metadata: read` |

**Add two repository secrets** under _Settings → Secrets and variables → Actions_:

| Secret | Value |
| --- | --- |
| `ACCESS_TOKEN` | the token you just made |
| `USER_NAME` | `ishraqkhann` |

Then run the workflow once by hand from the Actions tab. The first run is slow —
it walks every commit in every repository you have touched to count lines. Later
runs only re-walk repositories whose commit count moved, so they take seconds.

---

## 2. Your ASCII portrait

**76 characters wide × 41 rows tall. 3,116 characters.**

That is the size of the portrait currently in `assets/portrait.txt`, and the
layout is built around it. Every line is padded to exactly 76 — the renderer
pads and crops for you, and warns when it has to. Any character is fine; `&`,
`<` and `>` are escaped on the way into the SVG.

The geometry: a portrait cell is `11px × 0.599 = 6.59px` wide and `13px` tall
(near enough 1:2, which is what ASCII art is drawn for), so the block occupies
501 × 533px and stops 22px short of the info column.

From a photo:

```bash
pip install pillow
python tools/photo_to_ascii.py me.jpg --sharpen --gravity top
```

Then look at it and iterate — `--contrast 1.6`, `--ramp blocks`, `--gravity center`.
`--help` lists the rest.

Two things matter more than any flag: crop tight to head and shoulders before you
start, and use a photo with a plain background and strong side lighting. 76 × 41 is
about 3,100 characters of information. Busy backgrounds turn to mush.

Different size? Change `ASCII_COLS` / `ASCII_ROWS` in `config.py`, then adjust
`ASCII_FONT` / `ASCII_DY` / `INFO_X` / `CARD_W` in `themes.py` so it still fits.
`python today.py --check` does the arithmetic and tells you what overflows.

### Density tiers

ASCII art encodes brightness as glyph density, but SVG draws every glyph in the
same colour — so a `+++++` background comes out exactly as loud as an `@@@@@`
face and the portrait flattens into noise. The renderer buckets characters into
three density tiers and drops the opacity of the quiet ones, which puts the
tonal range back. `DENSITY` in `render.py`, `tier0`/`tier1` in `themes.py`.

---

## 3. Editing the content

Everything lives in `SECTIONS` in `config.py`:

```python
row("Host", "Kodezi - Founder & CEO")     # . Host: ...... Kodezi - Founder & CEO
row("Uptime", LIVE("age"))                # filled in at build time
row("Languages.Real", "English, Bengali") # dotted keys highlight per segment
rule("Contact")                           # ─ Contact ──────────────────
blank()                                   # spacer
```

Lines are 60 characters wide (`INFO_COLS`). Dot leaders are computed so every
value ends flush on the right — that alignment is what makes it look like real
`neofetch` output. Go over 60 and `--check` complains.

`LIVE(...)` fields: `age`, `repos`, `contributed`, `stars`, `commits`,
`followers`, `loc_net`, `loc_added`, `loc_deleted`, `level`, `xp_current`,
`xp_needed`.

**Set your date of birth.** `BIRTHDAY` in `config.py` is a placeholder and the
Uptime row is wrong until you fix it.

---

## 4. Working on it locally

```bash
pip install -r cache/requirements.txt
python today.py --demo      # render with placeholder numbers, no token needed
python today.py --check     # validate the layout, write nothing
python today.py --offline   # re-render from the last successful fetch
```

`preview.html` shows the whole desktop, with `<object>` copies where hover,
links and the close button are actually live:

```bash
python -m http.server 4173
```

then open <http://localhost:4173/preview.html>.

---

## 5. About the animation

The card animates two ways, and it is worth knowing which is which.

**Ambient — runs everywhere, including on GitHub.** A light sweep passes down the
portrait every nine seconds, the portrait breathes, rows fade in on load, and the
prompt cursor blinks. These are declarative CSS keyframes and SMIL, which browsers
do run inside an `<img>`.

**Hover — does not run on GitHub.** Hovering the portrait brings it into focus,
stops the breathing, and pushes a red/cyan chromatic split out from the glyphs.

Here is the honest version, measured rather than assumed. An SVG referenced from
an `<img>` is processed in what the [SVG Integration spec](https://www.w3.org/TR/svg-integration/#processing-modes)
calls *secure animated mode*: declarative animation runs, but interactivity is
switched off entirely — "any user input events that would be targetted at the
document or any elements within the document must have no effect." Hit-testing
stops at the `<img>` and never descends into the image, so `:hover` never
matches and SMIL `begin="mouseover"` has no event to fire on. Verified in
Chromium: the identical SVG changed colour on hover through `<object>` and did
not budge through `<img>`.

There is no way around it in a README either. Probing GitHub's own Markdown
renderer: `<object>`, `<embed>` and inline `<svg>` are **stripped**; `<style>`
and `<iframe>` are **escaped into literal text**; `onmouseover`, `style` and
`class` attributes are **removed**. `<picture>`, `<source>`, `<details>` and
`<summary>` survive. Anyone showing you a "hover effect" in a README is showing
you a GIF.

So the hover rules ship anyway and cost nothing where they are inert. They light
up wherever the SVG is a real document — opened directly, embedded with
`<object>` on ishraqkhan.com, or in `preview.html`.

The one genuinely interactive thing GitHub *does* allow is `<details>` — which is
exactly what the README is built on. Every window up there opens and closes for
real, because each one is a `<details>` block.

**The Dock is not in the hero image.** It used to be, and that was a mistake: a
dock drawn into the SVG cannot be clicked on GitHub, so having it there *and*
having the clickable icon row underneath rendered the same five icons twice, one
set of them dead.

The dock now lives outside the hero as five separate files — `dock0_globe.svg`
through `dock4_x.svg`. Each carries its own slice of the glass bar plus a
matching blurred crop of the wallpaper, so set flush against each other they
join into a single continuous dock, and each one is a real anchor.

**The tags must have zero whitespace between them.** This was measured, not
assumed: three variants rendered side by side, and a newline between the tags
produced a visible gap through the bar every time, because whitespace between
inline elements renders as a space. Flush tags join perfectly. If you ever
reformat `README.md` and something "prettifies" that line onto several lines,
the dock will break into five tiles — that is the cause.

The blur is baked in Pillow rather than applied with an `feGaussianBlur` per
file: a filter would sample each slice in isolation and band at the joins.
`strip_segment()` and `_strip_backdrop_slices()` in `ui.py`.

`icon_*.svg` are the same icons standalone on transparent, if you want them
without the bar. `desktop_dock()` still exists too, if you ever want it drawn
back into the hero.

Dropping it also took the hero from 244 KB to 103 KB, because the five icons are
no longer base64-inlined into it on top of existing as their own files.

### The close button

The red traffic light is wired up for real. Clicking it swaps the window for a
dashed placeholder reading `[ process completed ]` — which is what Terminal.app
actually prints when a shell exits — and clicking that puts the window back,
boot reveal and all. The XP theme's red **✕** does the same thing.

It is driven by four SMIL `<set>` elements keyed on `btnClose.click` and
`reopen.click`. **No JavaScript**, deliberately: these files are served under a
`default-src 'none'` CSP that would block inline script anyway, and SMIL timing
is not script so it survives.

Same boundary as everything else in this section — it works wherever the SVG is
a live document, and does nothing inside GitHub's `<img>`, where click
traversal is switched off along with hover.

> If you go looking, note that Chrome does **not** report SMIL-animated CSS
> properties through `getComputedStyle` — it will tell you `display` is still
> `inline` when the element is demonstrably gone from the render. Verify by
> screenshot, not by reading computed style. That quirk cost me a detour.

For GitHub, the closest honest equivalent is `<details>`, and the README uses
it: the card sits inside `<details open>` so anyone can collapse it. If you would
rather the card always show — reasonable, it is the hero image — delete the
`<details>`/`<summary>`/`</details>` lines around the `<picture>` block and
nothing else changes.

### Links inside the card

The Email / Web / X / LinkedIn / GitHub rows are real SVG `<a>` elements with
proper `href`s, and they hover-highlight and click through — **but only where the
SVG is a live document.** Same wall as `:hover`: link traversal is one of the
behaviours secure animated mode disables, so inside GitHub's `<img>` they are
decorative text.

Two things do work on GitHub, and between them they cover it:

- **The whole card is a link.** `README.md` wraps the `<picture>` in an
  `<a href="https://ishraqkhan.com">`, so clicking anywhere on it opens the site.
  (GitHub auto-wraps a bare `<img>` in a link to the Camo URL — supplying your own
  `<a>` overrides that.)
- **The "Find me" table under the card** is ordinary Markdown, so every row there
  is genuinely clickable everywhere.

Change a link in one place — `config.py` — and it flows into the SVG. The Markdown
table in `README.md` is maintained by hand; keep the two in step.

Two more things that fell out of the same testing and are worth knowing:

- **`raw.githubusercontent.com` is not proxied through Camo.** Third-party hosts
  are; raw is passed through verbatim. Either way the SVG is served under
  `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'`, which
  is exactly why an inline `<style>` block works and why the card must not
  reference an external font or image. The `@font-face` here uses `src: local()`
  only — it loads nothing.
- **`prefers-color-scheme` follows the OS, not your GitHub theme setting.** If
  someone runs a light OS and dark GitHub, they get the light card. Nothing to be
  done about it; just don't be surprised.

---

## 6. Themes

`dark_mode.svg` and `light_mode.svg` are macOS windows — traffic lights, graphite
title bar, drop shadow. The README swaps between them with `<picture>` and
`prefers-color-scheme`.

`xp_mode.svg` is Windows XP Luna: title bar gradient, real window buttons, a
taskbar with a Start button and a clock showing the build date, wrapped around a
black console interior.

A theme is one dict in `themes.py`. Add one there, and `render.write_all` picks
it up.

---

## 7. When it breaks

`today.py` fetches everything before it writes anything, so a failure mid-run
cannot leave a half-updated card on your profile. If the API fails outright it
falls back to `cache/stats.json` and re-renders yesterday's numbers rather than
publishing a broken card.

Delete `cache/<sha256>.txt` to force a full lines-of-code rebuild. It is slow and
burns API budget, so only do it if the numbers look wrong.

**On 502s.** GitHub answers `502 Bad Gateway` when a `history(first: N)` page is
too expensive for it to build. It is a server-side timeout, not a rate limit, so
retrying the identical query never succeeds — the first full run against this
account died exactly that way, after burning five backoff retries per attempt.
`walk_repo` now quarters its page size and retries the same cursor, down to a
floor of 5. Repositories with very large commits — lockfiles, vendored trees,
generated assets — only come back at all this way.

**On long first runs.** A full rebuild here walks ~43,000 commits across 67
repositories, which is several hundred paginated calls and many minutes. The
cache is flushed after *every* repository, so if the job is killed part-way it
resumes from where it stopped instead of starting over. Run it with `python -u`
if you want to watch — Python buffers stdout when it is not attached to a
terminal, so a killed run otherwise reports nothing at all.

---

## 8. Dock icons and the clock

### Dropping in your own icons

Put square PNGs here and they replace the drawn fallbacks on the next build:

```
assets/icons/globe.png       Website
assets/icons/kodezi.png      Kodezi
assets/icons/email.png       Email
assets/icons/linkedin.png    LinkedIn
assets/icons/x.png           X
```

Those five are **already in place**. `tools/` has no importer for them — they
were brought in by hand: trimmed on an alpha threshold of 40 (not on any
non-zero alpha, because several carry a soft drop shadow that `getbbox()` counts
as content, which left them visibly smaller than the rest), padded square, and
resized to 128 px. They render at 56, so 128 is still north of 2× retina.

To replace one, drop a square PNG at the same path and rebuild. Don't pre-round
the corners — the renderer masks to the macOS radius (22.4% of the side).
Anything missing falls back to a drawn vector, so you can swap them one at a
time.

They are embedded as base64 `data:` URIs, not linked. That is not a preference:
these files are served under `default-src 'none'; img-src data:`, so an `<image
href="https://...">` is blocked outright while a `data:` URI is allowed. It does
mean each icon inflates every SVG that contains it — keep them small.

Geometry, if you want to design against it:

| | bar | icon | gap | padding |
| --- | --- | --- | --- | --- |
| in `desktop_*.svg` | 302 × 70, r19 | 46 × 46 | 12 | 12 |
| standalone `dock_*.svg` | 354 × 82, r22 | 54 × 54 | 14 | 14 |

Adding or removing an app changes the bar width — it is computed from the length
of `DOCK_APPS` in `ui.py`, so nothing needs re-measuring by hand.

### The clock

The seconds tick. The hours and minutes do not.

That split is forced. There is no clock available to an SVG in a README: script
is blocked, and although SMIL defines `begin="wallclock(...)"` no browser has
ever implemented it, so nothing inside the file can learn what time it is. All a
build can do is bake in the time it ran.

So the seconds are a slot machine — the ten glyphs stacked, clipped to one cell,
stepped by a discrete `animateTransform` on a 10s and a 60s loop. That runs
inside an `<img>`, so it genuinely counts up while someone is looking at your
profile. Nobody can tell that second `07` is not the real second `07`.

Hours and minutes get no such cover. A menu bar reading `09:14` at four in the
afternoon looks broken, so those stay at the last build and the nightly Action
keeps the date honest. If you want the time fresher, raise the cron in
`.github/workflows/build.yaml` — but note GitHub throttles scheduled workflows
and starts skipping them on quiet repositories, so every 30 minutes is about as
tight as is worth trying.

---

## 9. Wallpaper and glass

### The wallpaper is drawn, not photographed

Five overlapping bezier "sheets", each with its own gradient, blurred as a group
and then overlaid with crisp fold lines. `SHEETS` and `WALLPAPER` in `ui.py`.

That is a deliberate choice, not a shortcut. A wallpaper cannot be *linked* here
— `default-src 'none'` blocks it — so a raster has to be base64-inlined into
every desktop SVG. A full-bleed photo at this size is 1–2 MB, which becomes
~2.5 MB of base64, twice for the two themes, in a file GitHub re-fetches on
every view. The drawn version is about four kilobytes and stays sharp at any
scale, which matters because GitHub downsamples the hero to roughly 880px.

**A photo is in use now**: `assets/wallpaper.webp`, the macOS Tahoe *Golden
Gate* wallpaper. It arrived as a 22 MB 6016 × 4147 PNG and is stored at
**28.8 KB** — cropped to exactly the 1318 × 870 canvas and saved as WebP, which
handles smooth gradients far better than PNG (the same crop as JPEG was 61 KB).
Replace it by dropping any `assets/wallpaper.{png,jpg,webp}` in; delete it and
the drawn version comes back.

The wallpaper is painted three times — once as the desktop and once behind each
frosted panel. Inlining the base64 three times tripled the file, so it is
defined once in `<defs>` and referenced with `<use>`. That alone took the
desktop SVG from 305 KB to 228 KB.

### The glass is real

The Dock and menu bar are genuinely frosted: a second copy of the wallpaper,
clipped to the panel, blurred, with a tint and a bright rim over it.

SVG has no `backdrop-filter`, and the `BackgroundImage` filter input the spec
once defined was never implemented by any browser — so the usual trick is a flat
translucent fill, which reads as grey plastic. Redrawing the wallpaper behind
the panel and blurring *that* is the only way to actually get it. Filters run
before clipping, so the blur samples the whole wallpaper and the panel edges do
not darken.

`glass()` in `ui.py` — pass it any rect and it frosts it.
