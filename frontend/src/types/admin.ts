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

export interface RoleUpdatePayload {
  role: UserRole
}
