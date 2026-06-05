# Design principles for multi-format adaptation

The standard the planner and critic hold every output to. These are general rules
of thumb — apply judgement, not literal compliance. Improve this file as principles,
rules and tips; never encode one-off, example-specific instructions.

## Core philosophy
- **Adapt by re-arranging real layers, don't regenerate.** When the source has
  separable layers (structured PDF/PSD), preserve its actual background, imagery,
  buttons, decorations and text and move them. Rebuild from tokens only when the art
  is genuinely flat and nothing can be separated.
- **Re-flow, don't rescale.** A different aspect ratio is a different composition, not
  a stretched copy. Decide placement for each ratio; shed content that doesn't fit.
- **Aim for "would a human designer ship this?"** If a choice looks automated
  (cramped type, a label floating on a product, a halo around text), it fails.

## Process — Think → Plan → Act → Iterate
- **Think:** read the layers and the image. Where is the subject? Where is the clean
  empty space? What is the reading direction? What must survive at this size?
- **Plan:** state placement intent before rendering (which side/zone for text, how the
  background is framed, which accents stay). Concise rules beat fiddly absolute coords.
- **Act:** render exact pixels.
- **Iterate:** look at the result with fresh eyes and fix it; repeat until it reads as
  intentional.

## Composition & negative space
- **Never place text or a button over a busy area or over an image element.** Put copy
  in the calmest, emptiest region (the negative space). If there isn't enough clean
  space, reframe the background to create some, or shrink/relocate the copy.
- **An opaque/framed photo gets its OWN zone; only a cut-out can share space with type.**
  A rectangular photo that fills its box is a wall — give it a band or a side of its own
  and put every word in the adjacent clean area; stacking type on top of it always looks
  broken. A transparent cut-out subject (a figure on no background) is the exception: copy
  may sit in the empty space around it. Decide which kind the hero is *before* placing copy,
  and re-decide the split per ratio (photo bottom + text top for a tall frame, photo one
  side + text the other for a wide one).
- **Frame the background to keep the subject in view and open up empty space** for type
  on the opposite side. Anchor the subject; let the plain area carry the message.
- **One clear focal point.** One element wins by size or contrast — squint at the thumbnail
  and one thing should clearly lead, with type supporting. If two compete, enlarge the hero or
  mute the rival. (A deliberately type-only or evenly patterned frame has no photographic hero
  — don't invent one.)
- **Balance visual weight.** A heavy subject on one side wants type / anchoring weight or
  active negative space opposite, so the frame doesn't tip — never pool all weight in one
  corner with the other empty.
- **When the hero takes a side, every caption moves to the open side.** Corner captions
  that lived at four corners of the original can't stay at the corners once a photo fills
  one half — the ones over the photo get hidden. Re-home them into the text area/column
  (eyebrows on top, contact/footer at the bottom). After laying out, check that nothing is
  stranded behind the hero.
- **Fit the stack to the canvas — never let a column overflow.** A tall headline plus
  several captions can run off the top/bottom of a short or busy format. Measure the parts
  and scale the whole stack down to fit with margins; clipped type at an edge is an
  auto-fail. Shrink only as much as needed, so roomy formats keep full-size type.

## Hierarchy & type
- **Preserve reading order:** eyebrow → headline → subhead → action.
- **Real hierarchy that survives grayscale.** The headline is clearly dominant (≈2× body),
  reinforced by weight/case, with at least three steps (headline / subhead-body / caption).
- **Re-stack copy in the source's reading order, not by font size.** Size decides which
  part is *the headline*; it does not decide stack order. When one phrase is split across
  parts of different sizes (a small connector tucked over a giant number/price), keep them
  in the order they read in the source so the new layout still reads as a sentence — sorting
  the column purely by size floats the loud fragment to the top and scrambles the meaning.
- **Scale type to the medium and viewing distance.** Far-viewed or small formats need bigger,
  fewer words (billboards/stories: a few words on one or two big lines) — drop secondary copy
  and long contact strings rather than shrink type to fit; dense paragraphs are only for
  formats people dwell on.
- **Legibility first.** Enough size and contrast against whatever sits behind the text; don't
  uniformly scale source point sizes — enforce a readable minimum for the medium, and collapse
  to fewer levels when tight.
- **Keep the source's type colour and style** when preserving layers; match closely
  when rebuilding.

## Margins, safe zones & cropping
- **Generous, even margins.** Nothing should touch or crowd an edge; consistent insets
  read as intentional.
- **Respect platform safe zones.** Vertical stories/reels hide the top and bottom bands
  behind UI — keep essential content within the central safe area.
- **Never crop the subject awkwardly** (no half-cut faces/products). If cover-cropping,
  position so the subject stays whole.

## Content level by format
- **Full** (square/landscape feed): headline + subhead + body + action.
- **Medium** (portrait/poster): drop the paragraph; headline + subhead + action.
- **Minimal** (banners, billboards, fast-glance): headline + one action only — a few
  words read in a second or two.

## Decoration discipline
- **Accents support; they never compete.** Keep decorative shapes/line-art/shadows only
  where they add atmosphere; if an ornament pulls the eye before the headline or overlaps the
  type or subject, mute, shrink, or cut it.
- **When a decoration crowds the copy or clutters a premium layout, cut it or fade it.**
  Empty space is a feature; restraint reads as expensive.

## Colour, brand & direction
- **Hold the brand/kit together across sizes:** same palette, type, logo treatment, and the
  same hero re-cropped — a set reads as one campaign, with variation from layout, not new assets.
- **Respect reading direction.** For RTL scripts, mirror the layout and right-align;
  disable letter-spacing that breaks cursive joins.
- **Backgrounds should be seamless.** If you extend or fill around a photo, match its
  edge colour and fade the seam so no hard line shows.

## Red flags (auto-fail)
Text/button on the product, a box/halo around keyed text or a hard photo-to-fill seam,
cramped/uneven margins, a face/edge crop, too much copy for a glance, or decoration fighting
the headline. `review-rubric.md` is the full, severity-tagged checklist.

## Reading the source correctly (decomposition)
- **Spot vector-flattened sources.** If a structured file has few/no live text runs
  but lots of vector shapes, its text and art are *outlined* — the live-text +
  image-layer model will mislabel things. Don't rebuild and don't crop-and-key; instead
  read the real drawings and **replay each element's vector paths onto its own
  transparent canvas** (see "A vector-flattened source still has the real components").
  Re-check the direction and every role by hand before composing.
- **A background must bleed to the page edges.** A large image that sits inside the
  margins is a *subject* (hero), not a background — area alone is misleading.
- **A ring/frame BLANKETS the photo; a corner decoration does not.** A photo's image
  rectangle is often much larger than what shows, so any decoration that overlaps that
  rectangle looks "attached". Only treat a shape as the photo's ring/frame if it sits
  inside *and* covers most of the displayed region (it surrounds the photo). A motif that
  merely clips one corner of the bounding box (a ring bleeding off a corner, a dot grid) is
  its own decoration — keep it separate so it can move independently.
- **Capture clipped/masked images in their displayed SHAPE** (with their frame/ring),
  not the raw rectangle, or you lose the design treatment. The crop is often a vector
  **clip path** — a rounded rectangle or organic blob — that is neither a fill nor an
  image alpha mask, so a naive extract squares it off. Read the source's clip paths
  (extended drawings) and apply the one that bounds the image as the photo's mask, so the
  real rounded/organic/masked edge is preserved when the photo moves to a new format.
- **Assign type roles by SIZE first, then position.** The headline is the *largest* type
  wherever it sits — it is not whatever happens to be highest on the page. A small block in
  a corner is an eyebrow (if up top) or a contact/footer line (if at the bottom), never the
  headline. So: rank the type by prominence (area / cap-height), call the biggest one or two
  the headline/subhead, and treat the small corner blocks as captions by their position.
  A design often has captions *above* the headline (an "invitation" eyebrow over a big
  title) — pure top-to-bottom ordering would crown the eyebrow, which is wrong.
- **Read the real background colour from a full-page fill — it can be any colour.** The
  field behind everything is often a single page-sized rectangle; record its actual colour
  (lavender, navy, cream…) and don't assume white. A coloured full-page fill is the
  background, not a movable shape, and must never be attached to a photo as a "frame".
  A **coloured** ground wins even when a plain white page-rect was painted *under* it first —
  that white is a print knockout plate (a fallback only); never let it steal the real colour.
- **A CTA pill can be a vector shape, not only a placed image.** A small filled, often
  rounded, rectangle that a text label sits inside is a button. Capture it by rendering the
  page over its box (so the fill, the label, and the paint order all come through exactly),
  mask it to its real rounded outline so the corners aren't squared, and bind the label to
  the pill as one unit — so the CTA never floats free of its pill in the new layout.
- **Tell a framed photo from a cut-out by its alpha.** A hero whose box is (near) fully
  opaque is a framed rectangular photo and must claim its own zone; a hero with large
  transparent regions is a cut-out figure that type can surround (and that should seat on
  the edge it is cropped at). Carry this flag into layout — it decides overlay vs. split.
- **Detect reading direction from the dominant script of the main copy**, not a single
  character — and only when there's enough text to trust. Allow per-element direction
  for genuinely mixed-script designs.
- **Elements that overlap by design can't be cleanly separated.** A title set over a
  photo, two stacked words sharing a backing shape — keep the overlapping group
  together (or re-typeset), rather than splitting them, which causes ghosting/clipping.

## A vector-flattened source still has the real components — extract them, never substitute
- **A flat/outlined file has no live layers, but every element is still there** as vector
  paths plus embedded rasters. Lift those. **Never re-typeset the title in a lookalike
  font or recreate the background shapes from scratch** — substituting is inventing, it
  never matches the original, and reusing the genuine assets is the whole job.
- **Inspect the real geometry before touching pixels:** list embedded images by reference
  (xref) and dump every vector drawing with its fill colour, bbox and area. Now you know
  the true background colour, which paths are the title vs the blobs vs the body, and
  which elements are photos — instead of eyeballing crop fractions (which is what clips
  glyphs and mislabels roles).
- **Replay the real vector paths onto transparent canvases, grouped by element** (the
  title, each blob, the logo, each text block), each drawn in its own real fill
  colour/opacity. This is exact, resolution-independent, and — unlike cropping — cannot
  drag in an overlapping neighbour: a title that sits on a background blob comes away
  clean because you draw only the title's paths.
- **Don't crop overlapping vector art from a flat render.** Keying a rectangular crop to
  transparent pulls in whatever shares that rectangle (the blob behind the headline, the
  photo behind the title). Isolate each element's paths and render them alone instead.
- **Lift embedded photos by their real raster + real mask:** pull the image by xref, then
  re-apply the source's own clip shape (its oval/organic mask) and its real decorative
  ring/frame — don't approximate the treatment with a CSS circle or box-shadow.
- Re-check direction and every role by hand after extraction, then re-arrange the real
  pieces per format exactly as you would real layers.

## Judge the shipped pixels, not the effort (review before shipping)
- **A rating reflects only "would a client ship this?"** — never how hard the result was to
  produce. A clipped headline or a decoration colliding with type fails at any effort level.
- **Review the rendered pixels before shipping; don't trust the first render.** Look at each
  output as a ruthless, fresh-eyes critic and hold it to `review-rubric.md` — one dominant
  focal point, the figure anchored not floating, nothing colliding or clipped, even margins,
  safe zones, real hierarchy, and no extraction artifacts (haloed cutouts, fuzzy/garbled
  glyphs, a dropped or doubled component, wrong reading direction). **Iterate until it passes**
  — one pass rarely lands; the `review-iterate` workflow exists to catch what the maker is
  blind to. Fix every issue it raises before the design ships.

## Aspect-distance strategy
- **Close target aspect → preserve the whole composition and pad/reframe.** Minimal
  rearrangement is the most faithful; don't dismantle a layout you don't need to.
- **Far target aspect (e.g. portrait → wide) → you must split and re-place elements.**
  Move the real extracted pieces into a new arrangement (e.g. photo to one side, the type
  stack to the other) — for a flat/outlined source that means replaying its real vector
  paths as separate movable pieces, never a crop and never a rebuild.

## Taste — the judgment that separates "designed" from "auto-filled"
Running the process is not enough. These are the calls a person makes that a template does
not. Hold every output to them, and **re-decide them for each ratio** — never just centre the
old layout in a new box.

**Focal point & the subject**
- **Seat the subject off-centre, on the new frame's thirds** — not dead-centre, unless the
  piece is deliberately symmetric.
- **Crop figures on safe lines, and bond the cut to the edge.** Cut a person through soft
  areas (mid-torso, mid-thigh), never a joint (neck, wrist, knee, ankle) or the face. A
  figure the frame cuts must **bleed flush to the edge it is cut at** so it "sits in" the
  frame; a cropped subject left floating with a sliver of background on its cut side reads as
  a pasted cutout. (That intentional bleed is *not* a tangent — see below.)
- **Ground a cutout; don't let it float.** A subject with no edge-contact, baseline, or
  contact shadow hovers like a paste-in. Anchor its base to an edge or give it a ground.
- **Give the subject lead room.** It should face/gaze *into* the frame, with the larger open
  space ahead of it — never looking off the nearest edge.
- **Keep the hero in a sensible size band:** big enough to read (bigger for far-viewed/small
  formats), never swimming in empty space, never jammed edge-to-edge — a deliberate breathing
  gap unless it is an intentional full bleed.

**Composition**
- **Protect one quiet zone.** Don't auto-expand content to fill the slack a new ratio creates;
  edge-to-edge density reads as automated.
- **No accidental tangents.** A *non-bleeding* element must not merely kiss another element or
  graze a frame edge — give a clear gap or a decisive overlap. (A subject intentionally bled
  off an edge is correct; a logo whose corner barely touches the margin is not.)
- **Align to shared edges, don't centre everything.** Stacked elements share a left/right edge
  or a grid line. Reserve centred alignment for a short headline or a symmetric lockup — "every
  block on the centre line" is the single most common automated tell.
- **Match flow to orientation.** Wide frames read left→right along the long axis; tall frames
  stack vertically. Never drop a portrait stack as a small clump into a wide billboard.
