import type { AppStatus, Document, EligibilityCheck } from './application'

export interface ApplicantResult {
  application_id: string
  position: number
  composite_score: number
  first_name?: string
  last_name?: string
  email?: string
}

export type RankingStatus = 'DRAFT' | 'APPROVED' | 'PUBLISHED'

export interface ResultsResponse {
  ranking_id: string
  status: RankingStatus
  published_at: string | null
  primary: ApplicantResult[]
  waitlisted: ApplicantResult[]
}

export interface PublishResultsResponse {
  announced_count: number
}

export interface AutoValidationResult {
  doc_type: string
  check: string
  passed: boolean
  detail?: string | null
}

export interface StaffApplicationSummary {
  id: string
  program_id: string
  period_id: string
  status: AppStatus
  tracking_number: string | null
  submitted_at: string | null
  created_at: string
  applicant_name?: string | null
  applicant_email?: string | null
  auto_validation_results: AutoValidationResult[]
}

export interface StaffApplicationDetail {
  id: string
  applicant_id: string
  program_id: string
  period_id: string
  status: AppStatus
  tracking_number: string | null
  submitted_at: string | null
  created_at: string
  updated_at: string
  progress: {
    tracking_number: string | null
    current_status: AppStatus
    steps: { step: string; completed: boolean; active: boolean; pending: boolean }[]
    percentage: number
    is_terminal: boolean
  }
  eligibility_checks: EligibilityCheck[]
  applicant_name?: string | null
  applicant_email?: string | null
  documents: Document[]
}

export const REJECTION_REASON_CODES = [
  'INVALID_DOCUMENT',
  'FRAUDULENT_DOCUMENT',
  'DUPLICATE_APPLICATION',
  'MISSED_DEADLINE',
  'OTHER',
] as const

export type RejectionReasonCode = (typeof REJECTION_REASON_CODES)[number]
