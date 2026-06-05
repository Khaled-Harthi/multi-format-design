/*
 * design-adapt-iterate — Think -> Plan -> Act -> Iterate for layered re-adaptation.
 *
 * Runs a planner agent (analyze the real layers + negative space, decide placement)
 * then a render -> fresh-eyes critic loop that adjusts recompose.py overrides until
 * each format looks human-designed (no text over the product, balanced, natural).
 *
 * HOW TO RUN (from the agent using this skill):
 *   1. Decompose first so layers.json + assets/layers/ exist:
 *        PY scripts/decompose.py <design> <project>
 *   2. EDIT the four constants below for this run (args injection is unreliable in
 *      the workflow sandbox, so inline them).
 *   3. Invoke the Workflow tool with {scriptPath: ".../workflows/adapt-iterate.js"}.
 *   4. When it returns, write result.mergedOverrides to <project>/overrides.json and
 *        PY scripts/recompose.py <project> --overrides <project>/overrides.json
 */

// ---- EDIT THESE FOUR FOR YOUR RUN ----
const project = "/ABSOLUTE/path/to/project"     // holds layers.json + assets/layers/
const venv    = "/ABSOLUTE/path/to/.venv/bin/python"
const scripts = "/ABSOLUTE/path/to/skill/scripts"
const formats = [                                // any subset from formats.json
  { key:"billboard_48sheet", w:2400, h:1200, label:"Outdoor Billboard" },
  { key:"instagram_story",   w:1080, h:1920, label:"Instagram Story" },
]
// subject side + text direction are read from layers.json by the agents themselves.
// --------------------------------------

export const meta = {
  name: 'design-adapt-iterate',
  description: 'Plan the placement of preserved layers, render, then critique-and-iterate until each format looks human-made.',
  phases: [{ title: 'Plan' }, { title: 'Iterate' }],
}

const OV = { type:'object', additionalProperties:false, properties:{
  side:{type:'string',enum:['top','left','right']}, topPct:{type:'number'}, widthPct:{type:'number'},
  scale:{type:'number'}, gapPct:{type:'number'}, marginPct:{type:'number'},
  framePos:{type:'string',enum:['left','right','center']}, photoWidthPct:{type:'number'},
  decorScale:{type:'number'}, decorOpacity:{type:'number'}, hideDecor:{type:'boolean'} }, required:[] }
const PLAN = { type:'object', additionalProperties:false, properties:{ rationale:{type:'string'}, overrides:OV }, required:['rationale','overrides'] }
const VERDICT = { type:'object', additionalProperties:false, properties:{ ok:{type:'boolean'}, issues:{type:'array',items:{type:'string'}}, overrides:OV }, required:['ok','issues','overrides'] }

const RULES = `First read the general quality bar in ${scripts}/../references/design-principles.md and apply it. Key rules: (1) NEVER place text or the button over the product/photo's busy area or any image — use the clean empty background (negative space). (2) Generous even margins; respect platform safe zones. (3) Reading order headline -> subhead -> button. (4) Balanced, clear hierarchy, natural — would a human designer ship this? Read ${project}/layers.json for the subject side + text direction.`

const results = await parallel(formats.map(f => async () => {
  const plan = await agent(
    `Senior graphic designer. Read ${project}/layers.json and view the layer PNGs in ${project}/assets/layers/ (background = real product photo; headline/subhead/button are real). Adapt to ${f.label} (${f.w}x${f.h}). ${RULES}
Return an 'overrides' JSON: side(top|left|right), topPct, widthPct, scale, gapPct, marginPct, framePos(left|right|center), photoWidthPct, decorScale, decorOpacity, hideDecor. Text goes on the clean side OPPOSITE the product. Justify in 'rationale'.`,
    { schema: PLAN, phase: 'Plan', label: `plan:${f.key}`, agentType: 'general-purpose' })
  let ov = plan.overrides, verdict = null
  const out = `${project}/out/${f.key}.png`
  for (let i = 1; i <= 3; i++) {
    await agent(
      `Run EXACTLY:
cat > ${project}/ov_${f.key}.json <<'EOF'
{"${f.key}": ${JSON.stringify(ov)}}
EOF
${venv} ${scripts}/recompose.py ${project} --only ${f.key} --overrides ${project}/ov_${f.key}.json
Return ${out}.`,
      { phase: 'Iterate', label: `render:${f.key}#${i}`, agentType: 'general-purpose' })
    verdict = await agent(
      `Art director, fresh eyes. Read the image ${out} (${f.label} ${f.w}x${f.h}). ${RULES}
ok=true ONLY if no text/button overlaps the product/any image, margins look intentional, balanced, readable, professional. Else give 'issues' and a FULL adjusted 'overrides' JSON to fix them. Current overrides: ${JSON.stringify(ov)}.`,
      { schema: VERDICT, phase: 'Iterate', label: `critic:${f.key}#${i}`, agentType: 'general-purpose' })
    if (verdict.ok) { log(`${f.key}: approved on iteration ${i}`); break }
    log(`${f.key} iter ${i}: ${verdict.issues.join(' | ')}`)
    ov = verdict.overrides
  }
  return { format: f.key, approved: !!(verdict && verdict.ok), overrides: ov, rationale: plan.rationale, out }
}))
const merged = {}; for (const r of results.filter(Boolean)) merged[r.format] = r.overrides
return { results, mergedOverrides: merged }
