const assert = require('node:assert/strict')
const test = require('node:test')
const fs = require('node:fs')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

// Use the installed compiler for small component regressions; no browser/test
// dependency is required and no application database or provider is contacted.
for (const extension of ['.ts', '.tsx']) require.extensions[extension] = (module, filename) => {
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8').replace('import.meta.env.VITE_API_BASE_URL', 'undefined'), {
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
const { HelpMenu } = require('../components/HelpMenu.tsx')
const { AuthModal } = require('../components/AuthModal.tsx')
const { AuthPage } = require('../pages/AuthPage.tsx')
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props))


test('confirmed dictation appends to typed text and keeps all accepted clip references after reload', () => {
  const { applyDictation } = require('../lib/dictation.ts')
  const first = applyDictation({ text: 'Typed introduction.', diagram: null, cloze: null, inputMode: 'typed', transcriptionId: null }, 'Memory is temporary.', 'clip-1')
  assert.equal(first.text, 'Typed introduction.\n\nMemory is temporary.')
  const key = draftKey('voice-session', 'case', 'submit_answer')
  writeStored(key, first)
  const second = applyDictation(readStored(key), 'A saved file survives.', 'clip-2')
  assert.equal(second.text, 'Typed introduction.\n\nMemory is temporary.\n\nA saved file survives.')
  assert.deepEqual(second.transcriptionSegments.map(s => s.transcription_id), ['clip-1', 'clip-2'])
  assert.deepEqual(second.transcriptionSegments.map(s => s.confirmed_text), ['Memory is temporary.', 'A saved file survives.'])
  assert.equal(second.transcriptionId, 'clip-2')
})

test('explicit dictation replacement discards earlier active clips while append confirmation cannot duplicate a clip', () => {
  const { applyDictation } = require('../lib/dictation.ts')
  const first = applyDictation({ text: 'Original typed text', inputMode: 'typed', transcriptionId: null }, 'First clip', 'first')
  assert.equal(applyDictation(first, 'First clip', 'first').text, 'Original typed text\n\nFirst clip')
  const replacement = applyDictation(first, 'Replacement clip', 'second', 'replace')
  assert.equal(replacement.text, 'Replacement clip')
  assert.deepEqual(replacement.transcriptionSegments.map(s => s.transcription_id), ['second'])
  assert.equal(first.text, 'Original typed text\n\nFirst clip')
})

test('adding to a legacy voice draft retains its source and identifies legacy confirmation scope', () => {
  const { applyDictation } = require('../lib/dictation.ts')
  const draft = applyDictation({ text: 'Earlier voice draft plus edits', inputMode: 'voice', transcriptionId: 'old' }, 'New words', 'new')
  assert.equal(draft.text, 'Earlier voice draft plus edits\n\nNew words')
  assert.equal(draft.transcriptionSegments[0].transcription_id, 'old')
  assert.equal(draft.transcriptionSegments[0].confirmation_scope, 'legacy_draft')
})

test('dictating into a cleared answer starts a new clip set instead of retaining deleted recordings', () => {
  const { applyDictation } = require('../lib/dictation.ts')
  const cleared = { text: '', inputMode: 'voice', transcriptionId: 'deleted', transcriptionSegments: [{ transcription_id: 'deleted', confirmed_text: 'Deleted answer' }] }
  const next = applyDictation(cleared, 'Fresh answer', 'fresh')
  assert.equal(next.text, 'Fresh answer')
  assert.deepEqual(next.transcriptionSegments.map(s => s.transcription_id), ['fresh'])
})

test('reviewed transcripts offer append and explicit replacement without answer submission', () => {
  const { TranscriptReview } = require('../components/TranscriptReview.tsx')
  const html = render(TranscriptReview, { existingText: 'Keep this answer', transcript: 'New clip', rawTranscript: 'New clip', onChange: () => {}, onConfirm: () => {}, onCancel: () => {}, onRecordAgain: () => {} })
  assert.match(html, /Add to my answer/)
  assert.match(html, /Replace my answer/)
  assert.match(html, /Cancel/)
  assert.doesNotMatch(html, /type="submit"/)
})

test('clearing then retyping drops discarded clips before typed submission or further dictation', () => {
  const { applyDictation, editDraftText } = require('../lib/dictation.ts')
  const original = applyDictation({ text: '', inputMode: 'typed', transcriptionId: null }, 'Discard this clip', 'discarded')
  const cleared = editDraftText(original, '   ')
  const retyped = editDraftText(cleared, 'New typed answer')
  assert.equal(retyped.inputMode, 'typed')
  assert.equal(retyped.transcriptionId, null)
  assert.deepEqual(retyped.transcriptionSegments, [])
  const next = applyDictation(retyped, 'New addition', 'fresh')
  assert.equal(next.text, 'New typed answer\n\nNew addition')
  assert.deepEqual(next.transcriptionSegments.map(s => s.transcription_id), ['fresh'])
  assert.equal(editDraftText(original, 'Edited clip plus typed text').transcriptionId, 'discarded')
})

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

test('compact diagnostic feedback displays summary findings, next tutor question, and collapsible details with per-answer distinction', () => {
  const attempts = [
    {
      id: 'diag-1',
      stage: 'diagnostic',
      case_type: 'baseline',
      scenario_text: 'Scenario 1',
      answer_text: 'Answer 1',
      criteria: [
        { criterion: 'Explains process memory', rating: 'demonstrated', met: true },
        { criterion: 'Explains disk persistence', rating: 'partially_demonstrated', met: false },
      ],
    },
    {
      id: 'diag-2',
      stage: 'diagnostic',
      case_type: 'baseline',
      scenario_text: 'Scenario 2',
      answer_text: 'Answer 2',
      criteria: [
        { criterion: 'Explains disk persistence', rating: 'ambiguous_needs_clarification', met: null },
      ],
    },
  ]
  const html = render(DiagnosticFeedback, {
    attempts,
    nextQuestion: 'What changes when the server restarts?',
  })
  // Plain language summary
  assert.match(html, /What your diagnostic answers showed/)
  assert.match(html, /Explains process memory/)
  assert.match(html, /Explains disk persistence/)
  assert.match(html, /Next tutor question/)
  assert.match(html, /What changes when the server restarts\?/)
  // Per-answer evidence preserved in secondary accordion
  assert.match(html, /View diagnostic details \(per-answer evidence\)/)
  assert.match(html, /Partially demonstrated \(1\)/)
  assert.match(html, /Needs clarification \(1\)/)
})

test('help menu provides accessible controls without cluttering the main conversation', () => {
  const html = render(HelpMenu, {
    canTeaching: true,
    canPractice: true,
    canResource: true,
    canClarify: true,
    canCorrectAi: true,
    disabled: false,
    onSelect: () => {},
  })
  assert.match(html, /More help ▾/)
  assert.match(html, /aria-haspopup="true"/)
  assert.match(html, /aria-expanded="false"/)
})

test('report view structures findings in order A (session summary), B (skill comparison), and C (detailed evidence), supporting print modes', () => {
  const report = {
    session_id: 'report-test-1',
    concept_title: 'Storage Persistence',
    stage: 'completed',
    outcome: 'criteria_demonstrated',
    outcome_reason: 'Your unfamiliar-case answer demonstrated all three prepared criteria. Your revised answer also addressed the earlier uncertainty about exposed keys. AI assessments remain provisional.',
    assessment_status: 'provisional',
    gaps: [
      {
        id: 'gap-1',
        description: 'Possible storage uncertainty',
        evidence_quote: 'Variables vanish',
        probe_text: 'What survives?',
        status: 'identified',
        source_attempt_id: 'att-1',
        addressed_by_attempt_id: 'att-rev',
        addressed_stage: 'Revised explanation',
      },
    ],
    attempts: [
      {
        id: 'att-1',
        stage: 'diagnostic',
        case_type: 'baseline',
        scenario_text: 'Baseline case 1',
        answer_text: 'Original answer',
        support_level: 'independent',
        criteria: [
          {
            criterion: 'Key revocation',
            skill_id: 'secret_lifecycle',
            rating: 'partially_demonstrated',
            met: false,
            unprompted: true,
            unprompted_note: 'The scenario did not explicitly ask how to handle key revocation, replacement, or downloaded copies.',
          },
        ],
      },
    ],
    interventions_used: [
      { id: 'i-1', type: 'hint', title: 'Conceptual clue', opened: true, completed: true },
    ],
    skill_comparisons: [
      {
        skill_id: 'secret_lifecycle',
        label: 'Secret lifecycle',
        baseline: [{ attempt_id: 'att-1', criterion: 'Key revocation', rating: 'partially_demonstrated', met: false, support_level: 'independent' }],
        revision: [],
        transfer: [],
        change_summary: 'Baseline noted.',
      },
    ],
    session_summary: {
      unfamiliar_case_summary: 'Demonstrated all criteria independently on the unfamiliar case.',
      revised_reasoning_summary: 'Revised answer demonstrated key mechanisms after hint.',
      unresolved_summary: 'None on tested cases; AI assessments remain provisional.',
      support_summary: '1 hint',
    },
    stage_summaries: [
      { stage: 'baseline', status: 'assessed', met_count: 0, total_count: 1, percentage: 0, support_levels: ['independent'] },
      { stage: 'revision', status: 'not_assessed', met_count: 0, total_count: 0, percentage: null, support_levels: [] },
      { stage: 'transfer', status: 'assessed', met_count: 1, total_count: 1, percentage: 100, support_levels: ['independent'] },
    ],
  }
  const html = render(ReportView, { report, onBack: () => {} })

  // Verify Part A: Session Summary
  assert.match(html, /Session overview/)
  assert.match(html, /Demonstrated all criteria independently/)
  assert.match(html, /Your unfamiliar-case answer demonstrated all three prepared criteria/)

  // Verify Part B: Compact Skill Comparison
  assert.match(html, /Matched skills across cases/)
  assert.match(html, /Secret lifecycle/)

  // Verify Part C: Detailed Evidence & Appendix
  assert.match(html, /Detailed evidence &amp; appendix/)
  assert.match(html, /print-appendix/)

  // Verify Print Mode Selector
  assert.match(html, /Print \/ Export options/)
  assert.match(html, /Compact summary/)
  assert.doesNotMatch(html, /Compact summary \(1–2 pages\)/)
  assert.match(html, /Full report with appendix/)

  // Verify Unprompted criterion flag and addressed gap badge
  assert.match(html, /Not asked in prompt/)
  assert.match(html, /Addressed in later evidence/)
  assert.match(html, /Revised explanation/)
})

test('diagnostic feedback attributes criteria to specific cases (Case 1, Case 2)', () => {
  const attempts = [
    {
      id: 'att-case1',
      stage: 'diagnostic',
      case_snapshot: {
        id: 'c1',
        case_type: 'baseline_1',
        scenario_text: 'Scenario for case 1',
        rubric: {
          criteria: [
            { id: 'crit-1', skill: 'secret_lifecycle', label: 'Revoke key', prompt_quoted_text: 'Revocation' },
          ],
        },
      },
      criterion_assessments: [
        { id: 'ca-1', criterion_id: 'crit-1', met: true, rating: 'demonstrated', evidence_quote: 'Found in case 1 answer' },
      ],
    },
    {
      id: 'att-case2',
      stage: 'diagnostic',
      case_snapshot: {
        id: 'c2',
        case_type: 'baseline_2',
        scenario_text: 'Scenario for case 2',
        rubric: {
          criteria: [
            { id: 'crit-2', skill: 'blast_radius', label: 'Contain scope', prompt_quoted_text: 'Containment' },
          ],
        },
      },
      criterion_assessments: [
        { id: 'ca-2', criterion_id: 'crit-2', met: false, rating: 'partially_demonstrated', evidence_quote: 'Found in case 2 answer' },
      ],
    },
  ]

  const html = render(DiagnosticFeedback, {
    attempts,
    conceptSlug: 'security',
    conceptTitle: 'Security Foundations',
    nextQuestion: 'What steps would you take next?',
  })

  // Verify Case attribution badges
  assert.match(html, /Case 1/)
  assert.match(html, /Case 2/)
  assert.match(html, /Revoke key/)
  assert.match(html, /Contain scope/)
  assert.match(html, /Found in case 1 answer/)
  assert.match(html, /Found in case 2 answer/)
})

test('report view embeds session transcript in print appendix and marks it hidden in summary mode', () => {
  const report = {
    session_id: 's-print',
    concept_slug: 'security',
    concept_title: 'Security Foundations',
    attempts: [],
    interventions_used: [],
    skill_comparisons: [],
    session_summary: {
      unfamiliar_case_summary: '',
      revised_reasoning_summary: '',
      unresolved_summary: '',
      support_summary: '',
    },
    stage_summaries: [],
  }
  const messages = [
    { id: 'm-1', role: 'user', content: 'My first response', stage: 'diagnostic', created_at: '2026-10-19T10:00:00Z' },
    { id: 'm-2', role: 'tutor', content: 'What about rotation?', stage: 'investigate', created_at: '2026-10-19T10:01:00Z' },
  ]

  const html = render(ReportView, { report, messages, onBack: () => {} })

  // Verify print-appendix and print-hide-in-summary are attached
  assert.match(html, /print-appendix/)
  assert.match(html, /print-hide-in-summary/)
  assert.match(html, /My first response/)
  assert.match(html, /What about rotation\?/)
})

function captureButtons(Component, props) {
  const jsxRuntime = require('react/jsx-runtime')
  const buttons = []
  const origJsx = jsxRuntime.jsx
  jsxRuntime.jsx = function(type, p, _key) {
    if (type === 'button' && p && p.onClick) buttons.push({ props: p, onClick: p.onClick })
    return origJsx.apply(this, arguments)
  }
  try {
    renderToStaticMarkup(React.createElement(Component, props))
  } finally {
    jsxRuntime.jsx = origJsx
  }
  return buttons
}

test('composed guide links across diagnostic feedback, chat messages, and help menu open exactly 1 tab, 1 save event, and 1 navigation', async () => {
  const { openTrackedResource } = require('../lib/trackedResources.ts')
  const events = []
  const tab = { opener: {}, location: { replace: url => events.push(['navigate', url]) }, close: () => events.push(['close']) }
  const host = { open: () => { events.push(['blank']); return tab }, location: { assign: url => events.push(['fallback', url]) } }
  global.window = host

  const confirmResourceOpening = async (url) => {
    events.push(['save', url])
    return true
  }
  const openConceptGuide = async (url) => {
    return openTrackedResource(url, () => confirmResourceOpening(url), host)
  }

  // 1. DiagnosticFeedback reference-guide button
  events.length = 0
  const diagButtons = captureButtons(DiagnosticFeedback, {
    attempts: [{ stage: 'diagnostic', criteria: [{ criterion: 'Storage', rating: 'demonstrated', met: true }] }],
    conceptSlug: 'storage-persistence',
    conceptTitle: 'Storage',
    onOpenResource: confirmResourceOpening,
  })
  assert.equal(diagButtons.length, 1)
  await diagButtons[0].onClick()
  assert.deepEqual(events, [
    ['blank'],
    ['save', '/v1/resources/storage-persistence'],
    ['navigate', '/v1/resources/storage-persistence'],
  ])

  // 2. Guide link in tutor message (SessionTranscript)
  events.length = 0
  const transcriptButtons = captureButtons(SessionTranscript, {
    stage: 'investigate',
    messages: [{ id: 'tutor-msg-1', role: 'tutor', content: 'Review the [Storage Guide](/v1/resources/storage-persistence)' }],
    onOpenResource: confirmResourceOpening,
  })
  assert.equal(transcriptButtons.length, 1)
  await transcriptButtons[0].onClick()
  assert.deepEqual(events, [
    ['blank'],
    ['save', '/v1/resources/storage-persistence'],
    ['navigate', '/v1/resources/storage-persistence'],
  ])

  // 3. More help -> Open concept guide (HelpMenu direct caller)
  events.length = 0
  const guideSuccess = await openConceptGuide('/v1/resources/storage-persistence')
  assert.equal(guideSuccess, true)
  assert.deepEqual(events, [
    ['blank'],
    ['save', '/v1/resources/storage-persistence'],
    ['navigate', '/v1/resources/storage-persistence'],
  ])
})

test('guide opening failure prevents navigation and closes reserved tab across all entry points', async () => {
  const { openTrackedResource } = require('../lib/trackedResources.ts')
  const events = []
  const tab = { opener: {}, location: { replace: url => events.push(['navigate', url]) }, close: () => events.push(['close']) }
  const host = { open: () => { events.push(['blank']); return tab }, location: { assign: url => events.push(['fallback', url]) } }
  global.window = host

  const failingConfirm = async (url) => {
    events.push(['save', url])
    return false
  }
  const openConceptGuide = async (url) => {
    return openTrackedResource(url, () => failingConfirm(url), host)
  }

  // 1. DiagnosticFeedback fails to save
  events.length = 0
  const diagButtons = captureButtons(DiagnosticFeedback, {
    attempts: [{ stage: 'diagnostic', criteria: [{ criterion: 'Storage', rating: 'demonstrated', met: true }] }],
    conceptSlug: 'storage-persistence',
    onOpenResource: failingConfirm,
  })
  await diagButtons[0].onClick()
  assert.deepEqual(events, [
    ['blank'],
    ['save', '/v1/resources/storage-persistence'],
    ['close'],
  ])

  // 2. SessionTranscript fails to save
  events.length = 0
  const transcriptButtons = captureButtons(SessionTranscript, {
    stage: 'investigate',
    messages: [{ id: 'tutor-msg-2', role: 'tutor', content: 'Review the [Storage Guide](/v1/resources/storage-persistence)' }],
    onOpenResource: failingConfirm,
  })
  await transcriptButtons[0].onClick()
  assert.deepEqual(events, [
    ['blank'],
    ['save', '/v1/resources/storage-persistence'],
    ['close'],
  ])

  // 3. Direct HelpMenu openConceptGuide fails to save
  events.length = 0
  const result = await openConceptGuide('/v1/resources/storage-persistence')
  assert.equal(result, false)
  assert.deepEqual(events, [
    ['blank'],
    ['save', '/v1/resources/storage-persistence'],
    ['close'],
  ])
})

test('regression: double-wrapping openTrackedResource reproduces double tabs and is prevented by confirmResourceOpening', async () => {
  const { openTrackedResource } = require('../lib/trackedResources.ts')
  const events = []
  const tab = { opener: {}, location: { replace: url => events.push(['navigate', url]) }, close: () => events.push(['close']) }
  const host = { open: () => { events.push(['blank']); return tab }, location: { assign: url => events.push(['fallback', url]) } }
  global.window = host

  // Buggy implementation: onOpenResource called openTrackedResource, creating a nested tab
  const buggyNestedOpener = async (url) => {
    return openTrackedResource(url, async () => { events.push(['save', url]); return true }, host)
  }
  events.length = 0
  const buggyButtons = captureButtons(DiagnosticFeedback, {
    attempts: [{ stage: 'diagnostic', criteria: [{ criterion: 'Storage', rating: 'demonstrated', met: true }] }],
    conceptSlug: 'storage-persistence',
    onOpenResource: buggyNestedOpener,
  })
  await buggyButtons[0].onClick()
  // Buggy nested call produced 2 blank tabs, 1 save, 2 navigations
  assert.deepEqual(events, [
    ['blank'],
    ['blank'],
    ['save', '/v1/resources/storage-persistence'],
    ['navigate', '/v1/resources/storage-persistence'],
    ['navigate', '/v1/resources/storage-persistence'],
  ])

  // Fixed implementation: onOpenResource is confirmResourceOpening, producing exactly 1 tab and 1 navigation
  events.length = 0
  const fixedConfirm = async (url) => {
    events.push(['save', url])
    return true
  }
  const fixedButtons = captureButtons(DiagnosticFeedback, {
    attempts: [{ stage: 'diagnostic', criteria: [{ criterion: 'Storage', rating: 'demonstrated', met: true }] }],
    conceptSlug: 'storage-persistence',
    onOpenResource: fixedConfirm,
  })
  await fixedButtons[0].onClick()
  assert.deepEqual(events, [
    ['blank'],
    ['save', '/v1/resources/storage-persistence'],
    ['navigate', '/v1/resources/storage-persistence'],
  ])
})

test('auth modal renders sign in and registration forms with accessible tablist', () => {
  const html = render(AuthModal, { isOpen: true, onClose: () => {}, onAuthSuccess: () => {} })
  assert.match(html, /Sign In to Concept Check/)
  assert.match(html, /role="tablist"/)
  assert.match(html, /Sign In/)
  assert.match(html, /Create Account/)
  assert.match(html, /Email Address/)
  assert.match(html, /Password/)
  assert.match(html, /Sign In →/)
})

test('auth page renders first-touch login and sign-up card with tabs and credentials form', () => {
  const html = render(AuthPage, { onAuthSuccess: () => {} })
  assert.match(html, /Sign In to Continue/)
  assert.match(html, /role="tablist"/)
  assert.match(html, /Sign In/)
  assert.match(html, /Create Account/)
  assert.match(html, /auth-page-card/)
  assert.match(html, /Email Address/)
  assert.match(html, /Password/)
  assert.match(html, /Sign In →/)
  assert.match(html, /Create one now/)
})

// Execute App's hooks and events without a browser or a real API. Child screens
// stay unmounted; the real App decides which identity/session may reach them.
function appHarness(api, entries = []) {
  const Module = require('node:module')
  const values = new Map(entries)
  const listeners = new Map()
  const oldStorage = global.localStorage
  const oldWindow = global.window
  global.localStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
  global.window = {
    addEventListener: (name, handler) => { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name).add(handler) },
    removeEventListener: (name, handler) => listeners.get(name)?.delete(handler),
    dispatchEvent: event => { for (const handler of listeners.get(event.type) || []) handler(event) },
  }
  const slots = []
  const pendingEffects = []
  let cursor = 0
  let dirty = true
  let tree
  const same = (a, b) => a && b && a.length === b.length && a.every((value, i) => Object.is(value, b[i]))
  const hooks = {
    useState(initial) { const i = cursor++; if (!slots[i]) slots[i] = { value: typeof initial === 'function' ? initial() : initial }; return [slots[i].value, value => { slots[i].value = typeof value === 'function' ? value(slots[i].value) : value; dirty = true }] },
    useRef(initial) { const i = cursor++; if (!slots[i]) slots[i] = { current: initial }; return slots[i] },
    useCallback(fn, deps) { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: fn }; return slots[i].value },
    useEffect(fn, deps) { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) { const previous = slots[i]; slots[i] = { deps }; pendingEffects.push(() => { previous?.cleanup?.(); slots[i].cleanup = fn() }) } },
  }
  const child = name => ({ [name]: function Screen() {} })
  const filename = require.resolve('../App.tsx')
  const compiled = new Module(filename, module)
  compiled.filename = filename
  compiled.paths = module.paths
  compiled.require = id => id === 'react' ? hooks : id === './api/client' ? { api, AUTH_REQUIRED_EVENT: 'cc:auth-required' }
    : id.endsWith('.css') ? {} : id.startsWith('./pages/') || id.startsWith('./components/') ? child(id.split('/').at(-1)) : require(id)
  compiled._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } }).outputText, filename)
  const renderApp = () => { cursor = 0; dirty = false; tree = compiled.exports.App(); while (pendingEffects.length) pendingEffects.shift()() }
  const find = predicate => {
    const visit = node => { if (!node || typeof node !== 'object') return; if (predicate(node)) return node; for (const child of React.Children.toArray(node.props?.children)) { const found = visit(child); if (found) return found } }
    return visit(tree)
  }
  return {
    values, find,
    event: event => global.window.dispatchEvent(event),
    async flush() { for (let i = 0; i < 20; i++) { if (dirty) renderApp(); await new Promise(resolve => setImmediate(resolve)); if (!dirty) return } throw new Error('App did not settle') },
    close() { for (const slot of slots) slot?.cleanup?.(); global.localStorage = oldStorage; global.window = oldWindow },
  }
}

const userA = { id: 'account-a', email: 'a@example.test', full_name: 'Learner A' }
const userB = { id: 'account-b', email: 'b@example.test', full_name: 'Learner B' }

test('authenticated refresh restores the selected session after identity verification', async () => {
  const app = appHarness({ getHealth: async () => ({}), getMe: async () => ({ authenticated: true, user: userA }) }, [
    ['cc_active_session_id', 'session-a'], ['cc_active_view', 'session'], ['cc_active_session_owner', userA.id],
  ])
  try {
    await app.flush()
    assert.equal(app.find(node => node.props?.sessionId === 'session-a')?.props.sessionId, 'session-a')
    assert.equal(app.values.get('cc_active_session_id'), 'session-a')
  } finally { app.close() }
})

test('a token change in another tab clears the previous account screen and session', async () => {
  let user = userA
  const app = appHarness({ getHealth: async () => ({}), getMe: async () => ({ authenticated: true, user }) }, [
    ['cc_auth_token', 'token-a'], ['cc_active_session_id', 'session-a'], ['cc_active_view', 'session'], ['cc_active_session_owner', userA.id],
  ])
  try {
    await app.flush()
    user = userB
    app.values.set('cc_auth_token', 'token-b')
    app.event({ type: 'storage', key: 'cc_auth_token', newValue: 'token-b' })
    await app.flush()
    assert.equal(app.find(node => node.props?.sessionId === 'session-a'), undefined)
    assert.equal(app.find(node => node.props?.title === `Signed in as ${userB.email}`)?.props.title, `Signed in as ${userB.email}`)
    assert.equal(app.find(node => node.props?.title === `Signed in as ${userA.email}`), undefined)
  } finally { app.close() }
})

test('an expired session gates saved learner content and offers sign-in again', async () => {
  const app = appHarness({ getHealth: async () => ({}), getMe: async () => ({ authenticated: true, user: userA }) }, [
    ['cc_active_session_id', 'session-a'], ['cc_active_view', 'session'], ['cc_active_session_owner', userA.id],
  ])
  try {
    await app.flush()
    app.event({ type: 'cc:auth-required' })
    await app.flush()
    assert.equal(app.find(node => node.props?.sessionId), undefined)
    assert.ok(app.find(node => node.props?.onAuthSuccess))
    assert.ok(app.find(node => node.props?.role === 'alert'))
  } finally { app.close() }
})

test('failed sign-out preserves the authenticated screen and reports the failure', async () => {
  const app = appHarness({ getHealth: async () => ({}), getMe: async () => ({ authenticated: true, user: userA }), logout: async () => { throw new Error('Offline') } })
  try {
    await app.flush()
    await assert.doesNotReject(app.find(node => node.props?.title === 'Sign out of your account').props.onClick())
    await app.flush()
    assert.ok(app.find(node => node.props?.title === `Signed in as ${userA.email}`))
    assert.ok(app.find(node => node.props?.role === 'alert'))
  } finally { app.close() }
})

function loadApiClient() {
  const Module = require('node:module')
  const filename = require.resolve('../api/client.ts')
  const compiled = new Module(filename, module)
  compiled.filename = filename
  compiled.paths = module.paths
  compiled._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8').replace('import.meta.env.VITE_API_BASE_URL', 'undefined'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename)
  return compiled.exports
}

test('voice uploads carry the same bearer identity as ordinary API requests', async () => {
  const previous = { fetch: global.fetch, localStorage: global.localStorage, window: global.window }
  global.localStorage = { getItem: () => 'learner-token' }
  global.window = { location: { hostname: 'example.vercel.app' } }
  let uploaded
  global.fetch = async (url, options) => { uploaded = { url, options }; return { ok: true, json: async () => ({ id: 'clip' }) } }
  try {
    await loadApiClient().api.uploadTranscription('session-a', new Blob(['fictional audio']))
    assert.equal(uploaded.url, '/v1/sessions/session-a/transcriptions')
    assert.equal(uploaded.options.headers?.Authorization, 'Bearer learner-token')
    assert.equal(uploaded.options.credentials, 'include')
  } finally { Object.assign(global, previous) }
})

test('API authentication failure signals reauthentication but a wrong password does not', async () => {
  const previous = { fetch: global.fetch, localStorage: global.localStorage, window: global.window }
  const events = []
  const values = new Map([['cc_auth_token', 'expired-token']])
  global.localStorage = { getItem: key => values.get(key), removeItem: key => values.delete(key) }
  global.window = { location: { hostname: 'example.vercel.app' }, dispatchEvent: event => events.push(event.type) }
  global.fetch = async () => ({ ok: false, status: 401, statusText: 'Unauthorized', json: async () => ({ detail: 'Sign in required' }) })
  try {
    const { api } = loadApiClient()
    await assert.rejects(api.getSession('session-a'), /Sign in required/)
    assert.deepEqual(events, ['cc:auth-required'])
    await assert.rejects(api.login({ email: 'a@example.test', password: 'wrong-password' }), /Sign in required/)
    assert.equal(events.length, 1)
  } finally { Object.assign(global, previous) }
})

test('diagnostic and report preserve required-part coverage, omissions and useful feedback', () => {
  const attempt = { id: 'parts', stage: 'diagnostic', case_type: 'baseline', scenario_text: 'Explain saving and recovery.', answer_text: 'I save to a file.', support_level: 'independent', question_parts: [
    { part_id: 'save', description: 'Explain saving the answer' }, { part_id: 'recover', description: 'Explain restart recovery' }, { part_id: 'read', description: 'Explain retrieval after restart' },
  ], question_parts_coverage: [
    { question_part_id: 'save', coverage: 'partly_answered', demonstrated_explanation: 'You identified a durable file.', explanation: 'The write timing is not explained.', next_action: 'Explain when the write completes.', evidence: 'I save to a file.' },
    { question_part_id: 'recover', coverage: 'unanswered', issue_type: 'missing_requested_part', explanation: 'You did not answer the part asking about recovery.', next_action: 'Explain how startup retrieves the saved answer.', evidence: '' },
  ], criteria: [{ criterion: 'Explains durable saving', rating: 'partially_demonstrated', met: false, status: 'provisional', question_part_id: 'save', demonstrated_explanation: 'The destination is durable.', explanation: 'Missing write timing.', next_action: 'State when the write is acknowledged.' }] }
  for (const html of [render(DiagnosticFeedback, { attempts: [attempt] }), render(AttemptView, { attempt })]) {
    for (const text of ['Explain saving the answer', 'Explain restart recovery', 'Explain retrieval after restart', 'Partly answered', 'Unanswered', 'Coverage unavailable', 'You identified a durable file.', 'The write timing is not explained.', 'Explain when the write completes.', 'You did not answer the part asking about recovery.']) assert.ok(html.includes(text), `Missing learner feedback: ${text}`)
    assert.ok(html.includes('Missing write timing.'))
    assert.ok(html.includes('State when the write is acknowledged.'))
    assert.doesNotMatch(html, /“”|&quot;&quot;/)
  }
})

test('report shows requested-part coverage before its collapsed evidence appendix', () => {
  const report = { session_id: 'overview', concept_title: 'Storage', stage: 'completed', outcome: 'inconclusive', outcome_reason: 'Evidence is incomplete', gaps: [], interventions_used: [], assessment_status: 'provisional', attempts: [{
    id: 'unanswered-part', stage: 'apply', case_type: 'transfer', scenario_text: 'Explain recovery.', answer_text: 'Storage persists.', support_level: 'independent', criteria: [],
    question_parts: [{ part_id: 'recover', description: 'Explain recovering the answer after restart' }], question_parts_coverage: [{ question_part_id: 'recover', coverage: 'unanswered', issue_type: 'missing_requested_part', explanation: 'The restart part was omitted.', evidence: '' }],
  }] }
  const html = render(ReportView, { report })
  const overview = html.indexOf('Explain recovering the answer after restart')
  const appendix = html.indexOf('Detailed evidence &amp; appendix')
  assert.ok(overview >= 0 && overview < appendix)
  assert.ok(html.slice(0, appendix).includes('Unanswered'))
})

test('another account cannot restore a stored session selection from the previous account', async () => {
  const app = appHarness({ getHealth: async () => ({}), getMe: async () => ({ authenticated: true, user: userB }) }, [
    ['cc_active_session_id', 'session-a'], ['cc_active_view', 'session'], ['cc_active_session_owner', userA.id],
  ])
  try {
    await app.flush()
    assert.equal(app.find(node => node.props?.sessionId), undefined)
    assert.equal(app.values.has('cc_active_session_id'), false)
  } finally { app.close() }
})

test('failed account verification after a token change does not reveal the previous account', async () => {
  let offline = false
  const app = appHarness({ getHealth: async () => ({}), getMe: async () => { if (offline) throw new Error('Offline'); return { authenticated: true, user: userA } } })
  try {
    await app.flush()
    offline = true
    app.event({ type: 'storage', key: 'cc_auth_token', newValue: 'token-b' })
    await app.flush()
    assert.equal(app.find(node => node.props?.title === `Signed in as ${userA.email}`), undefined)
    assert.ok(app.find(node => node.props?.onAuthSuccess))
    assert.ok(app.find(node => node.props?.role === 'alert'))
  } finally { app.close() }
})

test('late session creation cannot reopen a previous account after sign-out', async () => {
  let finishCreation
  const app = appHarness({ getHealth: async () => ({}), getMe: async () => ({ authenticated: true, user: userA }), createSession: () => new Promise(resolve => { finishCreation = resolve }), logout: async () => ({ status: 'logged_out' }) })
  try {
    await app.flush()
    const creating = app.find(node => node.props?.onSelectConcept).props.onSelectConcept('concept')
    await app.find(node => node.props?.title === 'Sign out of your account').props.onClick()
    finishCreation({ id: 'old-account-session' })
    await creating
    await app.flush()
    app.find(node => node.props?.onAuthSuccess).props.onAuthSuccess(userB)
    await app.flush()
    assert.equal(app.find(node => node.props?.sessionId), undefined)
    assert.equal(app.values.has('cc_active_session_id'), false)
  } finally { app.close() }
})

test('failed logout keeps its bearer token until server cookie clearing is confirmed', async () => {
  const previous = { fetch: global.fetch, localStorage: global.localStorage, window: global.window }
  const values = new Map([['cc_auth_token', 'learner-token']])
  global.localStorage = { getItem: key => values.get(key), removeItem: key => values.delete(key) }
  global.window = { location: { hostname: 'example.vercel.app' } }
  global.fetch = async () => { throw new Error('Offline') }
  try {
    await assert.rejects(loadApiClient().api.logout(), /Offline/)
    assert.equal(values.get('cc_auth_token'), 'learner-token')
  } finally { Object.assign(global, previous) }
})

test('late unauthorized response does not erase a newer sign-in token', async () => {
  const previous = { fetch: global.fetch, localStorage: global.localStorage, window: global.window }
  const values = new Map([['cc_auth_token', 'old-token']])
  const events = []
  let finishRequest
  global.localStorage = { getItem: key => values.get(key), removeItem: key => values.delete(key) }
  global.window = { location: { hostname: 'example.vercel.app' }, dispatchEvent: event => events.push(event.type) }
  global.fetch = () => new Promise(resolve => { finishRequest = resolve })
  try {
    const pending = loadApiClient().api.getSession('old-session')
    values.set('cc_auth_token', 'new-token')
    finishRequest({ ok: false, status: 401, statusText: 'Unauthorized', json: async () => ({ detail: 'Expired' }) })
    await assert.rejects(pending, /Expired/)
    assert.equal(values.get('cc_auth_token'), 'new-token')
    assert.deepEqual(events, [])
  } finally { Object.assign(global, previous) }
})

test('partly answered omissions keep the valid quoted reasoning while fully unanswered parts do not', () => {
  const attempt = { id: 'partial-omission', stage: 'diagnostic', case_type: 'baseline', scenario_text: 'Explain persistence.', answer_text: 'It is in a file.', support_level: 'independent',
    question_parts: [{ part_id: 'persistence', description: 'Explain saving and reloading' }],
    question_parts_coverage: [{ question_part_id: 'persistence', coverage: 'partly_answered', issue_type: 'missing_requested_part', evidence: 'It is in a file.' }],
    criteria: [{ criterion: 'Explains persistence', rating: 'partially_demonstrated', met: false, status: 'provisional', question_part_id: 'persistence', coverage: 'partly_answered', issue_type: 'missing_requested_part', evidence: 'It is in a file.' }],
  }
  const diagnostic = render(DiagnosticFeedback, { attempts: [attempt] })
  const report = render(AttemptView, { attempt })
  assert.match(diagnostic, /<blockquote>It is in a file\.<\/blockquote>/)
  assert.match(diagnostic, /criterion-evidence-inline/)
  assert.match(report, /criterion-evidence-text/)
  const omitted = structuredClone(attempt)
  omitted.question_parts_coverage[0].coverage = 'unanswered'
  omitted.criteria[0].coverage = 'unanswered'
  omitted.criteria[0].rating = 'not_addressed'
  assert.doesNotMatch(render(DiagnosticFeedback, { attempts: [omitted] }), /<blockquote>|criterion-evidence-inline/)
  assert.doesNotMatch(render(AttemptView, { attempt: omitted }), /<blockquote>|criterion-evidence-text/)
})

test('a delayed sign-out response cannot clear a newer account in another tab', async () => {
  let user = userA
  let finishLogout
  const app = appHarness({ getHealth: async () => ({}), getMe: async () => ({ authenticated: true, user }), logout: () => new Promise(resolve => { finishLogout = resolve }) })
  try {
    await app.flush()
    const signingOut = app.find(node => node.props?.title === 'Sign out of your account').props.onClick()
    user = userB
    app.event({ type: 'storage', key: 'cc_auth_token', newValue: 'token-b' })
    await app.flush()
    finishLogout({ status: 'logged_out' })
    await signingOut
    await app.flush()
    assert.ok(app.find(node => node.props?.title === `Signed in as ${userB.email}`))
  } finally { app.close() }
})

test('a delayed logout keeps a newer bearer token established while it was pending', async () => {
  const previous = { fetch: global.fetch, localStorage: global.localStorage, window: global.window }
  const values = new Map([['cc_auth_token', 'old-token']])
  let finishRequest
  global.localStorage = { getItem: key => values.get(key), removeItem: key => values.delete(key) }
  global.window = { location: { hostname: 'example.vercel.app' } }
  global.fetch = () => new Promise(resolve => { finishRequest = resolve })
  try {
    const pending = loadApiClient().api.logout()
    values.set('cc_auth_token', 'new-token')
    finishRequest({ ok: true, json: async () => ({ status: 'logged_out' }) })
    await pending
    assert.equal(values.get('cc_auth_token'), 'new-token')
  } finally { Object.assign(global, previous) }
})

test('legacy provider failure details never render as learner quotations or criterion evidence', () => {
  const attempt = { id: 'provider-failure', stage: 'diagnostic', case_type: 'baseline', scenario_text: 'Explain persistence.', answer_text: 'My saved answer.', support_level: 'independent',
    question_parts: [{ part_id: 'save', description: 'Explain durable saving' }],
    question_parts_coverage: [{ question_part_id: 'save', coverage: 'unclear', issue_type: 'technical_failure', evidence: 'Provider unavailable' }],
    criteria: [{ criterion: 'Explains persistence', rating: 'technical_failure', met: null, status: 'provisional', evidence: 'Provider unavailable' }],
  }
  for (const html of [render(DiagnosticFeedback, { attempts: [attempt] }), render(AttemptView, { attempt })]) {
    assert.doesNotMatch(html, /<blockquote>|criterion-evidence-inline|criterion-evidence-text/)
    assert.ok(html.includes('Coverage unavailable'))
  }
})

