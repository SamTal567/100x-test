export interface Concept {
  id: string
  module: string
  slug: string
  title: string
  description: string
  enabled: boolean
}

export interface DiagramNode {
  id: string
  label: string
  x: number
  y: number
  type: 'actor' | 'process' | 'volatile' | 'persistent' | 'blank'
}

export interface DiagramEdge {
  id: string
  from: string
  to: string
  label: string
  status: 'correct' | 'needs_repair' | 'active'
}

export interface DiagramBlank {
  id: string
  prompt: string
  options: string[]
}

export interface DiagramRepairOption {
  id: string
  label: string
  target_node: string
}

export interface PresetDiagram {
  diagram_id: string
  title: string
  task_instruction: string
  nodes: DiagramNode[]
  edges: DiagramEdge[]
  blanks?: DiagramBlank[]
  repair_options?: DiagramRepairOption[]
  interaction_type: 'repair' | 'completion' | 'trace'
}

export interface ClozeBlank {
  id: string
  options: string[]
}

export interface ClozePreset {
  cloze_id: string
  sentence_template: string
  blanks: ClozeBlank[]
  justification_prompt: string
}

export interface CasePrompt {
  id: string
  stage: string
  case_type: string
  scenario_text: string
  response_format?: string
  assumptions?: string[]
  review_status?: string
  case_version?: number
  rubric_version?: number
  diagram_preset?: PresetDiagram | null
  cloze_preset?: ClozePreset | null
}

export interface SessionListItem {
  id: string
  concept_id: string
  concept_title: string
  stage: 'diagnostic' | 'investigate' | 'apply' | 'review' | 'completed'
  created_at: string
  updated_at: string
}

export interface SessionDetail {
  id: string
  concept_id: string
  concept_title?: string
  concept_slug?: string
  stage: 'diagnostic' | 'investigate' | 'apply' | 'review' | 'completed'
  version: number
  current_prompt: CasePrompt | null
  diagnostic_index: number
  diagnostic_total?: number
  created_at: string
  updated_at: string
  messages?: Message[]
  attempts?: AttemptReport[]
  allowed_actions?: string[]
  evidence_cards?: EvidenceCard[]
  gaps?: GapReport[]
  processing_status?: string
  provenance_warning?: string | null
  practice_active?: boolean
  pending_turn?: TurnRequest | null
}

export interface Message {
  id: string
  role: 'learner' | 'tutor' | 'system'
  content: string
  stage: string
  input_mode?: 'typed' | 'voice' | null
  created_at: string
  provider_status?: 'complete' | 'unavailable' | 'error' | null
}

export interface TurnRequest {
  client_turn_id: string
  expected_version: number
  prompt_id?: string | null
  action:
    | 'submit_answer'
    | 'clarify'
    | 'correct_ai'
    | 'answer_probe'
    | 'request_hint'
    | 'request_teaching'
    | 'request_practice'
    | 'request_help'
    | 'resource_opened'
    | 'resource_completed'
    | 'continue'
    | 'submit_practice'
    | 'finish_session'
    | 'retry_processing'
  text?: string | null
  diagram_state?: Record<string, unknown> | null
  cloze_state?: Record<string, unknown> | null
  attachment_ids?: string[]
  transcription_id?: string | null
  input_mode?: 'typed' | 'voice'
  resource_id?: string | null
  intervention_id?: string | null
}

export interface EvidenceCard {
  id?: string
  title?: string
  gap_description?: string
  evidence_quote?: string | null
  probe_question?: string | null
  status?: string
  source_attempt_id?: string | null
  [key: string]: unknown
}

export interface InterventionInfo {
  id?: string
  type: string
  title: string
  content?: string
  url?: string
  resource_id?: string
}

export interface TurnResponse {
  stage: 'diagnostic' | 'investigate' | 'apply' | 'review' | 'completed'
  version: number
  messages: Message[]
  current_prompt: CasePrompt | null
  allowed_actions: string[]
  processing_status: string
  diagnostic_index: number
  diagnostic_total?: number
  practice_active?: boolean
  evidence_cards: EvidenceCard[]
  intervention?: InterventionInfo | null
}

export interface GapReport {
  id: string
  description: string
  evidence_quote?: string | null
  probe_text?: string | null
  status: string
  source_attempt_id?: string | null
}

export interface CriterionAssessment {
  criterion: string
  skill_id?: string
  rating?: string
  met: boolean | null
  evidence?: string
  reviewer_notes?: string
  status: 'provisional' | 'reviewed' | 'corrected'
}

export interface AttemptReport {
  id: string
  stage: string
  case_type: string
  scenario_text: string
  answer_text: string
  case_prompt_id?: string
  case_version?: number
  rubric_version?: number
  gap_id?: string | null
  created_at?: string
  processing_status?: string
  provenance_warning?: string | null
  diagram_preset?: PresetDiagram | null
  cloze_preset?: ClozePreset | null
  response_format?: string
  diagram_state?: Record<string, unknown> | null
  cloze_state?: Record<string, unknown> | null
  criteria: CriterionAssessment[]
  support_level: string
  score?: number | null
  met_criteria_count?: number | null
  total_criteria_count?: number | null
  uncertain_criteria_count?: number
  unavailable_criteria_count?: number
}

export interface SkillEvidence {
  attempt_id: string
  criterion: string
  rating?: string
  met: boolean | null
  evidence?: string
  support_level: string
}

export interface SkillComparison {
  skill_id: string
  label: string
  baseline: SkillEvidence[]
  revision: SkillEvidence[]
  transfer: SkillEvidence[]
  change_summary: string
  review_status: string
}

export interface SessionReport {
  session_id: string
  concept_title: string
  stage: string
  outcome: 'gap_found' | 'no_gap' | 'inconclusive'
  gaps: GapReport[]
  attempts: AttemptReport[]
  interventions_used: { id?: string; type: string; title: string | null; status?: string; opened: boolean; completed: boolean; created_at?: string; url?: string; resource_id?: string }[]
  skill_comparisons?: SkillComparison[]
  previous_sessions?: { session_id: string; created_at: string; outcome: string; skill_comparisons: SkillComparison[] }[]
  assessment_status: 'provisional' | 'reviewed'
  outcome_reason: string
  initial_score?: number | null
  final_score?: number | null
  score_change?: number | null
  score_summary?: string | null
  stage_summaries?: {
    stage: 'baseline' | 'revision' | 'transfer'
    attempt_count: number
    met_count: number
    total_count: number
    uncertain_count: number
    unavailable_count: number
    percentage: number | null
    status: 'not_assessed' | 'partial' | 'assessed'
    support_levels: string[]
  }[]
}

export interface TranscriptionResult {
  id: string
  raw_transcript: string | null
  confirmed_text: string | null
  status: 'pending' | 'transcribed' | 'confirmed' | 'failed'
  created_at: string
}

export interface AssessmentReviewItem {
  id: string
  attempt_id: string
  criterion: string
  skill_id?: string
  rating?: string
  status: 'provisional' | 'reviewed' | 'corrected'
  met: boolean | null
  evidence: string | null
  scenario_text?: string
  answer_text?: string
  diagram_state?: Record<string, unknown> | null
  reference_answer?: string
  reviewer_notes?: string | null
  case_version?: number
  rubric_version?: number
  diagram_preset?: PresetDiagram | null
  cloze_preset?: ClozePreset | null
  cloze_state?: Record<string, unknown> | null
  proposal?: { rating?: string; met?: boolean | null; evidence?: string; reviewer_notes?: string } | null
  review_history?: { reviewer_name?: string; created_at?: string; review?: { rating?: string; met?: boolean | null; evidence?: string; reviewer_notes?: string; status?: string } }[]
}

export interface CaseReviewItem {
  id: string
  authored_id: string
  concept_id: string
  stage: string
  case_type: string
  version: number
  active: boolean
  review_status: string
  scenario_text: string
  assumptions: string[]
  response_format: string
  diagram_preset?: PresetDiagram | null
  cloze_preset?: ClozePreset | null
  reference_answer: string
  criteria: { criterion?: string; text?: string; skill_id?: string; [key: string]: unknown }[]
  rubric_version?: number
}

export interface HealthResponse {
  status: string
  openai_available: boolean
  fish_audio_available: boolean
}
