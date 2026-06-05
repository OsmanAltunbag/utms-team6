export interface YGKApplicationSummary {
  id: string
  tracking_number: string
  status: string
  program: string | null
  applicant: string | null
}

export interface YGKAcademicRecord {
  gpa_4: number | null
  gpa_100: number | null
  yks_score: number | null
  is_locked: boolean
  source: string | null
}

export interface YGKDocument {
  id: string
  doc_type: string
  status: string
}

export interface YGKEvaluationDetail {
  application_id: string
  status: string
  academic_record: YGKAcademicRecord | null
  gpa_100_converted: number | null
  documents: YGKDocument[]
}

export interface ScoreVerifyResult {
  id: string
  gpa_4: number | null
  gpa_100: number | null
  yks_score: number | null
  is_locked: boolean
  application_status?: string
}

export type CorrectionField = 'yks_score' | 'gpa_4'

export interface DeptConditionRequirement {
  rule_key: string
  required_value: string | null
  description: string | null
  result: 'Met' | 'Not Met' | 'Pending'
  detail: string | null
}

export interface DeptConditionsResponse {
  requirements: DeptConditionRequirement[]
}

export interface EvaluateConditionsResult {
  evaluation: {
    passed: boolean
    notes: string | null
    evaluated_at: string
  }
  checks: Array<{ rule_key: string; passed: boolean; detail: string | null }>
}

export interface ManualCourseMappingResult {
  id: string
  rule_key: string
  passed: boolean
  detail: string | null
}
