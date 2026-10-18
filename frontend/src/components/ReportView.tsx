import React from 'react'
import { PresetDiagramView } from './PresetDiagramView'
import { ClozeExerciseView } from './ClozeExerciseView'
import { supportLabel } from '../lib/sessionDrafts'
import type { AttemptReport, SessionReport, SkillComparison, SkillEvidence } from '../types'

export const AttemptView: React.FC<{ attempt: AttemptReport; anchor?: boolean }> = ({ attempt, anchor = true }) => <div className="attempt-card card-flat" id={anchor ? `attempt-${attempt.id}` : undefined}>
  <div className="attempt-card-topbar"><span className="attempt-index-tag">{attempt.stage === 'practice' || ['practice', 'guided_practice'].includes(attempt.case_type) ? 'Guided practice' : attempt.stage === 'investigate' ? 'Revised reasoning' : attempt.stage === 'apply' ? 'Fresh case' : 'Baseline case'}</span><span className="support-badge">{supportLabel(attempt.support_level)}</span>{Boolean(attempt.total_criteria_count) && <span className="badge badge-provisional">{attempt.met_criteria_count}/{attempt.total_criteria_count} criteria demonstrated{attempt.score == null ? ' · assessment incomplete' : ` (${attempt.score}% of these criteria)`}</span>}</div>
  <div className="attempt-scenario-box"><span className="attempt-box-label">Scenario</span><div className="attempt-box-content">{attempt.scenario_text}</div></div>
  <div className="attempt-answer-box"><span className="attempt-box-label">Submitted reasoning</span><div className="attempt-box-content">{attempt.answer_text}</div></div>
  {attempt.provenance_warning && <p className="report-disclaimer-box" role="note">{attempt.provenance_warning}</p>}
  {attempt.diagram_preset && <PresetDiagramView diagram={attempt.diagram_preset} value={attempt.diagram_state} readOnly />}
  {attempt.diagram_state && !attempt.diagram_preset && <p className="muted-note">An older diagram selection is saved, but its original preset is unavailable.</p>}
  {attempt.cloze_preset && <ClozeExerciseView cloze={attempt.cloze_preset} value={attempt.cloze_state as Record<string, string> | null} readOnly />}
  <p className="muted-note">Case version {attempt.case_version ?? 'not recorded'} · Rubric version {attempt.rubric_version ?? 'not recorded'}{attempt.processing_status && ` · Processing: ${attempt.processing_status.replaceAll('_', ' ')}`}</p>
  <div className="criteria-table">{attempt.criteria.map((criterion, index) => <div key={`${criterion.criterion}-${index}`} className="criterion-card-row">
    <span className={`criterion-status-glyph ${criterion.met === true ? 'met' : criterion.met === false ? 'not-met' : 'unclear'}`} aria-label={criterion.met === true ? 'Demonstrated' : criterion.met === false ? 'Needs attention' : 'Uncertain'}>{criterion.met === true ? '✓' : criterion.met === false ? '!' : '?'}</span>
    <div className="criterion-details"><div className="criterion-statement-line"><strong>{criterion.criterion}</strong><span className={`badge ${criterion.status === 'provisional' ? 'badge-provisional' : 'badge-reviewed'}`}>{criterion.skill_id?.startsWith('exercise:') ? 'Prepared selection check' : criterion.status === 'provisional' ? 'Provisional AI judgment' : criterion.status === 'corrected' ? 'Human corrected' : 'Human reviewed'}</span></div>
      <p>{criterion.rating?.replaceAll('_', ' ') || 'Rating not recorded'}</p>
      {criterion.evidence && <p className="criterion-evidence-text">Evidence: {criterion.evidence}</p>}
      {criterion.reviewer_notes && <p className="criterion-reviewer-note">Reviewer: {criterion.reviewer_notes}</p>}
    </div>
  </div>)}</div>
</div>

const EvidenceList: React.FC<{ items: SkillEvidence[] }> = ({ items }) => items.length ? <ul className="comparison-evidence">{items.map((item, index) => <li key={`${item.attempt_id}-${index}`}>
  <a href={`#attempt-${item.attempt_id}`}>{item.criterion}</a><br />
  <strong>{item.rating?.replaceAll('_', ' ') || (item.met === true ? 'Demonstrated' : item.met === false ? 'Needs attention' : 'Uncertain')}</strong> · {supportLabel(item.support_level)}
  {item.evidence && <p>{item.evidence}</p>}
</li>)}</ul> : <p className="muted-note">No evidence recorded.</p>

export const SkillComparisons: React.FC<{ comparisons: SkillComparison[]; historical?: boolean }> = ({ comparisons, historical = false }) => <div className="skill-comparisons">
  {comparisons.map(comparison => <section key={comparison.skill_id} className="card-flat comparison-card">
    <h4>{comparison.label}</h4><p className="muted-note">{comparison.review_status === 'reviewed' ? 'Human reviewed' : 'Provisional comparison — human review needed'}</p>
    <div className="comparison-columns">{([['Baseline', comparison.baseline], ['Revision with support', comparison.revision], ['Fresh case', comparison.transfer]] as const).map(([label, evidence]) => <div key={label}><h5>{label}</h5>{historical ? evidence.length ? <ul className="comparison-evidence">{evidence.map((item, index) => <li key={index}><strong>{item.rating?.replaceAll('_', ' ') || 'Uncertain'}</strong> · {supportLabel(item.support_level)}<p>{item.evidence || item.criterion}</p></li>)}</ul> : <p className="muted-note">No evidence recorded.</p> : <EvidenceList items={evidence} />}</div>)}</div>
    <p>{comparison.change_summary}</p>
  </section>)}
</div>

export const ReportView: React.FC<{ report: SessionReport; onBack: () => void; onOpenSession?: (id: string) => void; onRetryAssessments?: () => void; retryDisabled?: boolean }> = ({ report, onBack, onOpenSession, onRetryAssessments, retryDisabled }) => <article className="card report-card" aria-labelledby="report-heading">
  <div className="report-header-banner"><div className="report-badge-row"><span className={`outcome-status-badge outcome-${report.outcome}`}>{report.outcome === 'no_gap' ? 'NO GAP IN TESTED CASES' : report.outcome === 'gap_found' ? 'CRITERIA NEEDING ATTENTION' : 'ASSESSMENT INCONCLUSIVE'}</span><span className={`badge ${report.assessment_status === 'reviewed' ? 'badge-reviewed' : 'badge-provisional'}`}>{report.assessment_status === 'reviewed' ? 'Human reviewed' : 'Provisional AI assessment'}</span></div><h2 id="report-heading" className="report-title">{report.concept_title} — Evidence report</h2><p>{report.outcome_reason}</p></div>
  {Boolean(report.stage_summaries?.length) && <section className="report-evidence-section" aria-label="Separate assessment stages">
    <div className="comparison-columns">{report.stage_summaries!.map(summary => <div className="card-flat" key={summary.stage}>
      <h3>{{ baseline: 'Baseline evidence', revision: 'Revision after support', transfer: 'Unfamiliar case evidence' }[summary.stage]}</h3>
      {summary.status === 'not_assessed' ? <p>Not assessed</p> : <>
        <p><strong>{summary.met_count}/{summary.total_count} criteria demonstrated</strong>{summary.percentage != null ? ` (${summary.percentage}% of these criteria)` : ''}</p>
        {summary.status === 'partial' && <p className="muted-note">Assessment incomplete; no percentage is assigned.</p>}
        {summary.uncertain_count > 0 && <p>{summary.uncertain_count} need clarification.</p>}
        {summary.unavailable_count > 0 && <p>{summary.unavailable_count} could not be assessed.</p>}
        <p className="muted-note">{summary.support_levels.map(supportLabel).join(' · ')}</p>
      </>}
    </div>)}</div>
    <p className="muted-note">Counts describe separate cases, which can cover different skills and difficulty. Use the matched skill evidence below to compare reasoning.</p>
  </section>}

  <p className="report-disclaimer-box">Evidence reflects the cases attempted and the support received. A short session does not establish complete mastery or prove that tutoring caused a change. Authored cases remain unreviewed until a person reviews them.</p>
  {onRetryAssessments && report.attempts.some(attempt => !attempt.criteria.length || attempt.criteria.some(criterion => criterion.rating === 'technical_failure')) && <section className="card-flat recovery-card" aria-label="Assessment recovery"><strong>Some saved answers could not be assessed</strong><p>Retry assessment of those saved answers. This keeps the learner’s original submissions and preserves human-reviewed judgments.</p><button type="button" className="btn btn-secondary" disabled={retryDisabled} onClick={onRetryAssessments}>Retry unavailable assessments</button></section>}
  <section className="report-evidence-section"><h3>Matched skills across cases</h3>{report.skill_comparisons?.length ? <SkillComparisons comparisons={report.skill_comparisons} /> : <p>No matched skill comparison is available for this older session. Its original evidence remains below.</p>}</section>
  <section className="report-evidence-section"><h3>Support history</h3>{report.interventions_used.length ? <ol className="support-history">{report.interventions_used.map((item, index) => <li key={item.id || index}><strong>{item.title || item.type.replaceAll('_', ' ')}</strong> · {item.completed ? 'Completed' : item.opened ? 'Opened' : item.status?.replaceAll('_', ' ') || 'Offered'}{item.created_at && <span className="muted-note"> · {new Date(item.created_at).toLocaleString()}</span>}</li>)}</ol> : <p>No assistance events were recorded.</p>}</section>
  {report.gaps.length > 0 && <section className="report-evidence-section"><h3>Concerns and follow-up</h3>{report.gaps.map(gap => <div className="gap-finding-card" key={gap.id}><strong>{gap.description}</strong><p>Status: {gap.status.replaceAll('_', ' ')}</p>{gap.evidence_quote && <blockquote>{gap.evidence_quote}</blockquote>}{gap.probe_text && <p>Follow-up: {gap.probe_text}</p>}{gap.source_attempt_id && <a href={`#attempt-${gap.source_attempt_id}`}>View the source answer</a>}</div>)}</section>}
  <section className="report-evidence-section"><h3>Preserved answers and criterion evidence</h3><div className="attempts-stack">{report.attempts.map(attempt => <AttemptView key={attempt.id} attempt={attempt} />)}</div>{!report.attempts.some(attempt => attempt.stage === 'apply') && <p className="report-disclaimer-box">No fresh case was submitted. Independent transfer was not assessed.</p>}</section>
  <section className="report-evidence-section"><h3>Earlier sessions for this concept</h3>{report.previous_sessions?.length ? report.previous_sessions.map(previous => <details className="card-flat earlier-session" key={previous.session_id}><summary>{new Date(previous.created_at).toLocaleString()} · {previous.outcome.replaceAll('_', ' ')}</summary><p className="muted-note">These are separate sessions and cases. Compare the recorded evidence and support; differences do not establish a causal learning effect.</p><SkillComparisons comparisons={previous.skill_comparisons} historical />{onOpenSession && <button className="btn btn-secondary btn-sm" onClick={() => onOpenSession(previous.session_id)}>Open preserved session report</button>}</details>) : <p>No earlier sessions with comparable evidence were found.</p>}</section>
  <div className="report-action-footer"><button type="button" className="btn btn-secondary" onClick={onBack}>← Catalogue</button><button type="button" className="btn btn-primary" onClick={() => window.print()}>Print / Export report</button></div>
</article>
