export type NotificationStatus = 'PENDING' | 'SENT' | 'FAILED'

export interface NotificationLogEntry {
  id: string
  channel: string
  subject: string | null
  status: NotificationStatus
  retry_count: number
  sent_at: string | null
  created_at: string
  template_name: string | null
  error_message: string | null
}

export interface NotificationLogResponse {
  application_id: string
  notifications: NotificationLogEntry[]
}
