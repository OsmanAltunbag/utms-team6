import axios from 'axios'
import type {
  YGKApplicationSummary,
  YGKEvaluationDetail,
  ScoreVerifyResult,
  CorrectionField,
  DeptConditionsResponse,
  EvaluateConditionsResult,
  ManualCourseMappingResult,
  RankingResult,
  IntibakTable,
  CourseMapping,
} from '../types/ygk'

const client = axios.create({
  baseURL: '/api/ygk',
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

export async function listYGKApplications(status?: string): Promise<YGKApplicationSummary[]> {
  const params = status ? { status } : {}
  const { data } = await client.get<YGKApplicationSummary[]>('/applications', { params })
  return data
}

export async function getEvaluationDetail(applicationId: string): Promise<YGKEvaluationDetail> {
  const { data } = await client.get<YGKEvaluationDetail>(`/applications/${applicationId}/evaluation`)
  return data
}

export async function verifyScores(applicationId: string): Promise<ScoreVerifyResult> {
  const { data } = await client.post<ScoreVerifyResult>(`/applications/${applicationId}/verify-scores`)
  return data
}

export async function rejectApplication(applicationId: string): Promise<{ application_status: string }> {
  const { data } = await client.post(`/applications/${applicationId}/reject`)
  return data
}

export async function correctScore(
  applicationId: string,
  field: CorrectionField,
  corrected_value: number,
  correction_note: string,
): Promise<ScoreVerifyResult> {
  const { data } = await client.post<ScoreVerifyResult>(`/applications/${applicationId}/correct-score`, {
    field,
    corrected_value,
    correction_note,
  })
  return data
}

export async function getDeptConditions(applicationId: string): Promise<DeptConditionsResponse> {
  const { data } = await client.get<DeptConditionsResponse>(`/applications/${applicationId}/dept-conditions`)
  return data
}

export async function evaluateConditions(
  applicationId: string,
  opts: {
    notes?: string
    rejectionOverride?: boolean
    portfolioResult?: string
    rejectionJustification?: string
  } = {},
): Promise<EvaluateConditionsResult> {
  const { data } = await client.post<EvaluateConditionsResult>(
    `/applications/${applicationId}/evaluate-conditions`,
    {
      notes: opts.notes ?? null,
      rejection_override: opts.rejectionOverride ?? false,
      portfolio_result: opts.portfolioResult ?? null,
      rejection_justification: opts.rejectionJustification ?? null,
    },
  )
  return data
}

export async function manualCourseMapping(
  applicationId: string,
  external_course: string,
  rule_key: string,
): Promise<ManualCourseMappingResult> {
  const { data } = await client.post<ManualCourseMappingResult>(
    `/applications/${applicationId}/manual-course-mapping`,
    { external_course, rule_key },
  )
  return data
}

// ---------------------------------------------------------------------------
// Ranking (UC-04-03, UC-04-04, UC-04-06)
// ---------------------------------------------------------------------------

export async function generateRanking(programId: string, periodId: string): Promise<RankingResult> {
  const { data } = await client.post<RankingResult>('/rankings/generate', {
    program_id: programId,
    period_id: periodId,
  })
  return data
}

export async function getRanking(rankingId: string): Promise<RankingResult> {
  const { data } = await client.get<RankingResult>(`/rankings/${rankingId}`)
  return data
}

export async function approveRanking(rankingId: string): Promise<RankingResult> {
  const { data } = await client.post<RankingResult>(`/rankings/${rankingId}/approve`)
  return data
}

export async function deleteRanking(rankingId: string): Promise<void> {
  await client.delete(`/rankings/${rankingId}`)
}

export async function returnRankingForCorrection(rankingId: string, note: string): Promise<{ id: string; status: string; note: string }> {
  const { data } = await client.post(`/rankings/${rankingId}/return`, { note })
  return data
}

export async function getWaitlist(rankingId: string): Promise<{ vacant_slots: number; waitlisted: Array<{ application_id: string; position: number; composite_score: number }> }> {
  const { data } = await client.get(`/rankings/${rankingId}/waitlist`)
  return data
}

export async function promoteWaitlisted(rankingId: string, withdrawnApplicationId: string): Promise<{ promoted: { application_id: string; position: number; composite_score: number } | null; message: string }> {
  const { data } = await client.post(`/rankings/${rankingId}/promote-waitlisted`, {
    withdrawn_application_id: withdrawnApplicationId,
  })
  return data
}

// ---------------------------------------------------------------------------
// Intibak (UC-04-05)
// ---------------------------------------------------------------------------

export async function createIntibakTable(applicationId: string): Promise<{ id: string; application_id: string; status: string }> {
  const { data } = await client.post(`/applications/${applicationId}/intibak`)
  return data
}

export async function getIntibakTable(tableId: string): Promise<IntibakTable> {
  const { data } = await client.get<IntibakTable>(`/intibak/${tableId}`)
  return data
}

export async function addCourseMapping(
  tableId: string,
  mapping: {
    source_course: string
    source_credits?: number | null
    target_course: string
    target_credits?: number | null
    equivalence_type: string
    notes?: string | null
  },
): Promise<CourseMapping> {
  const { data } = await client.post<CourseMapping>(`/intibak/${tableId}/mappings`, mapping)
  return data
}

export async function submitIntibakTable(tableId: string): Promise<{ status: string; submitted_at: string }> {
  const { data } = await client.post(`/intibak/${tableId}/submit`)
  return data
}
