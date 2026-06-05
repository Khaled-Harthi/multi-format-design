# Multi-format design

Turn ONE finished design into many platform sizes — **recomposed for each aspect ratio, not
stretched or cropped.** Hand it a poster, flyer, ad, or social graphic plus a list of
destinations; it recreates the design's *real* components (photos with their real crops,
buttons, shapes, logo, type) and re-arranges them per size, trimming copy for fast-glance
formats. Works for any brand, LTR or RTL / Arabic.

This repo is built to be **driven by [Claude Code](https://claude.com/claude-code).** The
included [`CLAUDE.md`](CLAUDE.md) turns Claude into a specialized design-adaptation agent that
does the production and hands back finished files — without exposing the machinery.

## Use it with Claude Code
```bash
git clone <this-repo-url>
cd multi-format-design
claude            # or open the folder in Claude Code
```
Then just talk to it, attaching your design:

> "Adapt this for an Instagram story and a billboard."

It sets up its toolchain on first run, produces the sizes, reviews them against its own design
bar, and hands you the finished PNGs. You never touch the internals.

## What makes it different
- **Re-composition, not resizing.** A wide poster becomes a true 9:16 story — not a
  letterboxed or mid-subject crop.
- **Preserves the real design.** Real photos (rounded/masked edges intact), real fonts, real
  colours — moved, never redrawn or faked.
- **Has taste, and reviews itself.** Every output is judged against a design rubric and fixed
  before it's delivered.
- **Speaks design, not plumbing.** As an agent it talks about *the photo* and *the headline*,
  never layers, scripts, or settings.

## Manual use (without the agent)
```bash
python scripts/setup.py <project>                            # one-time toolchain (.venv)
<venv-python> scripts/decompose.py <design-file> <project>   # recreate the real pieces
<venv-python> scripts/recompose.py <project> --only instagram_story,billboard_48sheet
```
Outputs land in `<project>/out/`. Format keys are in
[`references/platform-layouts.md`](references/platform-layouts.md); the full operating guide is
[`CLAUDE.md`](CLAUDE.md).

## Layout
| Path | What |
|---|---|
| `CLAUDE.md` | The agent's operating + behaviour guide (the brain). |
| `scripts/` | The engine: `setup` · `decompose` (recreate pieces) · `recompose` (re-arrange) · flat-source fallback. |
| `references/` | Quality bar, review checklist, platform sizes, per-source ingestion notes. |
| `workflows/` | The review-and-fix loop and an optional auto-placement loop. |
| `assets/` | Target sizes (`formats.json`) + bundled fonts. |

## Licensing
Code is under the MIT License (see [`LICENSE`](LICENSE)). Bundled fonts in `assets/fonts/` are
under the SIL Open Font License.
