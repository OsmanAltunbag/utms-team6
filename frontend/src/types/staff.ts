import type { AppStatus, DocType, Document, EligibilityCheck } from './application'
import type { ProgressStep } from './application'

export interface AutoValidationResult {
  rule_key: string
  passed: boolean
  detail: string | null
}

export interface ApplicantProfile {
  first_name: string
  last_name: string
  email: string
  national_id: string
  phone: string | null
}

export interface StaffApplicationSummary {
  id: string
  program_id: string
  period_id: string
  status: AppStatus
  display_status: string
  tracking_number: string | null
  submitted_at: string | null
  created_at: string
  auto_validation_results: AutoValidationResult[]
}

export interface StaffApplicationDetail {
  id: string
  applicant_id: string
  program_id: string
  period_id: string
  status: AppStatus
  display_status: string
  tracking_number: string | null
  submitted_at: string | null
  created_at: string
  updated_at: string
  correction_deadline: string | null
  progress: {
    tracking_number: string | null
    current_status: string
    steps: ProgressStep[]
    percentage: number
    is_terminal: boolean
  }
  applicant: ApplicantProfile
  eligibility_checks: EligibilityCheck[]
  documents: Document[]
  auto_validation_results: AutoValidationResult[]
}

export interface OfficerActionResult {
  application_id: string
  status: string
  display_status: string
}

export interface DocumentPreviewResult {
  preview_url: string
  viewable: boolean
  content_type: string
  error_message: string | null
}

export type RejectionReasonCode =
  | 'INVALID_DOCUMENT'
  | 'FRAUDULENT_DOCUMENT'
  | 'DUPLICATE_APPLICATION'
  | 'MISSED_DEADLINE'
  | 'OTHER'

export const REJECTION_REASON_LABELS: Record<RejectionReasonCode, string> = {
  INVALID_DOCUMENT: 'Invalid document',
  FRAUDULENT_DOCUMENT: 'Fraudulent document',
  DUPLICATE_APPLICATION: 'Duplicate application',
  MISSED_DEADLINE: 'Missed deadline',
  OTHER: 'Other',
}

export interface PublishResultsResult {
  announced_count: number
  notifications_enqueued: number
  published_at: string
}

export interface ApplicantResultEntry {
  application_id: string
  tracking_number: string | null
  first_name: string
  last_name: string
  email: string
  position: number
  composite_score: number
  result_label: string
}

export interface ResultsListResponse {
  period_id: string
  program_id: string
  program_name: string
  period_label: string
  ranking_status: string
  published_at: string | null
  is_read_only: boolean
  can_publish: boolean
  primary: ApplicantResultEntry[]
  waitlisted: ApplicantResultEntry[]
}
