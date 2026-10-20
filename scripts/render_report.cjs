const fs = require('node:fs')
const path = require('node:path')

// Add frontend/node_modules to lookup path
module.paths.push(path.resolve(__dirname, '../frontend/node_modules'))

const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

// Transpile TypeScript and TSX files on the fly
for (const extension of ['.ts', '.tsx']) {
  require.extensions[extension] = (module, filename) => {
    module._compile(
      ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
        compilerOptions: {
          module: ts.ModuleKind.CommonJS,
          jsx: ts.JsxEmit.ReactJSX,
          target: ts.ScriptTarget.ES2022,
        },
      }).outputText,
      filename
    )
  }
}

// Mock sessionStorage for SSR
const storage = new Map()
global.sessionStorage = {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
  removeItem: key => storage.delete(key),
}

const { ReportView } = require('../frontend/src/components/ReportView.tsx')

// Representative fixture
const representativeFixture = {
  report: {
    session_id: 'session-storage-demo-01',
    concept_title: 'Storage & Persistence',
    stage: 'completed',
    outcome: 'gap_found',
    outcome_reason:
      'Your unfamiliar-case answer demonstrated its prepared criteria independently. Durable write timing improved in a supported revision but was not independently rechecked. AI assessments remain provisional until human review.',
    assessment_status: 'provisional',
    session_summary: {
      personal_summary: {
        demonstrated: 'The baseline identified volatile memory correctly; the unfamiliar case demonstrated its prepared criteria independently.',
        missing_or_incorrect: 'Initially incomplete: durable write boundary.',
        changed_after_help: 'The supported revision explained the durable write boundary.',
        needs_independent_checking: 'Retention beyond this session was not tested.',
        recommended_next_step: 'No additional remediation is indicated by the tested criteria.',
        initial_difficulties: 'Initially incomplete: durable write boundary.',
        later_evidence: 'The supported revision explained durability; the unfamiliar case provided separate independent application evidence.',
        remaining_gaps: 'Durable write timing improved with support and still needs an independent recheck.',
        assessment_notices: '',
        revision_note: 'The revision is supported evidence. Similarity to a tutor explanation does not establish independent learning.',
        next_steps: ['Try a different prepared, unseen case focused on durable write timing; explain your reasoning independently.'],
      },
      unfamiliar_case_summary:
        'Demonstrated dual-write consistency, idempotent key handling, and distributed compensation patterns independently on the object storage transfer case.',
      revised_reasoning_summary:
        'Addressed volatile memory buffering vulnerability by specifying synchronous write-ahead logging (fsync / WAL) before returning client acknowledgment.',
      unresolved_summary:
        'Durable write timing was demonstrated with support but not independently rechecked; assessments remain provisional.',
      support_summary:
        '1 hint, 1 conceptual lesson explanation, and 1 concept guide consultation used during investigation.',
    },
    stage_summaries: [
      {
        stage: 'baseline',
        status: 'assessed',
        met_count: 3,
        total_count: 4,
        percentage: 75,
        support_levels: ['independent'],
        uncertain_count: 0,
        unavailable_count: 0,
      },
      {
        stage: 'revision',
        status: 'assessed',
        met_count: 2,
        total_count: 2,
        percentage: 100,
        support_levels: ['supported'],
        uncertain_count: 0,
        unavailable_count: 0,
      },
      {
        stage: 'transfer',
        status: 'assessed',
        met_count: 2,
        total_count: 2,
        percentage: 100,
        support_levels: ['independent'],
        uncertain_count: 0,
        unavailable_count: 0,
      },
    ],
    skill_comparisons: [
      {
        skill_id: 'memory_lifetime',
        label: 'Memory lifetime',
        review_status: 'provisional',
        baseline: [
          {
            attempt_id: 'att-baseline-1',
            case_type: 'baseline',
            criterion: 'Distinguishes volatile memory lifetime from process restarts',
            rating: 'demonstrated',
            met: true,
            support_level: 'independent',
            evidence: 'Explains heap memory wiped on container restart',
          },
        ],
        revision: [],
        transfer: [],
        change_summary:
          'Baseline demonstrated that process heap memory does not survive container lifecycle restarts.',
      },
      {
        skill_id: 'durable_write_timing',
        label: 'Durable write timing',
        review_status: 'provisional',
        baseline: [
          {
            attempt_id: 'att-baseline-2',
            case_type: 'baseline',
            criterion: 'Evaluates durable persistence versus acknowledgement timing',
            rating: 'partially_demonstrated',
            met: false,
            support_level: 'independent',
            evidence:
              'Noted 45s loss but did not explain write-ahead logging or fsync commit guarantees before ACK',
          },
        ],
        revision: [
          {
            attempt_id: 'att-revised-1',
            case_type: 'revision',
            criterion: 'Evaluates durable persistence versus acknowledgement timing',
            rating: 'demonstrated',
            met: true,
            support_level: 'supported',
            evidence:
              'Explicitly identifies fsync/WAL commit boundary before returning ACK to client',
          },
        ],
        transfer: [],
        change_summary:
          'Revised reasoning addressed the durable write boundary by requiring disk-backed WAL commit before client acknowledgment.',
      },
      {
        skill_id: 'distributed_consistency',
        label: 'Distributed consistency',
        review_status: 'provisional',
        baseline: [],
        revision: [],
        transfer: [
          {
            attempt_id: 'att-transfer-1',
            case_type: 'transfer',
            criterion:
              'Identifies dual-write inconsistency between object storage and database',
            rating: 'demonstrated',
            met: true,
            support_level: 'independent',
            evidence:
              'Describes orphan database row risk if binary upload fails after DB commit',
          },
          {
            attempt_id: 'att-transfer-1',
            case_type: 'transfer',
            criterion: 'Specifies ordered execution and rollback/compensation pattern',
            rating: 'demonstrated',
            met: true,
            support_level: 'independent',
            evidence:
              'Specifies S3 idempotent upload first before DB commit, or outbox pattern with compensation',
          },
        ],
        change_summary:
          'Transfer case demonstrated independent application of durable persistence principles to distributed dual-write scenarios.',
      },
    ],
    gaps: [
      {
        id: 'gap-durable-write-1',
        description:
          'Uncertainty regarding durable write boundaries and fsync guarantees',
        evidence_quote:
          'The application gave a false sense of acknowledgement to the sensor without durable write confirmation.',
        probe_text:
          'What specific mechanism guarantees that acknowledged data survives an immediate power outage, and at what point in the request lifecycle must that occur?',
        status: 'addressed',
        source_attempt_id: 'att-baseline-2',
        addressed_by_attempt_id: 'att-revised-1',
        addressed_stage: 'Revised explanation',
      },
    ],
    attempts: [
      {
        id: 'att-baseline-1',
        stage: 'diagnostic',
        case_type: 'baseline',
        case_version: 1,
        rubric_version: 1,
        scenario_text:
          'An e-commerce order service receives a checkout request. The backend handler validates items, calculates totals, and stores the order object in an in-memory dictionary ACTIVE_ORDERS[order_id] = order_data. The server responds with HTTP 201 Created and the order ID. Five minutes later, the container restarts due to an automatic platform update. When the customer queries GET /orders/{order_id}, the server returns 404 Not Found. Explain why this happened, identify the boundary between volatile memory and durable storage, and describe what the backend should have done before responding to the checkout request.',
        answer_text:
          'The server stored the order only in a local Python dictionary in process memory. When the container restarted, the operating system terminated the Python process and wiped its heap memory, clearing the dictionary. To prevent this, the backend must write the order data durably to a database or disk-backed storage engine and confirm the write succeeded before returning the HTTP 201 Created response. The durable-write boundary is the moment the database flushes the transaction log to persistent non-volatile media.',
        support_level: 'independent',
        processing_status: 'complete',
        met_criteria_count: 2,
        total_criteria_count: 2,
        score: 100,
        criteria: [
          {
            criterion: 'Distinguishes volatile memory lifetime from process restarts',
            skill_id: 'memory_lifetime',
            rating: 'demonstrated',
            met: true,
            status: 'provisional',
            evidence: 'Explains heap memory wiped on container restart',
          },
          {
            criterion: 'Identifies write timing prior to HTTP response',
            skill_id: 'durable_write_timing',
            rating: 'demonstrated',
            met: true,
            status: 'provisional',
            evidence: 'Database write confirmed before 201 Created response',
          },
        ],
      },
      {
        id: 'att-baseline-2',
        stage: 'diagnostic',
        case_type: 'baseline',
        case_version: 1,
        rubric_version: 1,
        scenario_text:
          'A telemetry logging service receives high-throughput sensor events. To maximize ingestion speed, the developer buffers events in an internal ring buffer array in RAM and flushes them to PostgreSQL every 60 seconds. A hardware power outage occurs at second 45. What happens to the events recorded between second 0 and second 45? Contrast the guarantee of an application acknowledgment versus database durability, and evaluate whether an in-memory ring buffer meets transactional persistence requirements.',
        answer_text:
          'The events from second 0 to 45 are kept in RAM inside the ring buffer. When power is lost, volatile memory loses its contents immediately, so those 45 seconds of events are permanently lost. The application gave a false sense of acknowledgement to the sensor without durable write confirmation. An in-memory buffer cannot provide ACID durability or survive unexpected power failure without a persistent write-ahead log on non-volatile media.',
        support_level: 'independent',
        processing_status: 'complete',
        met_criteria_count: 1,
        total_criteria_count: 2,
        score: 50,
        criteria: [
          {
            criterion: 'Identifies data loss risk in unflushed application buffers',
            skill_id: 'memory_lifetime',
            rating: 'demonstrated',
            met: true,
            status: 'provisional',
            evidence: '45 seconds of buffered data lost on power cut',
          },
          {
            criterion: 'Evaluates durable persistence versus acknowledgement timing',
            skill_id: 'durable_write_timing',
            rating: 'partially_demonstrated',
            met: false,
            status: 'provisional',
            evidence:
              'Identified risk but omitted write-ahead logging (WAL) and synchronous disk flush requirements',
          },
        ],
      },
      {
        id: 'att-revised-1',
        stage: 'investigate',
        case_type: 'revision',
        case_version: 1,
        rubric_version: 1,
        scenario_text:
          'Re-evaluating the telemetry logging service: Define the exact sequence and boundaries required so that acknowledged events never suffer data loss upon power failure, stating your assumptions about hardware and transaction coordination.',
        answer_text:
          'Assumptions: Single-node server with direct-attached NVMe storage supporting synchronous fsync; client retries on network failure.\n\nRevised reasoning: To eliminate data loss, the ingestion endpoint must move the durable-write boundary before client acknowledgment. Instead of buffering in user-space RAM, each ingestion batch must be written to an append-only write-ahead log (WAL) on disk and flushed with fsync before the HTTP 200/202 acknowledgment is returned. If high throughput requires batching, group commit can be used where multiple concurrent requests are combined into a single fsync disk barrier. Buffering in volatile memory without a disk-backed WAL means the system cannot guarantee durability.',
        support_level: 'supported',
        processing_status: 'complete',
        met_criteria_count: 2,
        total_criteria_count: 2,
        score: 100,
        criteria: [
          {
            criterion: 'Evaluates durable persistence versus acknowledgement timing',
            skill_id: 'durable_write_timing',
            rating: 'demonstrated',
            met: true,
            status: 'provisional',
            evidence:
              'Positions fsync/WAL commit boundary strictly before returning client acknowledgment',
          },
          {
            criterion:
              'Distinguishes user-space memory buffering from persistent transaction logs',
            skill_id: 'durable_write_timing',
            rating: 'demonstrated',
            met: true,
            status: 'provisional',
            evidence:
              'Contrasts volatile RAM buffering with durable group-commit WAL disk barriers',
          },
        ],
      },
      {
        id: 'att-transfer-1',
        stage: 'apply',
        case_type: 'transfer',
        case_version: 1,
        rubric_version: 1,
        scenario_text:
          'A photo-sharing backend processes user image uploads via POST /upload. The service uploads the original JPEG binary to an Amazon S3 object storage bucket, and writes a metadata record (user_id, image_url, created_at) into a PostgreSQL database table. The developer implemented the database INSERT first, but the S3 upload subsequently timed out due to network disruption. How should the backend handle this failure to prevent orphan database records, and what architecture ensures consistency between external object storage and relational database metadata?',
        answer_text:
          'This scenario demonstrates a distributed dual-write consistency problem across heterogeneous storage boundaries. Because PostgreSQL and Amazon S3 cannot participate in a shared atomic ACID transaction, executing the database INSERT first causes orphan metadata records when the subsequent binary upload fails.\n\nTo ensure consistency, the backend should employ a two-phase reservation pattern: 1) Generate a client-deterministic idempotent upload key (e.g. UUIDv4 or SHA-256 hash). 2) Upload the binary to S3 first. If that fails, abort immediately without touching the database. 3) Only upon receiving HTTP 200 OK from S3, insert the database row. Alternatively, insert the metadata with status="pending" and use an outbox background worker with timeout-based cleanup to delete orphan S3 objects or rollback abandoned rows.',
        support_level: 'independent',
        processing_status: 'complete',
        met_criteria_count: 2,
        total_criteria_count: 2,
        score: 100,
        criteria: [
          {
            criterion:
              'Identifies dual-write inconsistency between object storage and database',
            skill_id: 'distributed_consistency',
            rating: 'demonstrated',
            met: true,
            status: 'provisional',
            evidence:
              'Describes orphan metadata rows arising from lack of atomic distributed transactions across S3 and SQL',
          },
          {
            criterion: 'Specifies ordered execution and rollback/compensation pattern',
            skill_id: 'distributed_consistency',
            rating: 'demonstrated',
            met: true,
            status: 'provisional',
            evidence:
              'Proposes idempotent upload first followed by DB insert, or pending status with outbox reconciliation',
          },
        ],
      },
    ],
    interventions_used: [
      {
        id: 'int-1',
        type: 'hint',
        title: 'Conceptual clue: Synchronous disk sync vs client acknowledgment',
        completed: true,
        opened: true,
        created_at: '2026-10-19T10:14:00Z',
      },
      {
        id: 'int-2',
        type: 'request_teaching',
        title: 'Lesson explanation: The Durable Write Boundary and WAL',
        completed: true,
        opened: true,
        created_at: '2026-10-19T10:16:30Z',
      },
      {
        id: 'int-3',
        type: 'request_help',
        title:
          'Opened concept guide: Storage, Persistence & Durable Writes (/v1/resources/storage-persistence)',
        completed: true,
        opened: true,
        created_at: '2026-10-19T10:18:15Z',
      },
    ],
    previous_sessions: [
      {
        session_id: 'sess-prev-001',
        concept_id: 'storage-persistence',
        created_at: '2026-10-18T14:30:00Z',
        outcome: 'gap_found',
        skill_comparisons: [
          {
            skill_id: 'memory_lifetime',
            label: 'Memory lifetime',
            baseline: [
              {
                criterion: 'Volatile vs persistent',
                met: false,
                rating: 'not_addressed',
                support_level: 'independent',
                evidence: 'Did not address container crash recovery',
              },
            ],
            revision: [],
            transfer: [],
            change_summary:
              'Earlier session identified gap on memory lifetime.',
          },
        ],
      },
    ],
  },
  messages: [
    {
      id: 'msg-1',
      role: 'learner',
      content:
        "I'm unsure why buffering telemetry in memory is considered unreliable if the server usually runs for months without rebooting.",
      stage: 'investigate',
      created_at: '2026-10-19T10:12:00Z',
    },
    {
      id: 'msg-2',
      role: 'tutor',
      content:
        'Consider what happens during an unexpected crash, power loss, or automated platform deploy. What guarantee does the client receive when your API returns an HTTP 200 OK status before the buffer writes to disk?',
      stage: 'investigate',
      created_at: '2026-10-19T10:12:45Z',
    },
    {
      id: 'msg-3',
      role: 'learner',
      content:
        "The client assumes their data is safely persisted and won't be lost, but if the machine dies 5 seconds later, it's gone forever.",
      stage: 'investigate',
      created_at: '2026-10-19T10:13:30Z',
    },
    {
      id: 'msg-4',
      role: 'tutor',
      content:
        'Exactly. That gap between client acknowledgment and disk synchronization is the durability risk. How can an application bridge that gap without losing all performance?',
      stage: 'investigate',
      created_at: '2026-10-19T10:14:15Z',
    },
    {
      id: 'msg-5',
      role: 'learner',
      content:
        'By using synchronous write-ahead logging (WAL) with fsync before returning the response, or combining concurrent writes into group commits.',
      stage: 'investigate',
      created_at: '2026-10-19T10:15:30Z',
    },
    {
      id: 'msg-6',
      role: 'tutor',
      content:
        'Spot on! Now let us revise your explanation to explicitly define where that durable write boundary belongs.',
      stage: 'investigate',
      created_at: '2026-10-19T10:16:00Z',
    },
  ],
}

function renderReportHtml(mode, forceAccordionsOpen = false) {
  const cssPath = path.resolve(__dirname, '../frontend/src/index.css')
  const cssContent = fs.readFileSync(cssPath, 'utf8')

  const markup = renderToStaticMarkup(
    React.createElement(ReportView, {
      report: representativeFixture.report,
      messages: representativeFixture.messages,
      onBack: () => {},
      initialPrintMode: mode,
    })
  )

  let finalMarkup = markup
  if (forceAccordionsOpen) {
    // Simulate user manually opening all <details> accordions in the UI
    finalMarkup = finalMarkup.replace(/<details/g, '<details open=""')
  }

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Concept Check Report Export (${mode})</title>
  <style>
${cssContent}
  </style>
</head>
<body>
  <div class="app-main">
    ${finalMarkup}
  </div>
</body>
</html>`

  return html
}

const mode = process.argv[2] || 'summary'
const outputPath = process.argv[3]
const forceAccordionsOpen = process.argv[4] === 'true'

if (!outputPath) {
  console.error('Usage: node render_report.cjs <summary|full> <output.html> [forceAccordionsOpen]')
  process.exit(1)
}

const html = renderReportHtml(mode, forceAccordionsOpen)
fs.writeFileSync(outputPath, html, 'utf8')
console.log(`Rendered ${mode} HTML to ${outputPath} (forceAccordionsOpen=${forceAccordionsOpen})`)
