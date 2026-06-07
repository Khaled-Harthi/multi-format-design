# Accepting designs from any tool

> **This page describes the flat token-rebuild FALLBACK.** The default engine is
> `decompose.py` → `recompose.py` (probe the real layers and replay them — see CLAUDE.md), and
> it is the preferred handler for layered/vector **PDF / AI / PSD**. Use `ingest.py` →
> `build.py` below only for a genuinely flat source (a single PNG/JPG with no vectors or live
> text) or when you deliberately want a token rebuild.

The flat path renders from a **content model** (`content.json`: copy + colors + a hero
image). `scripts/ingest.py` builds a *draft* of that model from whatever the user
brings. The richer the source, the more is filled in automatically.

## Input matrix

| Source | Extractor | What comes through automatically |
|--------|-----------|----------------------------------|
| **PSD / PSB** (Photoshop) | `psd-tools` | **Named layers → components**; **text layers → editable copy + font size**; largest non-background image layer → hero. Best case. |
| **AI / PDF** (Illustrator, exports) | PyMuPDF | Vector render + palette; live text if present, else outlined (copy must be typed in); subject cut from the flattened render. |
| **SVG** | Chromium raster + XML parse | `<text>` → copy, `fill=` → palette; subject cut from the raster. |
| **PNG / JPG** | Pillow + `rembg` | Palette (color quantize) + subject cutout as hero. No copy (type it in). |
| **Canva** | *export first* (see below) | Depends on the export format you choose. |

Run it: `python scripts/ingest.py <file> <project-dir>`. It writes
`content.json` (or `content.draft.json` if one exists), copies `formats.json` in,
and saves `assets/components/hero.png`. Then a human edits the copy/colors and runs
`build.py`.

## Photoshop (PSD) — the layer advantage
Adobe's own resize skill **flattens** PSD and AI before cropping, discarding the
layer structure. We do the opposite: `psd-tools` walks the layer tree, so a layer
named `headline`, `logo`, `cta`, or `hero` maps straight onto a component, and text
layers hand us the actual words. Name your layers sensibly and ingestion is nearly
automatic. (Smart-object–heavy or PSB files that fail to parse fall back to the
flattened-raster path — same as a PNG.)

## Canva — export as PDF or SVG, then ingest
Canva is a closed web app with **no local file format**, so "accept Canva" means
accepting what Canva exports. **Tell the user to download it as PDF or SVG** — both
are vector and keep the text + shapes, which is what lets us recompose the layout.
From the Canva editor: **Share → Download**, then:

| Export | When | Quality for us |
|--------|------|----------------|
| **PDF Print** | ✅ recommended | keeps vectors + selectable text → best decomposition |
| **SVG** (Canva Pro) | ✅ also great | groups/text parse cleanly |
| **PNG** (2×) | last resort only | flat — hero cutout + palette only, copy must be retyped |

Then: `python scripts/ingest.py my-canva-export.pdf <project-dir>`.

### Optional: pull from Canva automatically (Connect API)
For power users who don't want to export by hand, Canva's **Connect API** can list
and export designs programmatically:
1. Create an app at `canva.com/developers`, enable the **Design Export** scope.
2. OAuth 2.0 to get a user token.
3. `POST /v1/exports` with the design id and `format: pdf|png` → poll the job →
   download the asset → feed that file to `ingest.py`.

This needs per-user OAuth setup, so it's **off by default** — the export path above
needs nothing. Wire it in only if a team wants hands-free Canva pulls.

## After ingest, always
1. Open `content.json` and fix the copy (the eyebrow/headline/subhead/body/CTA/
   contact) and the color slots — auto-extraction is a starting point, not final.
2. Check `assets/components/hero.png`; re-cut or replace if the subject is rough.
3. `python scripts/build.py <project-dir>` then `contact_sheet.py <project-dir>`.
