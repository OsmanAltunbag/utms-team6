import axios from 'axios'
import type {
  DocumentPreviewResult,
  OfficerActionResult,
  PublishResultsResult,
  RejectionReasonCode,
  ResultsListResponse,
  StaffApplicationDetail,
  StaffApplicationSummary,
} from '../types/staff'

const client = axios.create({
  baseURL: '/api/staff',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

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

export async function getStaffDocumentPreview(
  applicationId: string,
  documentId: string,
): Promise<DocumentPreviewResult> {
  const { data } = await client.get<DocumentPreviewResult>(
    `/applications/${applicationId}/documents/${documentId}/preview`,
  )
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
  reason_code: RejectionReasonCode,
  note: string,
): Promise<OfficerActionResult> {
  const { data } = await client.post<OfficerActionResult>(
    `/applications/${applicationId}/reject`,
    { reason_code, note },
  )
  return data
}

export async function getResultsList(
  periodId: string,
  programId: string,
): Promise<ResultsListResponse> {
  const { data } = await client.get<ResultsListResponse>(`/results/${periodId}/${programId}`)
  return data
}

export async function publishResults(
  periodId: string,
  programId: string,
): Promise<PublishResultsResult> {
  const { data } = await client.post<PublishResultsResult>(`/results/${periodId}/${programId}/publish`)
  return data
}
