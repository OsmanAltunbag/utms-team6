export type AppStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'UNDER_REVIEW'
  | 'ENGLISH_REVIEW'
  | 'DEPT_EVAL'
  | 'RANKING'
  | 'DEAN_APPROVED'
  | 'ANNOUNCED'
  | 'REJECTED'
  | 'CORRECTION_REQUESTED'

export type DocType =
  | 'TRANSCRIPT'
  | 'YKS_RESULT'
  | 'LANGUAGE_CERT'
  | 'ID_COPY'
  | 'MILITARY_STATUS'
  | 'DISCIPLINE_RECORD'
  | 'OTHER'

export type DocStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'CORRECTION_REQUESTED'

export interface ApplicationSummary {
  id: string
  program_id: string
  period_id: string
  status: AppStatus
  tracking_number: string | null
  submitted_at: string | null
  created_at: string
}

export interface ProgressStep {
  step: string
  completed: boolean
  active: boolean
  pending: boolean
}

export interface ApplicationDetail extends ApplicationSummary {
  applicant_id: string
  updated_at: string
  progress: {
    tracking_number: string | null
    current_status: AppStatus
    steps: ProgressStep[]
    percentage: number
    is_terminal: boolean
  }
  eligibility_checks: EligibilityCheck[]
}

export interface EligibilityCheck {
  rule_key: string
  passed: boolean
  detail: string | null
}

export interface AcademicRecord {
  institution: string | null
  gpa_4: number | null
  gpa_100: number | null
  yks_score: number | null
  credits_completed: number | null
  fetched_at: string | null
  source: string | null
  errors: string[] | null
}

export interface Document {
  id: string
  application_id: string
  doc_type: DocType
  file_name: string
  file_size_bytes: number | null
  status: DocStatus
  uploaded_at: string
  extracted_data: Record<string, unknown> | null
  extraction_confirmed: boolean
}

export interface PresignedUploadResult {
  upload_url: string
  object_key: string
}

export interface SubmitResult {
  tracking_number: string
  status: AppStatus
}

export interface PipelineStage {
  name: string
  label_tr: string
  label_en: string
  completed: boolean
  active: boolean
}

export interface HistoryEntry {
  status: AppStatus
  changed_at: string
  changed_by_role: string | null
  note: string | null
}

export interface ApplicationStatus {
  tracking_number: string | null
  status: AppStatus
  progress: {
    stages: PipelineStage[]
    current_stage: string
  }
  history: HistoryEntry[]
  result: { outcome: string; reason: string | null } | null
}

export interface NotificationMessage {
  id: string
  subject: string | null
  message: string
  status: 'PENDING' | 'SENT' | 'FAILED'
  sent_at: string | null
  created_at: string
}
