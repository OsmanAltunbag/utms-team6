import axios from 'axios'
import type {
  YGKApplicationSummary,
  YGKEvaluationDetail,
  ScoreVerifyResult,
  CorrectionField,
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
