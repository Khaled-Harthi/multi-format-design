---
name: multi-format-design
description: >-
  Recreate ONE graphic design across many platform sizes by intelligently
  re-arranging its components per aspect ratio — not naive scaling or cropping.
  Use whenever the user wants to adapt, resize, reformat, repurpose, or "make
  versions / different sizes" of a design, poster, flyer, ad, or social graphic
  for multiple destinations: Instagram posts & stories, Snapchat, TikTok,
  Facebook, LinkedIn, X/Twitter, YouTube thumbnails, Pinterest, web banners,
  bus-shelter / street signage, roll-up standees, or outdoor billboards. Accepts
  PSD, AI, PDF, SVG, PNG/JPG, and Canva exports; works for any brand and for LTR or
  RTL / Arabic designs.
  Trigger this even when the user just says "I need this in different sizes",
  "resize my poster for social", "make a story version", "adapt this for a
  billboard", or drops a design file with a list of platforms — prefer it over a
  plain image resize because it recomposes the layout and trims the copy for each
  format instead of stretching one flat picture.
---

# Multi-format design

Recreate ONE design across many platform sizes by **re-arranging its real components
per aspect ratio** — never a flat scale or crop. A wide poster scaled into a 9:16 story
letterboxes or slices the subject, and type set for a wide measure turns unreadable. This
skill treats a design as **components** (logo · eyebrow · headline · subhead · body · hero ·
CTA · contact · decoration) and re-flows them through a layout chosen by the target's aspect
ratio, shedding copy that small / fast-glance formats can't carry.

**Preserve, don't regenerate.** The default path lifts the source's *actual* pixels — it
**probes** the file, **replays** the real background, photo, button, blobs, logo and text
onto transparent layers, and **re-arranges** those per size with headless Chromium at exact
platform pixels. Never re-typeset a title in a lookalike font or recreate art in CSS — that
is inventing, and it never matches. Only a truly flat photo (no vectors, no live text) falls
back to a token rebuild. The engine is **brand-agnostic** (nothing baked in) and handles LTR
and **RTL / Arabic** alike — only the source differs.

## When to use
Any "same design, many sizes / platforms" request — social sets, ad campaigns, print +
digital out-of-home. A literal pixel resize of a photo with no layout (e.g. "make this JPG
800px wide") is a plain resize, not this skill.

## Setup (once — BOTH paths need this)
```
python scripts/setup.py <project>
```
`<project>` is any new folder that will hold the assets + outputs. This builds
`<project>/.venv` with the toolchain (PyMuPDF, Playwright + Chromium, Pillow, numpy, rembg,
psd-tools) and fonts, then **prints the venv python path**. Use *that* python for every
command below — shown as `PY` — and pass the same `<project>` to each script.

## Workflow — PROBE → REPLAY → RE-ARRANGE (the default)
```
PY scripts/decompose.py <design-file> <project>   # PROBE + REPLAY -> assets/layers/* + layers.json
PY scripts/recompose.py <project>                 # RE-ARRANGE the real components per size
PY scripts/recompose.py <project> --only billboard_48sheet,instagram_story
```
Works for a normal **structured** PDF/PSD *and* a **vector-flattened** one (text and art
outlined, no live layers). `decompose` takes a layered or vector source (PDF / AI / PSD); a
genuinely flat SVG/PNG/JPG routes to the fallback below. It probes the real geometry (rasters
by xref + soft masks, every vector drawing with its fill / bbox / area, live-text runs, the
true background colour, reading direction), lifts each photo by its xref re-clipped with its
own mask / rounded clip and ring, bakes a CTA pill's label onto the pill, and keys live text
to its own ink — or, when flattened, replays each element's own vector paths so the title
comes away in its **real** font. It emits a kit tagged **hero / headline / subhead / body /
footer / note / qr / logo / decoration / button** with the background colour and direction in
`layers.json`. `recompose` chooses a layout from the target aspect: a full-bleed-background ad
keeps its background with the text column in the empty space; a poster / flyer becomes
hero-to-one-side (wide) or hero-in-its-own-band (tall), RTL-aware. An **opaque / framed photo
gets its own zone; only a transparent cut-out shares space with type.**

Review `layers.json` + the layer PNGs and nudge anything that lands awkwardly with
`--overrides overrides.json` (a JSON object keyed per format key). Knobs:
`heroAnchorY` (top|center|bottom|overlay) · `heroSide` (left|right) · `heroPct` ·
`heroFit` (cover|contain) · `marginPct` · `gapPct` · `widthPct` · `cap` · `scale` · `side` ·
`topPct` · `logoPct` · `qrPct` · `framePos` · `photoWidthPct` · `decorOpacity` · `decorScale` ·
`hideDecor` · and portrait positions `titleTop` / `heroTop` / `bodyTop` / `qrTop` / `noteTop` /
`logoTop` / `buttonTop` / `buttonPct` / `buttonGap` (percent numbers).

To tune placement automatically instead of by hand, run **`workflows/adapt-iterate.js`** (via
the Workflow tool): a planner sets placement from the layers + negative space, then a render →
fresh-eyes-critic loop tunes the overrides. Both planner and critic hold the result to
`references/design-principles.md` — read it first.

## Review & iterate — the REQUIRED final step (never ship the first render)
After rendering, **every output is judged and fixed before it ships.** Run
**`workflows/review-iterate.js`** (via the Workflow tool): for each format it renders, then a
**fresh-eyes vision reviewer reads the actual rendered pixels** and judges them against
`references/review-rubric.md` — extraction integrity first (no dropped / doubled component, no
haloed cutout, no fuzzy / garbled or non-joining glyphs, correct reading direction), then
composition (one focal point; a cropped figure seated on its edge not floating; nothing
colliding or clipped; even margins & safe zones; real hierarchy; restrained decoration). It
returns concrete issues + an `overrides` patch, applies it, **re-renders, and re-reviews in a
loop until no blocker / major issue remains.** Layout problems are fixed by overrides;
integrity blockers (artifacts, mojibake, a dropped layer) are flagged to fix upstream in
`decompose`. `decompose` writes a `source.png` for the reviewer to compare against. Reviewing
by hand is fine — hold each output to the same rubric and iterate the overrides the same way.

> The bundled workflows carry `EDIT-ME` path constants at the top of each `.js` — set them
> before running; they also accept `args` where the runtime supports it.

## Flat fallback — only for a truly flat photo (no vectors, no live text)
When nothing can be lifted, rebuild from style tokens instead of replaying real layers:
```
PY scripts/ingest.py <design-file> <project>   # -> draft content.json + hero cutout
PY scripts/build.py <project>                  # -> out/*.png    (--only key,key)
PY scripts/contact_sheet.py <project>          # -> out/_contact_sheet.png review grid
```
Then edit `<project>/content.json` — the copy (`kicker` / `headline` / `subhead` / `body` /
`cta` / `contact`) and the `style` tokens: `bg`, `ink`, `accent`, `headline`
(+ optional `headlineAccent`), `cta:{bg,ink,border}`, `scrim`, `uppercase`,
`decor` (none|hex|dots|soft), `dir` (ltr|rtl), `fonts` (point to a script-capable TTF in
`assets/fonts/`; **Cairo / Arabic is bundled**). In this path `assets/formats.json` tags each
size with a `layoutClass` (square|portrait|landscape|strip|billboard) and `level`
(full|medium|minimal) that drive `build.py`'s layouts (the default engine above instead picks
layout from the aspect ratio). Per-tool ingestion — PSD / SVG / PNG / JPG and **Canva** (export
as PDF or SVG, never a flat PNG) — is in `references/inputs.md`. To add a platform, append a row
to `assets/formats.json`.

## Honest limitations
- Hero quality depends on the source: a layered PSD yields a clean hero from its own layer;
  a flat PNG relies on a `rembg` cutout that can still need a manual re-cut or a supplied
  transparent PNG for a perfect edge.
- Auto role / colour / direction guesses are heuristics — confirm `layers.json` (or
  `content.json`) before shipping.
- The component model fits **marketing / promo** designs (brand + headline + hero + CTA); it
  is not meant for dense editorial layouts or data-heavy infographics.

## Files
- **Default path:** `scripts/setup.py` (installer — builds the venv both paths use) ·
  `scripts/decompose.py` (PROBE + REPLAY the real components) · `scripts/recompose.py`
  (RE-ARRANGE them per size)
- **Iterate:** `workflows/adapt-iterate.js` (optional planner + critic loop) ·
  **`workflows/review-iterate.js`** (required render → vision-review → fix loop) ·
  `references/review-rubric.md` (the checkable, worst-first reviewer checklist)
- **Flat fallback (truly flat photo only):** `scripts/ingest.py` · `scripts/build.py` ·
  `scripts/contact_sheet.py`
- `assets/formats.json` (target deliverables) · `assets/fonts/` (bundled OFL fonts)
- `references/platform-layouts.md` (per-platform sizes + direction) ·
  `references/inputs.md` (per-tool ingestion, incl. Canva & PSD) ·
  `references/design-principles.md` (the quality bar + the **Taste** rules every output is held to)
