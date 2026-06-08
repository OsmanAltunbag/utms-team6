export type UserRole =
  | 'APPLICANT'
  | 'STUDENT_AFFAIRS'
  | 'TRANSFER_COMMISSION'
  | 'YDYO'
  | 'DEAN_OFFICE'
  | 'SYSTEM_ADMIN'

export interface StaffMember {
  id: string
  email: string
  first_name: string
  last_name: string
  role: UserRole
  department: string | null
  title: string | null
  is_active: boolean
  created_at: string
}

export interface StaffCreatePayload {
  email: string
  first_name: string
  last_name: string
  role: UserRole
  department?: string
  title?: string
}

export interface StaffCreateResponse extends StaffMember {
  temp_password?: string | null
}

export interface RoleUpdatePayload {
  role: UserRole
}

// SPEC-018
export interface ApplicationPeriod {
  id: string
  label: string
  opens_at: string
  closes_at: string
  is_active: boolean
  created_by: string | null
  created_at: string
}

export interface PeriodCreatePayload {
  label: string
  opens_at: string
  closes_at: string
}

export interface PeriodExtendPayload {
  new_closes_at: string
}

export interface PeriodUpdatePayload {
  label?: string
  opens_at?: string
  closes_at?: string
}

// SPEC-019
export type RuleKey =
  | 'MIN_GPA'
  | 'MIN_YKS'
  | 'MIN_CREDITS'
  | 'CORE_COURSE_GRADE'
  | 'PORTFOLIO_REQUIRED'
  | 'REQUIRED_DOC'

export interface DepartmentCondition {
  id: string
  program_id: string
  rule_key: RuleKey
  rule_value: string
  description: string | null
  is_active: boolean
}

export interface ConditionCreatePayload {
  rule_key: RuleKey
  rule_value: string
  description?: string
}

export interface ConditionUpdatePayload {
  rule_value?: string
  is_active?: boolean
}
