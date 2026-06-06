import axios from 'axios'
import type {
  ResultsResponse,
  PublishResultsResponse,
  StaffApplicationSummary,
  StaffApplicationDetail,
  RejectionReasonCode,
} from '../types/staff'

const client = axios.create({
  baseURL: '/api/staff',
  withCredentials: true,
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

// ---------------------------------------------------------------------------
// SPEC-006: Application review
// ---------------------------------------------------------------------------

export async function listStaffApplications(params?: {
  status?: string
  program_id?: string
  period_id?: string
}): Promise<StaffApplicationSummary[]> {
  const { data } = await client.get<StaffApplicationSummary[]>('/applications', { params })
  return data
}

export async function getStaffApplication(id: string): Promise<StaffApplicationDetail> {
  const { data } = await client.get<StaffApplicationDetail>(`/applications/${id}`)
  return data
}

export async function approveVerification(applicationId: string): Promise<{ id: string; status: string }> {
  const { data } = await client.post<{ id: string; status: string }>(
    `/applications/${applicationId}/approve-verification`,
  )
  return data
}

export async function requestCorrection(
  applicationId: string,
  note: string,
): Promise<{ id: string; status: string }> {
  const { data } = await client.post<{ id: string; status: string }>(
    `/applications/${applicationId}/request-correction`,
    { note },
  )
  return data
}

export async function rejectStaffApplication(
  applicationId: string,
  reason_code: RejectionReasonCode,
  note: string,
): Promise<{ id: string; status: string }> {
  const { data } = await client.post<{ id: string; status: string }>(
    `/applications/${applicationId}/reject`,
    { reason_code, note },
  )
  return data
}

// ---------------------------------------------------------------------------
// SPEC-007: Results publication
// ---------------------------------------------------------------------------

export async function getResults(
  periodId: string,
  programId: string,
): Promise<ResultsResponse> {
  const { data } = await client.get<ResultsResponse>(`/results/${periodId}/${programId}`)
  return data
}

export async function publishResults(
  periodId: string,
  programId: string,
): Promise<PublishResultsResponse> {
  const { data } = await client.post<PublishResultsResponse>(
    `/results/${periodId}/${programId}/publish`,
  )
  return data
}
