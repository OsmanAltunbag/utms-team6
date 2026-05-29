import { useEffect, useState } from 'react'
import { Mail, AlertCircle, Clock, CheckCircle } from 'lucide-react'
import { getNotificationLog } from '../api/applications'
import type { NotificationLogEntry } from '../types/notification'
import Spinner from './Spinner'

function StatusIcon({ status }: { status: string }) {
  if (status === 'SENT') return <CheckCircle className="w-4 h-4 text-green-600" />
  if (status === 'FAILED') return <AlertCircle className="w-4 h-4 text-red-600" />
  return <Clock className="w-4 h-4 text-yellow-600" />
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString()
}

export function NotificationLogPanel({ applicationId }: { applicationId: string | null }) {
  const [entries, setEntries] = useState<NotificationLogEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!applicationId) {
      setEntries([])
      return
    }
    setLoading(true)
    setError(null)
    getNotificationLog(applicationId)
      .then((res) => setEntries(res.notifications))
      .catch(() => setError('Failed to load notification log.'))
      .finally(() => setLoading(false))
  }, [applicationId])

  if (!applicationId) {
    return (
      <p className="text-gray-500 text-sm">Select an application to view notifications.</p>
    )
  }

  if (loading) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    )
  }

  if (error) {
    return <p className="text-red-600 text-sm">{error}</p>
  }

  if (entries.length === 0) {
    return <p className="text-gray-500 text-sm">No notifications sent yet.</p>
  }

  return (
    <div className="space-y-3">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 bg-gray-50"
        >
          <Mail className="w-4 h-4 text-indigo-500 mt-0.5 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-gray-900 truncate">
                {entry.subject ?? 'Notification'}
              </p>
              <div className="flex items-center gap-1 flex-shrink-0">
                <StatusIcon status={entry.status} />
                <span className="text-xs text-gray-500">{entry.status}</span>
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              {entry.sent_at
                ? `Sent ${formatDate(entry.sent_at)}`
                : `Queued ${formatDate(entry.created_at)}`}
              {entry.retry_count > 0 && ` · ${entry.retry_count} retries`}
            </p>
            {entry.template_name && (
              <p className="text-xs text-gray-400 mt-0.5">Template: {entry.template_name}</p>
            )}
            {entry.error_message && (
              <p className="text-xs text-red-600 mt-1">{entry.error_message}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}
