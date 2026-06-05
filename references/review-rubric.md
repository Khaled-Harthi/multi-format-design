# Reviewer rubric — judge the shipped pixels

The checklist a reviewer applies to **one rendered output**, looking only at the image (plus
the original source render for comparison and the `layers.json` kit list). Every item is an
**observable** property — no pipeline intent or coordinate metadata required. Score worst-first;
**any unresolved Blocker or Major = the format fails and must be re-rendered with a fix.**

How to use it (and what to return):
- For each item, decide pass / fail from what you actually see. Quote the specific thing you see.
- Tag each failure `blocker` (broken/unshippable), `major` (clearly looks automated/wrong), or
  `minor` (polish).
- For a **layout** failure, give an `overrides` patch (keys below) the loop can apply and
  re-render. For an **upstream** failure (artifact, dropped component, mojibake, wrong
  direction) set `fixable:false` and name the upstream fix — overrides can't repair it.
- Approve only when no blocker/major remains. Don't invent problems; a clean output passes.

The override knobs (per-format, in `overrides.json`): `heroAnchorY` (top|center|bottom|overlay),
`heroSide` (left|right), `heroPct`, `heroFit` (cover|contain), `marginPct`, `gapPct`, `widthPct`,
`cap`, `scale`, `logoPct`, `qrPct`, `decorOpacity`, `decorScale`, `hideDecor`, `framePos`,
`photoWidthPct`, and portrait positions `titleTop`/`heroTop`/`bodyTop`/`qrTop`/`noteTop`/
`logoTop`/`buttonTop`/`buttonPct`/`buttonGap`.

---

## A. Blockers — integrity & extraction (usually an upstream fix, `fixable:false`)
These are the failures *this* engine actually produces. Check them first.

1. **Missing or doubled component.** Compare against the source: is every essential element
   (hero, headline, logo, CTA/button, key contact) present, and **exactly once**? → Fail if the
   hero or a required line is gone, or any element renders twice. Upstream: fix decompose
   role/extraction; don't ship.
2. **Garbled or boxed glyphs (mojibake / tofu / broken joins).** Any `□` boxes, missing glyphs,
   or — for Arabic — letters that don't join (disconnected letterforms) or run left-to-right.
   → Fail. Upstream: font/shaping/direction problem.
3. **Cutout / mask artifacts.** A halo or colored fringe around a cutout (e.g. hair), a jagged
   or chewed silhouette, a residual rectangular matte, or a clip/rounded corner that got
   squared off. → Fail. Upstream: re-cut the hero / fix the mask.
4. **Fuzzy or upscaled-to-mush art.** A keyed-text or photo element is visibly soft, aliased,
   or pixelated for the canvas size (e.g. a small source blown up to billboard). → Fail.
   Upstream: higher-res extraction or a different source.
5. **Wrong reading direction (RTL/LTR).** For Arabic/Hebrew copy: text must read right-to-left,
   the layout mirrored (logo/CTA/lead-room on the correct side), not forced into a Latin
   left-aligned stack. → Fail if mirrored wrong. Fix: `dir` in `layers.json`; may need re-layout.
6. **Wrong canvas / letterbox.** The output isn't the requested pixel size, or the real design
   sits as a smaller rectangle inside flat bars. → Fail. Fix: render at the correct size / fill
   the ratio (don't letterbox).

## B. Major — composition & taste (usually fixable via `overrides`)
7. **Focal subject cropped out or unreadable.** The intended hero's head/key part is cut off by
   the frame, or it's shrunk to a tiny clump and lost. → Fix: `heroPct` up, re-anchor, or
   re-place on the new thirds. (Skip for deliberately type-only frames.)
8. **Floating cutout / figure not anchored.** A figure the frame cuts (its silhouette is flat
   across the bottom/edge) is hovering with a gap of background between the cut and the frame
   edge, instead of sitting on it. → Fix: `heroAnchorY:"bottom"` (or the cut edge). **Note: a
   subject correctly bled flush to its cut edge is NOT a tangent — do not flag it as one.**
9. **Text/element collision or occlusion.** Text sits on a busy part of the hero and half-
   disappears, crashes into another element, or re-stacking put a block on top of the product /
   wrong z-order. → Fix: move it to the clean side (`heroSide`/`widthPct`/`*Top`), add space
   (`gapPct`/`marginPct`), or `hideDecor`.
10. **Clipped or overflowing content.** A headline, line, or whole element runs off an edge or
    is cut by its column. → Fix: shrink the stack (`cap` down, `gapPct` down) or `marginPct`.
11. **Everything centered / no alignment.** Every block pinned to the centre line with two
    ragged margins, or elements each on their own near-but-different axis. → Fix: a side layout
    (`heroSide` + column) or share an edge.
12. **Uneven or wrong margins.** Tight on one side, loose/near-touching on another; or a tiny
    central clump in a wide frame with huge empty sides. → Fix: `marginPct`, or re-flow along
    the long axis for wide frames.
13. **Weak hierarchy.** Headline, subhead, body look ~the same size; nothing dominates. → Fix:
    enlarge the headline (it's the biggest extracted type — check roles), shrink competitors.
14. **Too much copy for a glance format.** A billboard/story carries a paragraph or multiple
    blocks unreadable in a few seconds. → Fix: drop secondary lines/contact (the engine's
    `level:minimal`), keep the one takeaway.
15. **Decoration competes with the message.** An ornament/blob pulls the eye before the
    headline or overlaps the hero/text. → Fix: `decorOpacity` down or `hideDecor`.

## C. Minor — polish
16. **Accidental tangent.** A *non-bleeding* element just grazes an edge or another element. →
    Fix: small `marginPct`/position nudge for a clear gap.
17. **Lead room / balance.** Subject faces off the near edge with space stranded behind it, or
    one corner is heavy and the opposite dead. → Fix: `heroSide`/flip, or rebalance.
18. **Crowded / no quiet zone.** No deliberate area of rest. → Fix: `marginPct` up, shrink the
    busiest cluster.

## D. Set-level — needs all siblings together (run once, not per image)
- **Consistency:** same palette, type, logo treatment, and the same hero re-cropped across the
  set; hero size stays in one band (not 90% in one ratio and 25% in another). → Re-scale the
  outliers.
- **Cohesion:** placed side by side, the frames read as one campaign — variation from layout,
  not swapped assets.

---

**Severity → action.** Blocker: stop, fix upstream, re-extract. Major: apply the override fix
and re-render. Minor: fix if cheap; never let a pile of minors masquerade as "good". Re-review
after every change; **loop until no blocker/major remains.** Judgment-call thresholds (margins
"even", space "generous") are deliberately not numeric — use a designer's eye, and when in
doubt compare to the source's own restraint.
