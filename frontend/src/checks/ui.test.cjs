const assert = require('node:assert/strict')
const test = require('node:test')
const fs = require('node:fs')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

// Use the installed compiler for small component regressions; no browser/test
// dependency is required and no application database or provider is contacted.
for (const extension of ['.ts', '.tsx']) require.extensions[extension] = (module, filename) => {
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText, filename)
}
const storage = new Map()
global.sessionStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) }
const { draftKey, pendingKey, readStored, writeStored, savedPending, safeResourceUrl, supportLabel } = require('../lib/sessionDrafts.ts')
const { PresetDiagramView } = require('../components/PresetDiagramView.tsx')
const { MessageContent } = require('../components/MessageContent.tsx')
const { ReportView, AttemptView } = require('../components/ReportView.tsx')
const { StageProgressBar } = require('../components/StageProgressBar.tsx')
const { SessionTranscript } = require('../components/SessionTranscript.tsx')
const { DiagnosticFeedback } = require('../components/DiagnosticFeedback.tsx')
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props))

test('practice, reply and original-case revision drafts survive independently', () => {
  storage.clear()
  writeStored(draftKey('session-a', 'original', 'submit_answer'), { text: 'revision' })
  writeStored(draftKey('session-a', 'practice', 'submit_practice'), { text: 'practice', diagram: { selected_repair: 'archive' } })
  writeStored(draftKey('session-a', 'original', 'answer_probe'), { text: 'reply' })
  assert.equal(readStored(draftKey('session-a', 'original', 'submit_answer')).text, 'revision')
  assert.equal(readStored(draftKey('session-a', 'practice', 'submit_practice')).diagram.selected_repair, 'archive')
  assert.equal(readStored(draftKey('session-b', 'original', 'submit_answer')), null)
  assert.equal(readStored(draftKey('session-a', 'original', 'answer_probe')).text, 'reply')
})

test('unavailable baseline assessment never labels the learner wrong or assigns zero percent', () => {
  const attempt = { id: 'failed', stage: 'diagnostic', criteria: [{ criterion: 'Explains storage', rating: 'technical_failure', met: null, status: 'provisional' }] }
  const html = render(DiagnosticFeedback, { attempts: [attempt], conceptSlug: 'storage-persistence' })
  assert.match(html, /Could not be assessed/)
  assert.doesNotMatch(html, /0%|You missed some key concepts|None of the core criteria|All prepared criteria were satisfied/)
})

test('baseline feedback distinguishes partial, omitted and ambiguous evidence', () => {
  const attempt = { stage: 'diagnostic', criteria: [
    { criterion: 'Some reasoning', rating: 'partially_demonstrated', met: false },
    { criterion: 'Unstated step', rating: 'not_addressed', met: false },
    { criterion: 'Ambiguous wording', rating: 'ambiguous_needs_clarification', met: null },
  ] }
  const html = render(DiagnosticFeedback, { attempts: [attempt] })
  for (const label of ['Partially demonstrated', 'Not addressed', 'Needs clarification']) assert.ok(html.includes(label))
  assert.doesNotMatch(html, /0%|You missed|What You Got Right/)
})

test('report separates stage evidence even when legacy score fields claim growth', () => {
  const html = render(ReportView, { report: { session_id: 'one', concept_title: 'Storage', stage: 'completed', outcome: 'inconclusive', gaps: [], attempts: [], interventions_used: [], assessment_status: 'provisional', final_score: 100, initial_score: 0, score_change: 100, score_summary: '100% growth', stage_summaries: [
    { stage: 'baseline', status: 'assessed', met_count: 0, total_count: 1, percentage: 0, uncertain_count: 0, unavailable_count: 0, support_levels: ['independent'] },
    { stage: 'revision', status: 'assessed', met_count: 1, total_count: 1, percentage: 100, uncertain_count: 0, unavailable_count: 0, support_levels: ['after_teaching'] },
    { stage: 'transfer', status: 'not_assessed', met_count: 0, total_count: 0, percentage: null, uncertain_count: 0, unavailable_count: 0, support_levels: [] },
  ] }, onBack: () => {} })
  assert.match(html, /Baseline evidence/)
  assert.match(html, /Revision after support/)
  assert.match(html, /Unfamiliar case evidence/)
  assert.match(html, /Not assessed/)
  assert.doesNotMatch(html, /Concept Understanding|growth/i)
})

test('tracked guides save the opening before navigating and close an empty tab if saving fails', async () => {
  const { openTrackedResource } = require('../lib/trackedResources.ts')
  const events = []
  const tab = { opener: {}, location: { replace: url => events.push(['navigate', url]) }, close: () => events.push(['close']) }
  const host = { open: () => { events.push(['blank']); return tab }, location: { assign: url => events.push(['fallback', url]) } }
  assert.equal(await openTrackedResource('/v1/resources/storage-persistence', async () => { events.push(['save']); return true }, host), true)
  assert.deepEqual(events.map(e => e[0]), ['blank', 'save', 'navigate'])
  assert.equal(tab.opener, null)
  events.length = 0
  assert.equal(await openTrackedResource('/v1/resources/storage-persistence', async () => false, host), false)
  assert.deepEqual(events.map(e => e[0]), ['blank', 'close'])
  events.length = 0
  assert.equal(await openTrackedResource('/v1/resources/storage-persistence', async () => { throw Error('offline') }, host), false)
  assert.deepEqual(events.map(e => e[0]), ['blank', 'close'])
})

test('in-session guide and conversation links use tracked controls instead of unrecorded anchors', () => {
  const onOpenResource = async () => true
  const html = render(DiagnosticFeedback, { attempts: [{ stage: 'diagnostic', criteria: [] }], conceptSlug: 'storage-persistence', onOpenResource })
  assert.doesNotMatch(html, /<a[^>]*href="\/v1\/resources/)
  const conversation = render(SessionTranscript, { stage: 'investigate', messages: [{ id: 'guide', role: 'tutor', content: '[Guide](/v1/resources/storage-persistence)' }], onOpenResource })
  assert.doesNotMatch(conversation, /<a[^>]*href="\/v1\/resources/)
  assert.match(conversation, /<button/)
})

test('pending retry restores the exact action, request identifier and submitted body', () => {
  const request = { client_turn_id: 'exact-id', expected_version: 4, prompt_id: 'case-1', action: 'clarify', text: 'Was saving completed?', input_mode: 'typed' }
  writeStored(pendingKey('session-a'), request)
  assert.deepEqual(savedPending('session-a'), request)
  assert.equal(savedPending('other-session'), null)
})

test('diagram repair follows arbitrary authored targets without claiming correctness', () => {
  const diagram = { diagram_id: 'generic', title: 'Archive flow', task_instruction: 'Select a target', interaction_type: 'repair',
    nodes: [{ id: 'writer', label: 'Writer', x: 10, y: 30, type: 'process' }, { id: 'temp', label: 'Temporary', x: 300, y: 20, type: 'volatile' }, { id: 'archive-node', label: 'Archive', x: 300, y: 110, type: 'persistent' }],
    edges: [{ id: 'write', from: 'writer', to: 'temp', label: 'save', status: 'needs_repair' }], repair_options: [{ id: 'choose-archive', label: 'Archive destination', target_node: 'archive-node' }] }
  const html = render(PresetDiagramView, { diagram, value: { repair_selection: 'choose-archive' } })
  assert.match(html, /selected: Archive/)
  assert.match(html, /x2="295" y2="125"/)
  assert.match(html, /aria-pressed="true"/)
  assert.doesNotMatch(html, /opt_disk|redirected to disk/)
  assert.match(render(PresetDiagramView, { diagram, value: { selected_repair: 'choose-archive' } }), /selected: Archive/)
})

test('resource markdown permits curated links and keeps injected markup inert', () => {
  assert.equal(safeResourceUrl('javascript:alert(1)'), null)
  assert.equal(safeResourceUrl('https://example.com/unreviewed'), null)
  assert.equal(safeResourceUrl('//evil.example/path'), null)
  const html = render(MessageContent, { content: '[Read](/v1/resources/storage-persistence) [Bad](javascript:alert)\n<script>bad()</script>\n```text\n[RAM] -> [Disk]\n```' })
  assert.match(html, /href="\/v1\/resources\/storage-persistence"/)
  assert.doesNotMatch(html, /href="javascript:/)
  assert.match(html, /&lt;script&gt;/)
  assert.match(html, /<pre[^>]*><code>\[RAM\] -&gt; \[Disk\]/)
})

test('diagram completion restores each canonical blank independently', () => {
  const diagram = { diagram_id: 'two-blanks', title: 'Two steps', task_instruction: 'Complete both', interaction_type: 'completion', nodes: [{ id: 'step-a', label: 'First?', x: 10, y: 20, type: 'blank' }, { id: 'step-b', label: 'Second?', x: 300, y: 20, type: 'blank' }], edges: [], blanks: [{ id: 'step-a', prompt: 'First step', options: ['Write', 'Wait'] }, { id: 'step-b', prompt: 'Second step', options: ['Reload', 'Forget'] }] }
  const html = render(PresetDiagramView, { diagram, value: { blanks: { 'step-a': 'Write', 'step-b': 'Reload' } } })
  assert.match(html, />Write<\/text>/)
  assert.match(html, />Reload<\/text>/)
  assert.equal((html.match(/aria-pressed="true"/g) || []).length, 2)
})

test('report renders matched evidence, support and earlier sessions without mastery scores', () => {
  const comparison = { skill_id: 'memory', label: 'Memory lifetime', baseline: [{ attempt_id: 'baseline-one', criterion: 'Explains lifetime', rating: 'partially_demonstrated', met: false, evidence: 'Original exact text', support_level: 'independent' }], revision: [{ attempt_id: 'revision-one', criterion: 'Explains lifetime', rating: 'demonstrated', met: true, evidence: 'Revision text', support_level: 'after_teaching' }], transfer: [], change_summary: 'Revision adds the mechanism; independent transfer is unassessed.', review_status: 'provisional' }
  const html = render(ReportView, { report: { session_id: 'one', concept_title: 'Storage', stage: 'completed', outcome: 'inconclusive', outcome_reason: 'Partial session', gaps: [], attempts: [], interventions_used: [{ id: 'help', type: 'teaching', title: 'Memory explanation', opened: false, completed: true }], assessment_status: 'provisional', skill_comparisons: [comparison], previous_sessions: [{ session_id: 'previous', created_at: '2026-10-17T12:00:00Z', outcome: 'inconclusive', skill_comparisons: [comparison] }] }, onBack: () => {} })
  assert.match(html, /href="#attempt-baseline-one"/)
  assert.match(html, /After teaching/)
  assert.match(html, /No fresh case was submitted/)
  assert.match(html, /Earlier sessions for this concept/)
  assert.match(html, /Original exact text/)
  assert.doesNotMatch(html, /mastery percentage|100%|score:/i)
})

test('skipped investigation is labelled unattempted instead of ticked complete', () => {
  const html = render(StageProgressBar, { currentStage: 'completed', recordedStages: ['diagnostic', 'apply'] })
  assert.match(html, /Not attempted/)
  assert.equal((html.match(/stage-dot done/g) || []).length, 3)
})

test('technical failures offer reassessment without turning missing historical support into independent work', () => {
  const attempt = { id: 'legacy', stage: 'diagnostic', case_type: 'baseline', scenario_text: 'Original case', answer_text: 'Saved answer', support_level: 'legacy_unknown', provenance_warning: 'Historical case snapshot unavailable.', criteria: [{ criterion: 'Explains memory', rating: 'technical_failure', met: null, status: 'provisional' }] }
  const html = render(ReportView, { report: { session_id: 'one', concept_title: 'Storage', stage: 'completed', outcome: 'inconclusive', outcome_reason: 'Provider failed', gaps: [], attempts: [attempt], interventions_used: [], assessment_status: 'provisional' }, onBack: () => {}, onRetryAssessments: () => {} })
  assert.match(html, /Retry unavailable assessments/)
  assert.match(html, /Historical case snapshot unavailable/)
  assert.match(html, /Historical support not recorded/)
  assert.equal(supportLabel(undefined), 'Support not recorded')
  assert.doesNotMatch(render(AttemptView, { attempt }), /Independent response/)
})

test('completed and legacy report stages retain a closed, safe saved conversation', () => {
  const messages = [{ id: 'help-1', role: 'tutor', stage: 'investigate', content: 'Earlier help [Read](/v1/resources/storage-persistence)\n```text\n[RAM] -> [Disk]\n```', provider_status: 'error' }, { id: 'correction-1', role: 'learner', stage: 'investigate', content: 'You misread my original answer.' }]
  for (const stage of ['completed', 'review']) {
    const html = render(SessionTranscript, { stage, messages })
    assert.match(html, /<details class="saved-transcript earlier-session"><summary>Saved tutoring and clarification conversation/)
    assert.doesNotMatch(html, /<details[^>]*\sopen/)
    assert.match(html, /Earlier help/)
    assert.match(html, /You misread my original answer/)
    assert.match(html, /AI provider request failed/)
    assert.match(html, /href="\/v1\/resources\/storage-persistence"/)
    assert.match(html, /<pre[^>]*><code>\[RAM\]/)
  }
})

test('practice attempts and deterministic selections have accurate report labels', () => {
  const attempt = { id: 'practice-one', stage: 'practice', case_type: 'guided_practice', scenario_text: 'Complete the flow', answer_text: 'Practice explanation', support_level: 'after_practice', criteria: [{ criterion: 'Selected the authored target', skill_id: 'exercise:repair', rating: 'demonstrated', met: true, status: 'provisional' }] }
  const html = render(AttemptView, { attempt })
  assert.match(html, /Guided practice/)
  assert.match(html, /Prepared selection check/)
  assert.doesNotMatch(html, /Baseline case|Provisional AI judgment/)
})

test('report body and heading theme tokens meet normal-text contrast on both surface themes', () => {
  const css = fs.readFileSync(require('node:path').join(__dirname, '../index.css'), 'utf8')
  const luminance = hex => {
    const rgb = hex.match(/[0-9a-f]{2}/gi).map(value => parseInt(value, 16) / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4)
    return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722
  }
  for (const expression of [/\[data-theme="light"\], :root\s*\{([^}]+)/, /\[data-theme="dark"\]\s*\{([^}]+)/]) {
    const block = css.match(expression)[1]
    const token = name => block.match(new RegExp(`--${name}:\\s*(#[0-9A-Fa-f]{6})`))[1]
    for (const foreground of ['text-body', 'text-primary', 'text-secondary']) for (const background of ['bg-surface', 'bg-surface-alt', 'bg-card']) {
      const a = luminance(token(foreground)), b = luminance(token(background))
      assert.ok((Math.max(a, b) + .05) / (Math.min(a, b) + .05) >= 4.5, `${foreground} against ${background} needs readable contrast`)
    }
  }
})
