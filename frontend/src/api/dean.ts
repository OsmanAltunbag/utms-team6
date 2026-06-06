import axios from 'axios'

const client = axios.create({
  baseURL: '/api/dean',
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
            .post('/api/auth/refresh', {}, { withCredentials: true })
            .then(() => { _refreshing = null })
            .catch((e) => { _refreshing = null; throw e })
        }
        await _refreshing
        return client(original)
      } catch {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

// ── Types ───────────────────────────────────────────────────────────────

/** One row in the Dean's Office application list. */
export interface DeanApplicationSummary {
  id: string
  tracking_number: string | null
  /** Raw application lifecycle status (RANKING | ANNOUNCED | REJECTED). */
  status: string
  /** Frontend-friendly badge derived from status: Pending | Approved | Rejected. */
  dean_status: 'Pending' | 'Approved' | 'Rejected' | string
  /** Target department / program at IZTECH. */
  program: string | null
  applicant: string | null
  /** Applicant's current institution (academic_record.institution). */
  current_university: string | null
  /** 4.00-scale GPA from academic_record. */
  gpa: number | null
  /** ISO timestamp the applicant submitted the application. */
  submitted_at: string | null
  ranking_position: number | null
  composite_score: number | null
  intibak_status: string | null
}

export type DeanRejectionCode =
  | 'INSUFFICIENT_ACADEMIC_STANDING'
  | 'QUOTA_LIMIT_REACHED'
  | 'DISCIPLINARY_RECORD'
  | 'UNSUITABLE_PROGRAM_MATCH'
  | 'OTHER'

export interface DeanRejectionCodeOption {
  code: DeanRejectionCode
  label: string
}

export interface DeanRejectAuditLog {
  dean_id: string
  dean_email: string | null
  dean_name: string | null
  action: string
  timestamp: string
  rejection_code: DeanRejectionCode
  rejection_reason: string
  note: string
  ip_address: string
}

export interface DeanRejectResponse {
  status: string
  message: string
  rejection_code: DeanRejectionCode
  rejection_reason: string
  notification_message: string
  audit_log: DeanRejectAuditLog
}

/** Standardized dean rejection reasons (SRS AC-01). */
export const DEAN_REJECTION_OPTIONS: DeanRejectionCodeOption[] = [
  {
    code: 'INSUFFICIENT_ACADEMIC_STANDING',
    label: 'Failure to meet the grade point average requirement.',
  },
  { code: 'QUOTA_LIMIT_REACHED', label: 'Program quota limit has been reached.' },
  { code: 'DISCIPLINARY_RECORD', label: 'Disciplinary record on file.' },
  { code: 'UNSUITABLE_PROGRAM_MATCH', label: 'Unsuitable program match.' },
  { code: 'OTHER', label: 'Other reason (see note).' },
]

// ── API ─────────────────────────────────────────────────────────────────

export async function listDeanApplications(): Promise<DeanApplicationSummary[]> {
  const { data } = await client.get('/applications')
  return data
}

export async function approveDeanApplication(id: string): Promise<{ status: string }> {
  const { data } = await client.post(`/applications/${id}/approve`)
  return data
}

export async function listDeanRejectionCodes(): Promise<DeanRejectionCodeOption[]> {
  const { data } = await client.get<DeanRejectionCodeOption[]>('/rejection-codes')
  return data
}

export async function rejectDeanApplication(
  id: string,
  rejection_code: DeanRejectionCode = 'OTHER',
  note: string = '',
): Promise<DeanRejectResponse> {
  const { data } = await client.post<DeanRejectResponse>(`/applications/${id}/reject`, {
    rejection_code,
    note,
  })
  return data
}

/** Full application bundle for the dean's "View Details" modal. */
export interface DeanApplicationDetail {
  id: string
  tracking_number: string | null
  status: string
  dean_status: 'Pending' | 'Approved' | 'Rejected' | string
  program: string | null
  submitted_at: string | null
  applicant: {
    name: string | null
    email: string | null
    national_id: string | null
  } | null
  academic_record: {
    institution: string | null
    gpa_4: number | null
    gpa_100: number | null
    yks_score: number | null
    credits_completed: number | null
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
  } | null
  department_evaluations: Array<{
    id: string
    score: number | null
    decision: string | null
    notes: string | null
    evaluated_at: string | null
  }>
  ranking_entry: {
    position: number
    composite_score: number
    is_primary: boolean
  } | null
  intibak_table: { id: string; status: string } | null
  documents: Array<{
    id: string
    doc_type: string
    status: string
    file_name: string | null
    file_size_bytes: number | null
    extracted_data: Record<string, unknown> | null
  }>
}

export async function getDeanApplicationDetail(id: string): Promise<DeanApplicationDetail> {
  const { data } = await client.get(`/applications/${id}`)
  return data
}
