import axios from 'axios'

const _base = import.meta.env.VITE_API_BASE_URL ?? ''

const client = axios.create({
  baseURL: `${_base}/api/ydyo`,
  withCredentials: true,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

let _refreshing: Promise<void> | null = null

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        if (!_refreshing) {
          _refreshing = axios
            .post(`${_base}/api/auth/refresh`, {}, { withCredentials: true })
            .then(() => { _refreshing = null })
            .catch((e) => { _refreshing = null; throw e })
        }
        await _refreshing
        return client(original)
      } catch {
        window.location.href = '/login'
      }
    }
    if (error.response?.status === 403) {
      // sessionStorage role can drift from the HttpOnly cookie after switching
      // accounts in another tab — surface a clear message.
      const detail = error.response?.data?.detail
      if (detail === 'Insufficient permissions') {
        error.response.data.detail =
          'Insufficient permissions. Log out and sign in as ydyo@iyte.edu.tr (or a System Admin account).'
      }
    }
    return Promise.reject(error)
  },
)

// ── Types ───────────────────────────────────────────────────────────────

export interface YdyoApplicationSummary {
  id: string
  tracking_number: string | null
  status: string
  program: string | null
  applicant: string | null
  certificate: {
    id: string
    file_name: string | null
    status: string
    extracted_data: {
      exam_type?: string
      score?: number
      issued_on?: string
      expires_on?: string
      filename?: string
    } | null
  } | null
  english_review: {
    approved: boolean | null
    exam_type: string | null
    exam_score: number | null
    notes: string | null
    reviewed_at: string | null
    must_take_exam: boolean
    exam_date: string | null
    published_at: string | null
    published_by: string | null
  } | null
}

export interface YdyoDocument {
  id: string
  doc_type: string
  status: string
  file_name: string | null
  extracted_data: Record<string, unknown> | null
}

export interface YdyoEnglishReview {
  approved: boolean | null
  exam_type: string | null
  exam_score: number | null
  notes: string | null
  reviewed_at: string | null
}

export interface YdyoApplicationDetail {
  id: string
  tracking_number: string | null
  status: string
  program: string | null
  applicant_name: string | null
  applicant_email: string | null
  english_review: YdyoEnglishReview | null
  documents: YdyoDocument[]
}

export interface YdyoExamResult {
  application_id: string
  applicant_name: string | null
  score: number | null
  passed: boolean | null
}

export type EnglishRejectionReason =
  | 'EXPIRED_EXAM'
  | 'INSUFFICIENT_SCORE'
  | 'UNVERIFIABLE_DOCUMENT'
  | 'OTHER'

// ── Endpoints ───────────────────────────────────────────────────────────

export async function listYdyoApplications(
  scope: 'pending' | 'all' = 'all',
): Promise<YdyoApplicationSummary[]> {
  const { data } = await client.get<YdyoApplicationSummary[]>('/applications', { params: { scope } })
  return data
}

export async function getYdyoApplication(id: string): Promise<YdyoApplicationDetail> {
  const { data } = await client.get<YdyoApplicationDetail>(`/applications/${id}`)
  return data
}

export async function approveEnglish(
  id: string,
  notes?: string,
  exam_type?: string,
  exam_score?: number,
): Promise<{ application_id: string; approved: boolean; exam_type: string | null; exam_score: number | null }> {
  const { data } = await client.post(`/applications/${id}/approve-english`, {
    notes: notes || null,
    exam_type: exam_type || null,
    exam_score: exam_score ?? null,
  })
  return data
}

export async function rejectEnglish(
  id: string,
  rejection_reason: EnglishRejectionReason,
  notes: string,
): Promise<{ application_id: string; approved: boolean; notes: string | null }> {
  const { data } = await client.post(`/applications/${id}/reject-english`, {
    rejection_reason,
    notes,
  })
  return data
}

export async function routeToExam(
  id: string,
  notes: string,
): Promise<{ application_id: string; must_take_exam: boolean; notes: string | null }> {
  const { data } = await client.post(`/applications/${id}/route-to-exam`, { notes })
  return data
}

export async function publishExamResult(
  id: string,
  score: number,
  passed: boolean,
  rejectionReason: EnglishRejectionReason = 'INSUFFICIENT_SCORE',
): Promise<{ processed: number; passed_count: number; failed_count: number }> {
  const { data } = await client.post(`/applications/${id}/exam-result`, {
    score,
    passed,
    exam_type: 'IZTECH_EXAM',
    rejection_reason: rejectionReason,
  })
  return data
}

// ── UC-05-02 ────────────────────────────────────────────────────────────

export async function recordExamResult(
  id: string,
  score: number,
  examDate?: string,
  examType: string = 'IZTECH_EXAM',
): Promise<{
  application_id: string
  exam_type: string | null
  exam_score: number | null
  exam_date: string | null
  published_at: string | null
}> {
  const { data } = await client.post(`/applications/${id}/record-exam-result`, {
    score,
    exam_type: examType,
    exam_date: examDate,
  })
  return data
}

export async function publishPendingExamResults(): Promise<{
  processed: number
  passed_count: number
  failed_count: number
  published_at: string
}> {
  const { data } = await client.post('/exam-results/publish-pending')
  return data
}

export async function listExamResults(): Promise<YdyoExamResult[]> {
  const { data } = await client.get<YdyoExamResult[]>('/exam-results')
  return data
}
