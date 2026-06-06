import axios from 'axios'
import type { ApplicationDetail, ApplicationSummary } from '../types/application'

const client = axios.create({
  baseURL: '/api/staff',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        await axios.post('/api/auth/refresh', {}, { withCredentials: true })
        return client(original)
      } catch {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export type RejectionReasonCode =
  | 'INVALID_DOCUMENT'
  | 'FRAUDULENT_DOCUMENT'
  | 'DUPLICATE_APPLICATION'
  | 'MISSED_DEADLINE'
  | 'OTHER'

export const REJECTION_REASON_CODES: RejectionReasonCode[] = [
  'INVALID_DOCUMENT',
  'FRAUDULENT_DOCUMENT',
  'DUPLICATE_APPLICATION',
  'MISSED_DEADLINE',
  'OTHER',
]

interface OfficerActionResult {
  id: string
  status: string
}

// SPEC-006 / UC-03-01: Student Affairs document oversight
export async function listStaffApplications(): Promise<ApplicationSummary[]> {
  const { data } = await client.get<ApplicationSummary[]>('/applications')
  return data
}

export async function getStaffApplication(applicationId: string): Promise<ApplicationDetail> {
  const { data } = await client.get<ApplicationDetail>(`/applications/${applicationId}`)
  return data
}

export async function approveVerification(applicationId: string): Promise<OfficerActionResult> {
  const { data } = await client.post<OfficerActionResult>(
    `/applications/${applicationId}/approve-verification`,
  )
  return data
}

export async function requestCorrection(
  applicationId: string,
  note: string,
): Promise<OfficerActionResult> {
  const { data } = await client.post<OfficerActionResult>(
    `/applications/${applicationId}/request-correction`,
    { note },
  )
  return data
}

export async function rejectApplication(
  applicationId: string,
  reasonCode: RejectionReasonCode,
  note: string,
): Promise<OfficerActionResult> {
  const { data } = await client.post<OfficerActionResult>(
    `/applications/${applicationId}/reject`,
    { reason_code: reasonCode, note },
  )
  return data
}
