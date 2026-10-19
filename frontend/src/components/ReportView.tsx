import React, { useState } from 'react'
import { PresetDiagramView } from './PresetDiagramView'
import { ClozeExerciseView } from './ClozeExerciseView'
import { supportLabel } from '../lib/sessionDrafts'
import { SessionTranscript } from './SessionTranscript'
import { QuestionPartFeedback } from './QuestionPartFeedback'
import type { AttemptReport, Message, SessionDetail, SessionReport, SkillComparison, SkillEvidence } from '../types'

export const AttemptView: React.FC<{ attempt: AttemptReport; anchor?: boolean }> = ({ attempt, anchor = true }) => <div className="attempt-card card-flat" id={anchor ? `attempt-${attempt.id}` : undefined}>
  <div className="attempt-card-topbar">
    <span className="attempt-index-tag">{attempt.stage === 'practice' || ['practice', 'guided_practice'].includes(attempt.case_type) ? 'Guided practice' : attempt.stage === 'investigate' ? 'Revised reasoning' : attempt.stage === 'apply' ? 'Fresh case' : 'Baseline case'}</span>
    <span className="support-badge">{supportLabel(attempt.support_level)}</span>
    {Boolean(attempt.total_criteria_count) && <span className="badge badge-provisional">{attempt.met_criteria_count}/{attempt.total_criteria_count} criteria demonstrated{attempt.score == null ? ' · assessment incomplete' : ` (${attempt.score}% of these criteria)`}</span>}
  </div>
  <div className="attempt-scenario-box"><span className="attempt-box-label">Scenario</span><div className="attempt-box-content">{attempt.scenario_text}</div></div>
  <div className="attempt-answer-box"><span className="attempt-box-label">Submitted reasoning</span><div className="attempt-box-content">{attempt.answer_text}</div></div>
  {attempt.provenance_warning && <p className="report-disclaimer-box" role="note">{attempt.provenance_warning}</p>}
  {attempt.diagram_preset && <PresetDiagramView diagram={attempt.diagram_preset} value={attempt.diagram_state} readOnly />}
  {attempt.diagram_state && !attempt.diagram_preset && <p className="muted-note">An older diagram selection is saved, but its original preset is unavailable.</p>}
  {attempt.cloze_preset && <ClozeExerciseView cloze={attempt.cloze_preset} value={attempt.cloze_state as Record<string, string> | null} readOnly />}
  <p className="muted-note">Case version {attempt.case_version ?? 'not recorded'} · Rubric version {attempt.rubric_version ?? 'not recorded'}{attempt.processing_status && ` · Processing: ${attempt.processing_status.replaceAll('_', ' ')}`}</p>
  <QuestionPartFeedback attempt={attempt} />
  <div className="criteria-table">{attempt.criteria.map((criterion, index) => <div key={`${criterion.criterion}-${index}`} className="criterion-card-row">
    <span className={`criterion-status-glyph ${criterion.met === true ? 'met' : criterion.met === false ? 'not-met' : 'unclear'}`} aria-label={criterion.met === true ? 'Demonstrated' : criterion.met === false ? 'Needs attention' : 'Uncertain'}>{criterion.met === true ? '✓' : criterion.met === false ? '!' : '?'}</span>
    <div className="criterion-details">
      <div className="criterion-statement-line">
        <strong>{criterion.criterion}</strong>
        <div className="criterion-badges-wrap">
          {criterion.question_part_id && <span className="badge badge-part">Part: {criterion.question_part_id}</span>}
          {criterion.coverage && <span className="badge badge-coverage">{criterion.coverage.replaceAll('_', ' ')}</span>}
          {criterion.issue_type && <span className="badge badge-warning">{criterion.issue_type.replaceAll('_', ' ')}</span>}
          {criterion.unprompted && <span className="badge badge-unprompted" title={criterion.unprompted_note || 'Not explicitly requested in scenario prompt'}>⚠️ Not asked in prompt</span>}
          <span className={`badge ${criterion.status === 'provisional' ? 'badge-provisional' : 'badge-reviewed'}`}>{criterion.skill_id?.startsWith('exercise:') ? 'Prepared selection check' : criterion.status === 'provisional' ? 'Provisional AI judgment' : criterion.status === 'corrected' ? 'Human corrected' : 'Human reviewed'}</span>
        </div>
      </div>
      <p>{criterion.rating?.replaceAll('_', ' ') || 'Rating not recorded'}</p>
      {criterion.unprompted && criterion.unprompted_note && <p className="muted-note text-warning">{criterion.unprompted_note}</p>}
      {criterion.demonstrated_explanation && <p className="criterion-demonstrated-text"><strong>Demonstrated:</strong> {criterion.demonstrated_explanation}</p>}
      {criterion.explanation && <p className="criterion-explanation-text"><strong>Explanation:</strong> {criterion.explanation}</p>}
      {criterion.next_action && <p className="criterion-next-action-text"><strong>Next action:</strong> {criterion.next_action}</p>}
      {criterion.evidence && !['not_addressed', 'technical_failure'].includes(criterion.rating || '') && criterion.issue_type !== 'technical_failure' && criterion.coverage !== 'unanswered' && <p className="criterion-evidence-text">Evidence: {criterion.evidence}</p>}
      {criterion.reviewer_notes && <p className="criterion-reviewer-note">Reviewer: {criterion.reviewer_notes}</p>}
    </div>
  </div>)}</div>
</div>

const STAGE_EMPTY_REASONS: Record<string, string> = {
  Baseline: 'Not asked in this case',
  'Revision with support': 'Not attempted (revision skipped)',
  'Fresh case': 'Not rechecked in fresh case',
}

const EvidenceList: React.FC<{ items: SkillEvidence[]; emptyReason?: string }> = ({ items, emptyReason = 'Not attempted' }) => items.length ? <ul className="comparison-evidence">{items.map((item, index) => <li key={`${item.attempt_id}-${index}`}>
  <a href={`#attempt-${item.attempt_id}`}>{item.criterion}</a><br />
  <strong>{item.rating?.replaceAll('_', ' ') || (item.met === true ? 'Demonstrated' : item.met === false ? 'Needs attention' : 'Uncertain')}</strong> · {supportLabel(item.support_level)}
  {item.evidence && <p>{item.evidence}</p>}
</li>)}</ul> : <p className="muted-note">{emptyReason}</p>

export const SkillComparisons: React.FC<{ comparisons: SkillComparison[]; historical?: boolean }> = ({ comparisons, historical = false }) => <div className="skill-comparisons">
  {comparisons.map(comparison => <section key={comparison.skill_id} className="card-flat comparison-card">
    <h4>{comparison.label}</h4><p className="muted-note">{comparison.review_status === 'reviewed' ? 'Human reviewed' : 'Provisional comparison — human review needed'}</p>
    <div className="comparison-columns">{([['Baseline', comparison.baseline], ['Revision with support', comparison.revision], ['Fresh case', comparison.transfer]] as const).map(([label, evidence]) => {
      const reason = STAGE_EMPTY_REASONS[label] || 'Not attempted'
      return <div key={label}>
        <h5>{label}</h5>
        {historical ? evidence.length ? <ul className="comparison-evidence">{evidence.map((item, index) => <li key={index}><strong>{item.rating?.replaceAll('_', ' ') || 'Uncertain'}</strong> · {supportLabel(item.support_level)}<p>{item.evidence || item.criterion}</p></li>)}</ul> : <p className="muted-note">{reason}</p> : <EvidenceList items={evidence} emptyReason={reason} />}
      </div>
    })}</div>
    <p>{comparison.change_summary}</p>
  </section>)}
</div>

export const ReportView: React.FC<{ report: SessionReport; onBack: () => void; onOpenSession?: (id: string) => void; onRetryAssessments?: () => void; retryDisabled?: boolean; messages?: Message[]; initialPrintMode?: 'summary' | 'full' }> = ({ report, onBack, onOpenSession, onRetryAssessments, retryDisabled, messages, initialPrintMode }) => {
  const [printMode, setPrintMode] = useState<'summary' | 'full'>(initialPrintMode || 'summary')
  const summary = report.session_summary

  return <article className={`card report-card print-mode-${printMode}`} aria-labelledby="report-heading">
    {/* Part A: Short Session Summary */}
    <div className="report-header-banner">
      <div className="report-badge-row">
        <span className={`outcome-status-badge outcome-${report.outcome}`}>
          {report.outcome === 'no_gap' ? 'NO GAP IN TESTED CASES'
            : report.outcome === 'criteria_demonstrated' ? 'PREPARED CRITERIA DEMONSTRATED'
            : report.outcome === 'gap_found' ? 'CRITERIA NEEDING ATTENTION'
            : 'ASSESSMENT INCONCLUSIVE'}
        </span>
        <span className={`badge ${report.assessment_status === 'reviewed' ? 'badge-reviewed' : 'badge-provisional'}`}>
          {report.assessment_status === 'reviewed' ? 'Human reviewed' : 'Provisional AI assessment'}
        </span>
      </div>
      <h2 id="report-heading" className="report-title">{report.concept_title} — Evidence report</h2>
      <p className="report-outcome-reason">{report.outcome_reason}</p>
    </div>

    {/* 1. 5-Point Personal Summary (Prominently First) */}
    {summary?.personal_summary && <section className="report-personal-summary card-flat mb-4" aria-label="Personal summary">
      <h3 className="section-subtitle">Personal summary</h3>
      <div className="personal-summary-grid">
        <div className="summary-point-card personal-summary-card">
          <span className="summary-point-label">What you demonstrated</span>
          <p>{summary.personal_summary.demonstrated}</p>
        </div>
        <div className="summary-point-card personal-summary-card">
          <span className="summary-point-label">Missing or incorrect</span>
          <p>{summary.personal_summary.missing_or_incorrect}</p>
        </div>
        <div className="summary-point-card personal-summary-card">
          <span className="summary-point-label">Changed after help</span>
          <p>{summary.personal_summary.changed_after_help}</p>
        </div>
        <div className="summary-point-card personal-summary-card">
          <span className="summary-point-label">Needs independent checking</span>
          <p>{summary.personal_summary.needs_independent_checking}</p>
        </div>
        <div className="summary-point-card personal-summary-card">
          <span className="summary-point-label">Recommended next step</span>
          <p>{summary.personal_summary.recommended_next_step}</p>
        </div>
      </div>
    </section>}

    {/* 2. Session Overview (Unfamiliar case, Revised reasoning, etc.) */}
    {summary && (summary.unfamiliar_case_summary || summary.revised_reasoning_summary || summary.unresolved_summary || summary.support_summary) && <section className="report-summary-grid card-flat mb-4" aria-label="Session summary findings">
      <h3 className="section-subtitle">Session overview</h3>
      <div className="summary-grid-cards">
        {summary.unfamiliar_case_summary && <div className="summary-point-card">
          <span className="summary-point-label">Unfamiliar case</span>
          <p>{summary.unfamiliar_case_summary}</p>
        </div>}
        {summary.revised_reasoning_summary && <div className="summary-point-card">
          <span className="summary-point-label">Revised reasoning</span>
          <p>{summary.revised_reasoning_summary}</p>
        </div>}
        {summary.unresolved_summary && <div className="summary-point-card">
          <span className="summary-point-label">Unresolved / unassessed</span>
          <p>{summary.unresolved_summary}</p>
        </div>}
        {summary.support_summary && <div className="summary-point-card">
          <span className="summary-point-label">Support used</span>
          <p>{summary.support_summary}</p>
        </div>}
      </div>
    </section>}

    {report.attempts.some(attempt => attempt.stage !== 'practice' && attempt.question_parts?.some(part => !part.supplementary)) && <section className="report-part-coverage card-flat mb-4" aria-label="Question-part coverage overview">
      <h3 className="section-subtitle">Question-part coverage</h3>
      {report.attempts.filter(attempt => attempt.stage !== 'practice' && attempt.question_parts?.some(part => !part.supplementary)).map((attempt, index) => <div key={attempt.id}>
        <h4>{attempt.stage === 'apply' ? 'Fresh case' : attempt.stage === 'investigate' ? 'Revised reasoning' : `Baseline case ${index + 1}`}</h4>
        <QuestionPartFeedback attempt={attempt} compact />
      </div>)}
    </section>}

    {/* 3. Concern Cards */}
    {Boolean(summary?.concern_cards?.length) && <section className="report-concern-cards card-flat mb-4" aria-label="Specific areas of concern">
      <h3 className="section-subtitle">Specific areas of concern</h3>
      <div className="concern-cards-list">
        {summary!.concern_cards!.map((card, index) => <div key={`${card.case_name}-${card.question_part}-${index}`} className="concern-card card-flat mb-3">
          <div className="concern-card-topbar">
            <div className="concern-card-title-group">
              <strong className="concern-case-name">{card.case_name}</strong>
              {card.question_part && <span className="concern-question-part">Part: {card.question_part}</span>}
            </div>
            <div className="concern-card-badges">
              {card.issue_type && <span className="badge badge-warning">{card.issue_type.replaceAll('_', ' ')}</span>}
              {card.rating && <span className="badge badge-provisional">{card.rating.replaceAll('_', ' ')}</span>}
            </div>
          </div>
          {card.learner_quote && card.learner_quote.trim() && <div className="concern-field concern-quote-box">
            <span className="concern-field-label">Your quote:</span>
            <blockquote className="concern-quote">{card.learner_quote}</blockquote>
          </div>}
          {card.what_was_correct && <div className="concern-field">
            <span className="concern-field-label">What was correct:</span>
            <p>{card.what_was_correct}</p>
          </div>}
          <div className="concern-field">
            <span className="concern-field-label">Why this rating:</span>
            <p>{card.why_rating}</p>
          </div>
          {card.how_to_improve && <div className="concern-field">
            <span className="concern-field-label">How to improve:</span>
            <p>{card.how_to_improve}</p>
          </div>}
          {card.suggested_next_step && <div className="concern-field">
            <span className="concern-field-label">Suggested next step:</span>
            <p>{card.suggested_next_step}</p>
          </div>}
        </div>)}
      </div>
    </section>}

    <p className="report-disclaimer-box">Evidence reflects the cases attempted and the support received. A short session does not establish complete mastery or prove that tutoring caused a change. Authored cases remain unreviewed until a person reviews them.</p>

    {onRetryAssessments && report.attempts.some(attempt => !attempt.criteria.length || attempt.criteria.some(criterion => criterion.rating === 'technical_failure')) && <section className="card-flat recovery-card mb-4 no-print" aria-label="Assessment recovery">
      <strong>Some saved answers could not be assessed</strong>
      <p>Retry assessment of those saved answers. This keeps the learner’s original submissions and preserves human-reviewed judgments.</p>
      <button type="button" className="btn btn-secondary" disabled={retryDisabled} onClick={onRetryAssessments}>Retry unavailable assessments</button>
    </section>}

    {/* Part B: Compact Skill Comparison */}
    <section className="report-evidence-section mb-4">
      <h3>Matched skills across cases</h3>
      {report.skill_comparisons?.length ? <SkillComparisons comparisons={report.skill_comparisons} /> : <p>No matched skill comparison is available for this older session. Its original evidence remains below.</p>}
    </section>

    {/* Part C: Expandable Detailed Evidence */}
    <section className="report-evidence-section print-appendix print-hide-in-summary">
      <h3>Detailed evidence & appendix</h3>
      <p className="muted-note no-print">Review original prompts, submitted reasoning, detailed criteria, and recorded support below.</p>

      {/* Stage Progress Breakdown (Moved from Primary View to Appendix) */}
      {Boolean(report.stage_summaries?.length) && <details className="card-flat report-detail-accordion mb-3" open={printMode === 'full'}>
        <summary className="detail-accordion-title">Stage criterion breakdown (separate cases)</summary>
        <div className="mt-3">
          <p className="report-disclaimer-box" role="note">
            Stage percentages describe separate non-comparable tasks and do not measure learning <span>grow</span>th or mastery.
          </p>
          <div className="comparison-columns mt-2">{report.stage_summaries!.map(s => <div className="card-flat" key={s.stage}>
            <h4>{{ baseline: 'Baseline evidence', revision: 'Revision after support', transfer: 'Unfamiliar case evidence' }[s.stage]}</h4>
            {s.status === 'not_assessed' ? <p>Not assessed</p> : <>
              <p><strong>{s.met_count}/{s.total_count} criteria demonstrated</strong>{s.percentage != null ? ` (${s.percentage}% of these criteria)` : ''}</p>
              {s.status === 'partial' && <p className="muted-note">Assessment incomplete; no percentage is assigned.</p>}
              {s.uncertain_count > 0 && <p>{s.uncertain_count} need clarification.</p>}
              {s.unavailable_count > 0 && <p>{s.unavailable_count} could not be assessed.</p>}
              <p className="muted-note">{s.support_levels.map(supportLabel).join(' · ')}</p>
            </>}
          </div>)}</div>
          <p className="muted-note mt-2">Counts describe separate cases, which can cover different skills and difficulty. Use the matched skill evidence above to compare reasoning.</p>
        </div>
      </details>}

      {/* 1. Preserved Scenarios & Answers */}
      <details className="card-flat report-detail-accordion mb-3" open={printMode === 'full'}>
        <summary className="detail-accordion-title">Preserved answers and criterion evidence ({report.attempts?.length || 0} attempts)</summary>
        <div className="attempts-stack mt-3">
          {(report.attempts || []).map(attempt => <AttemptView key={attempt.id} attempt={attempt} />)}
          {!(report.attempts || []).some(attempt => attempt.stage === 'apply') && <p className="report-disclaimer-box">No fresh case was submitted. Independent transfer was not assessed.</p>}
        </div>
      </details>

      {/* 2. Support History */}
      <details className="card-flat report-detail-accordion mb-3" open={printMode === 'full'}>
        <summary className="detail-accordion-title">Support history ({report.interventions_used?.length || 0} events)</summary>
        <div className="mt-3">
          {(report.interventions_used || []).length ? <ol className="support-history">{(report.interventions_used || []).map((item, index) => <li key={item.id || index}><strong>{item.title || item.type.replaceAll('_', ' ')}</strong> · {item.completed ? 'Completed' : item.opened ? 'Opened' : item.status?.replaceAll('_', ' ') || 'Offered'}{item.created_at && <span className="muted-note"> · {new Date(item.created_at).toLocaleString()}</span>}</li>)}</ol> : <p>No assistance events were recorded.</p>}
        </div>
      </details>

      {/* 3. Concerns and Follow-up */}
      {Boolean(report.gaps?.length) && <details className="card-flat report-detail-accordion mb-3" open={printMode === 'full'}>
        <summary className="detail-accordion-title">Concerns and follow-up ({report.gaps?.length || 0} recorded)</summary>
        <div className="mt-3">
          {report.gaps.map(gap => <div className="gap-finding-card mb-2" key={gap.id}>
            <strong>{gap.description}</strong>
            <p>Original status: {gap.status.replaceAll('_', ' ')}</p>
            {gap.addressed_by_attempt_id && <p className="gap-addressed-badge">✓ Addressed in later evidence: <a href={`#attempt-${gap.addressed_by_attempt_id}`}>{gap.addressed_stage || 'later answer'}</a></p>}
            {gap.evidence_quote && <blockquote>{gap.evidence_quote}</blockquote>}
            {gap.probe_text && <p>Follow-up: {gap.probe_text}</p>}
            {gap.source_attempt_id && <a href={`#attempt-${gap.source_attempt_id}`}>View the source answer</a>}
          </div>)}
        </div>
      </details>}

      {/* 4. Earlier Sessions */}
      <details className="card-flat report-detail-accordion mb-3" open={printMode === 'full'}>
        <summary className="detail-accordion-title">Earlier sessions for this concept ({report.previous_sessions?.length || 0})</summary>
        <div className="mt-3">
          {report.previous_sessions?.length ? report.previous_sessions.map(previous => <details className="card-flat earlier-session mb-2" key={previous.session_id} open={printMode === 'full'}>
            <summary>{new Date(previous.created_at).toLocaleString()} · {previous.outcome.replaceAll('_', ' ')}</summary>
            <p className="muted-note">These are separate sessions and cases. Compare the recorded evidence and support; differences do not establish a causal learning effect.</p>
            <SkillComparisons comparisons={previous.skill_comparisons} historical />
            {onOpenSession && <button type="button" className="btn btn-secondary btn-sm mt-2 no-print" onClick={() => onOpenSession(previous.session_id)}>Open preserved session report</button>}
          </details>) : <p>No earlier sessions with comparable evidence were found.</p>}
        </div>
      </details>

      {/* 5. Saved Conversation Transcript */}
      {messages && messages.length > 0 && (
        <details className="card-flat report-detail-accordion report-conversation-section mb-3" open={printMode === 'full'}>
          <summary className="detail-accordion-title">Saved conversation transcript ({messages.length} messages)</summary>
          <div className="mt-3">
            <SessionTranscript messages={messages} stage={(report.stage as SessionDetail['stage']) || 'completed'} open={printMode === 'full'} />
          </div>
        </details>
      )}
    </section>

    {/* Export Controls & Action Footer */}
    <div className="report-action-footer no-print">
      <div className="print-mode-toggle-group" role="radiogroup" aria-label="Print export mode">
        <span className="export-label">Print / Export options:</span>
        <label className="radio-label">
          <input type="radio" name="print-mode" value="summary" checked={printMode === 'summary'} onChange={() => setPrintMode('summary')} />
          Compact summary
        </label>
        <label className="radio-label">
          <input type="radio" name="print-mode" value="full" checked={printMode === 'full'} onChange={() => setPrintMode('full')} />
          Full report with appendix
        </label>
      </div>
      <div className="report-footer-buttons">
        <button type="button" className="btn btn-secondary" onClick={onBack}>← Catalogue</button>
        <button type="button" className="btn btn-primary" onClick={() => window.print()}>🖨️ Print / Export PDF</button>
      </div>
    </div>
  </article>
}
