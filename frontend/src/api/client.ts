import type {
  Concept,
  SessionListItem,
  SessionDetail,
  TurnRequest,
  TurnResponse,
  SessionReport,
  TranscriptionResult,
  AssessmentReviewItem,
  HealthResponse,
  CaseReviewItem,
  AuthResponse,
  AuthStatus,
} from '../types'
const BASE_URL =
  typeof window !== 'undefined' && window.location.hostname.endsWith('vercel.app')
    ? ''
    : (import.meta.env.VITE_API_BASE_URL || '')
export const AUTH_REQUIRED_EVENT = 'cc:auth-required'

export class ApiError extends Error {
  readonly status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('cc_auth_token') : null
  const authHeaders: Record<string, string> = {}
  if (token) {
    authHeaders['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    credentials: 'include',
    headers: {
      'Accept': 'application/json',
      ...authHeaders,
      ...options.headers,
    },
  })

  if (!res.ok) {
    if (res.status === 401 && /^\/v1\/(sessions|attachments)(?:\/|$)/.test(endpoint)
      && (typeof localStorage === 'undefined' || localStorage.getItem('cc_auth_token') === token)) {
      if (typeof localStorage !== 'undefined') localStorage.removeItem('cc_auth_token')
      if (typeof window !== 'undefined') window.dispatchEvent(new Event(AUTH_REQUIRED_EVENT))
    }
    let errorDetail = `Request failed: ${res.status} ${res.statusText}`
    try {
      const errorJson = await res.json()
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail)
      }
    } catch {
      // ignore
    }
    throw new ApiError(errorDetail, res.status)
  }

  return res.json() as Promise<T>
}

export const api = {
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health')
  },

  async getConcepts(): Promise<Concept[]> {
    return request<Concept[]>('/v1/concepts')
  },

  async listSessions(): Promise<SessionListItem[]> {
    return request<SessionListItem[]>('/v1/sessions')
  },

  async createSession(conceptId: string): Promise<SessionDetail> {
    return request<SessionDetail>('/v1/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ concept_id: conceptId }),
    })
  },

  async getSession(sessionId: string): Promise<SessionDetail> {
    return request<SessionDetail>(`/v1/sessions/${sessionId}`)
  },

  async submitTurn(sessionId: string, turn: TurnRequest): Promise<TurnResponse> {
    return request<TurnResponse>(`/v1/sessions/${sessionId}/turns`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(turn),
    })
  },

  async getSessionReport(sessionId: string): Promise<SessionReport> {
    return request<SessionReport>(`/v1/sessions/${sessionId}/report`)
  },

  async uploadTranscription(sessionId: string, audioBlob: Blob, filename = 'recording.webm'): Promise<TranscriptionResult> {
    const formData = new FormData()
    formData.append('audio', audioBlob, filename)

    return request<TranscriptionResult>(`/v1/sessions/${sessionId}/transcriptions`, {
      method: 'POST',
      body: formData,
    })
  },

  async listReviewAssessments(reviewerKey: string): Promise<AssessmentReviewItem[]> {
    return request<AssessmentReviewItem[]>('/v1/review/assessments', {
      headers: { 'X-Reviewer-Key': reviewerKey },
    })
  },

  async submitReview(
    assessmentId: string,
    data: { status: 'reviewed' | 'corrected'; met?: boolean | null; reviewer_notes?: string; reviewer_name?: string },
    reviewerKey: string
  ): Promise<{ status: string; assessment_id: string }> {
    return request<{ status: string; assessment_id: string }>(`/v1/review/assessments/${assessmentId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Reviewer-Key': reviewerKey,
      },
      body: JSON.stringify(data),
    })
  },

  async listReviewCases(reviewerKey: string): Promise<CaseReviewItem[]> {
    return request<CaseReviewItem[]>('/v1/review/cases', { headers: { 'X-Reviewer-Key': reviewerKey } })
  },

  async submitCaseReview(caseId: string, data: { review_status: 'reviewed' | 'rejected'; reviewer_name: string; reviewer_notes?: string }, reviewerKey: string): Promise<{ status: string }> {
    return request<{ status: string }>(`/v1/review/cases/${caseId}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Reviewer-Key': reviewerKey }, body: JSON.stringify(data),
    })
  },

  async signup(data: { email: string; password: string; full_name?: string }): Promise<AuthResponse> {
    const res = await request<AuthResponse>('/v1/auth/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (res.access_token && typeof localStorage !== 'undefined') {
      localStorage.setItem('cc_auth_token', res.access_token)
    }
    return res
  },

  async login(data: { email: string; password: string }): Promise<AuthResponse> {
    const res = await request<AuthResponse>('/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
    if (res.access_token && typeof localStorage !== 'undefined') {
      localStorage.setItem('cc_auth_token', res.access_token)
    }
    return res
  },

  async logout(): Promise<{ status: string }> {
    const token = typeof localStorage !== 'undefined' ? localStorage.getItem('cc_auth_token') : null
    const result = await request<{ status: string }>('/v1/auth/logout', { method: 'POST' })
    if (typeof localStorage !== 'undefined' && localStorage.getItem('cc_auth_token') === token) {
      localStorage.removeItem('cc_auth_token')
    }
    return result
  },

  async getMe(): Promise<AuthStatus> {
    return request<AuthStatus>('/v1/auth/me')
  },
}
