export const meta = {
  name: 'review-iterate',
  description: 'Render each format, have a fresh-eyes vision reviewer judge it against the rubric, apply override fixes, and re-render until it passes',
  phases: [
    { title: 'Review', detail: 'render + vision-review each format against review-rubric.md' },
    { title: 'Fix', detail: 'apply override patches and re-render until no blocker/major remains' },
  ],
}

// ── Run config ─────────────────────────────────────────────────────────────────────
// Pass these via the Workflow tool's `args`, e.g.
//   Workflow({ name:'review-iterate', args:{ project:'/abs/proj', venv:'/abs/.venv/bin/python',
//     scripts:'/abs/multi-format-design/scripts', rubric:'/abs/multi-format-design/references/review-rubric.md',
//     formats:['billboard_48sheet','instagram_story'], maxRounds:3 } })
// If args is unavailable in your runtime, EDIT the fallback block below.
const CFG = (typeof args !== 'undefined' && args && args.project) ? args : {
  project: '/EDIT/ME/project',
  venv:    '/EDIT/ME/.venv/bin/python',
  scripts: '/EDIT/ME/multi-format-design/scripts',
  rubric:  '/EDIT/ME/multi-format-design/references/review-rubric.md',
  formats: ['billboard_48sheet', 'instagram_story'],
  maxRounds: 3,
}

const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    format: { type: 'string' },
    pass: { type: 'boolean', description: 'true ONLY if no blocker and no major issue remain' },
    issues: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
          item: { type: 'string', description: 'the rubric item, e.g. "B8 floating figure"' },
          observation: { type: 'string', description: 'what you actually see' },
          fixable: { type: 'boolean', description: 'true if a layout override can fix it; false for upstream artifacts/dropped components/mojibake/direction' },
        },
        required: ['severity', 'item', 'observation', 'fixable'],
      },
    },
    overrides: { type: 'object', additionalProperties: true, description: 'override knobs to apply for this format; empty if none' },
    summary: { type: 'string' },
  },
  required: ['format', 'pass', 'issues', 'overrides', 'summary'],
}

function reviewerPrompt(fmt) {
  return `You are a ruthless, fresh-eyes design reviewer. Judge ONE rendered output on its merits.

Read these (Read tool):
- rendered output: ${CFG.project}/out/${fmt}.png
- the component kit that SHOULD be present (roles list): ${CFG.project}/layers.json
- the reviewer rubric: ${CFG.rubric}
- the original source, for comparison: ${CFG.project}/source.png  (read it if it exists)

Judge the output against EVERY rubric item — Section A blockers first, then B major, then C minor.
Look ONLY at what you can see in the image. For each problem you genuinely see, record an issue:
severity (blocker|major|minor), the rubric item id+name, a one-line observation quoting what you see,
and fixable (true if a layout override fixes it; false for upstream artifacts/dropped or doubled
components/mojibake/wrong reading direction).

Then produce \`overrides\`: a JSON object of ONLY the knobs you are changing to fix the layout
issues, chosen from: heroAnchorY (top|center|bottom), heroSide (left|right), heroPct (number, %),
marginPct, gapPct, widthPct, cap (0-1), decorOpacity (0-1), hideDecor (bool), framePos
(left|right|center), photoWidthPct, titleTop, heroTop, bodyTop, qrTop, noteTop (percent numbers).
Leave unfixable blockers OUT of overrides (note them as issues with fixable=false).

Critical judgment calls:
- A subject correctly BLED FLUSH to the edge it is cropped at is GOOD — do NOT flag it as a tangent
  or as "touching the edge". Only flag a figure that FLOATS with a gap of background on its cut side
  (fix: heroAnchorY to that edge).
- A deliberately type-only frame has no photographic hero — don't demand one.
- Don't invent problems. If the frame is clean, pass it with an empty overrides object.

Set format to "${fmt}". pass = true ONLY if there is no blocker and no major issue.`
}

const fmts = CFG.formats.slice()
const history = {}
let remaining = fmts.slice()
let round = 0

while (remaining.length && round < CFG.maxRounds) {
  round++
  phase('Review')
  log(`round ${round}: rendering + reviewing ${remaining.join(', ')}`)
  // 1) render the formats still under review, with whatever overrides exist so far
  await agent(
    `Run exactly this command with the Bash tool and report only success/failure + any stderr:\n` +
    `${CFG.venv} ${CFG.scripts}/recompose.py ${CFG.project} --only ${remaining.join(',')} --overrides ${CFG.project}/overrides.json`,
    { label: `render r${round}`, phase: 'Review' }
  )
  // 2) one fresh-eyes reviewer per format, in parallel
  const reviews = (await parallel(remaining.map(fmt => () =>
    agent(reviewerPrompt(fmt), { label: `review:${fmt}`, phase: 'Review', schema: VERDICT_SCHEMA })
  ))).filter(Boolean)

  const stillBad = []
  for (const v of reviews) {
    ;(history[v.format] = history[v.format] || []).push(v)
    const hardLeft = v.issues.some(i => (i.severity === 'blocker' || i.severity === 'major'))
    const hasPatch = v.overrides && Object.keys(v.overrides).length > 0
    if ((!v.pass || hardLeft) && hasPatch) stillBad.push(v)
    else if (!v.pass || hardLeft) log(`${v.format}: unresolved (no override can fix) — ${v.summary}`)
    else log(`${v.format}: PASS — ${v.summary}`)
  }
  if (!stillBad.length) break

  // 3) merge the override patches and loop
  phase('Fix')
  const patch = {}
  stillBad.forEach(v => { patch[v.format] = v.overrides })
  await agent(
    `Update ${CFG.project}/overrides.json. Read it first (it may not exist — then start from {}). ` +
    `Deep-merge these per-format override patches into it (new values win, keep existing keys), then Write the file back. ` +
    `Patches:\n${JSON.stringify(patch, null, 2)}\nConfirm the final JSON.`,
    { label: `apply r${round}`, phase: 'Fix' }
  )
  remaining = stillBad.map(v => v.format)
}

return {
  rounds: round,
  results: fmts.map(f => {
    const last = (history[f] || []).slice(-1)[0] || null
    return {
      format: f,
      passed: last ? last.pass : null,
      remainingIssues: last ? last.issues.filter(i => i.severity !== 'minor') : null,
      summary: last ? last.summary : 'not reviewed',
    }
  }),
}
