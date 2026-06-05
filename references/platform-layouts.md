# Platform layouts & direction

This is the "where does everything go" reference. Adobe's resize skill answers
this with *which expanded canvas to crop from and what to keep in frame*. We
answer it with *which composition to rebuild and how much copy to keep* — so the
result is recomposed, not cropped.

Every format in `formats.json` carries a **`layoutClass`** (the composition) and a
**`level`** (how much content survives). Change either to re-target a format.

## The five layout classes

| Class | Aspect feel | Composition strategy | Hero | Copy |
|-------|-------------|----------------------|------|------|
| `square` | ~1:1 | logo top-left, headline block left, hero bottom-right, CTA+contact on a bottom scrim | bottom-right, ~74% height | full |
| `portrait` | taller than 4:5 → 9:16 | vertical stack: logo top · headline · subhead · hero centred-bottom · CTA+contact on bottom scrim | centred, anchored to bottom | drop the paragraph (glanceable) |
| `landscape` | wider than 1:1 → 16:9 | editorial split: text column left (headline·subhead·body·CTA), hero right full-height, contact bottom-left | right, full height | full |
| `strip` | very wide (≥3:1) | single row: logo · headline · CTA pill | omitted (no room) | headline only |
| `billboard` | wide + large (outdoor/TV) | huge headline + phone, hero on one third, **no body** | right third | headline + phone only |

## Content levels
- **full** — kicker, headline, subhead, body, CTA, hero, logo, contact.
- **medium** — same minus the body paragraph (portrait/poster default).
- **minimal** — headline + CTA/phone + logo only (banners, billboards).

Stories are forced to `medium` inside the engine even if set to `full`: a
paragraph on a 9:16 story competes with the hero and never gets read.

## Why re-layout, not crop
A 28×19″ poster cropped to 9:16 either letterboxes or slices the hero in half,
and the headline that was set for a wide measure becomes unreadably small. By
rebuilding from components we keep the **reading order** (eyebrow → headline →
support → action) intact at every ratio, scale type to the new measure, and shed
copy the format can't carry.

## Per-format direction & safe zones

| Format | Class / level | Direction notes |
|--------|---------------|-----------------|
| Instagram/FB square 1080² | square / full | Most balanced; safe default. |
| Instagram portrait 1080×1350 (4:5) | portrait / full | Largest feed real-estate on IG; keep CTA above the bottom ~6%. |
| Instagram Story/Reel · Snapchat · TikTok 1080×1920 | portrait / full→medium | Keep all content inside the central **1080×1420** safe band — top ~250px (handle) and bottom ~250px (caption/▲ UI, TikTok right-rail icons) get covered. The bottom scrim + CTA already sit inside this. |
| Pinterest Pin 1000×1500 (2:3) | portrait / medium | Vertical; text-forward performs well — keep headline dominant. |
| Facebook feed 1200×630 · LinkedIn 1200×627 | landscape / full | ~1.91:1 link/share image; hero right, text left. |
| X/Twitter 1600×900 (16:9) | landscape / full | In-stream; center-weight the text column. |
| YouTube thumbnail 1280×720 | landscape / full | Will be seen tiny — push headline size up, keep ≤4 words emphasized. |
| Web leaderboard 728×90 | strip / minimal | logo · headline · CTA only; no hero. |
| Web billboard banner 970×250 | strip / minimal | Two-line headline fits; compact CTA. |
| Web skyscraper 300×600 | portrait / minimal | Very narrow — logo top, stacked headline, hero small/optional, CTA bottom. |
| Bus shelter 6-sheet 1200×1800 · Roll-up standee 1000×2400 | portrait / medium | Read at distance + standing height; subhead not body. |
| Billboard 48-sheet 2400×1200 · Digital screen 1920×1080 | billboard / minimal | ≤6 words + phone/URL; viewed for ~1s at speed. |

## Platform → formats to render
When the user names platforms (the way Adobe's skill asks "which platforms?"),
render just those keys with `build.py --only`. Several platforms share one canvas,
so a single render serves many — no need to duplicate work.

| Platform | `--only` keys |
|----------|---------------|
| Instagram | `instagram_post,instagram_portrait,instagram_story` |
| Facebook | `instagram_post,facebook_feed,instagram_story` |
| LinkedIn | `linkedin_post,instagram_post` |
| X / Twitter | `x_post,instagram_post` |
| YouTube | `youtube_thumb` |
| TikTok | `tiktok` |
| Snapchat | `snapchat_story` |
| Pinterest | `pinterest_pin` |
| Threads | `instagram_portrait` |
| Web display ads | `web_leaderboard,web_banner_wide,web_skyscraper` |
| Out-of-home / print | `bus_shelter_6sheet,roll_up_standee,billboard_48sheet,digital_screen_16x9` |
| **Everything** | omit `--only` |

Canvas sizes follow current platform specs: 1:1 1080², 4:5 1080×1350, 9:16
1080×1920, ~1.91:1 1200×630, 16:9 1280×720 / 1600×900, 2:3 1000×1500. For a big
cross-platform batch, render one of each class first as a quick preview
(`--only instagram_post,instagram_story,linkedin_post`), confirm the copy/brand
with the user, then render the rest — the same safety-net idea as Adobe's 3-crop test.

## Tuning a format
- Too cramped at a given size? Drop its `level` (full→medium→minimal).
- Want the hero bigger/smaller or moved? Edit the matching `layout_*` function's
  CSS in `scripts/build.py` (sizes are in `vw`/`vh`/`vmin`, so they scale with the
  canvas automatically).
- New size? Append one row to `formats.json` with the closest `layoutClass`.
