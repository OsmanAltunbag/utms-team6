interface StatusBadgeProps {
  status: string
}

const statusStyles: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  pending: 'bg-blue-100 text-blue-800',
  waiting: 'bg-gray-100 text-gray-600',
  rejected: 'bg-red-100 text-red-800',
  'under review': 'bg-yellow-100 text-yellow-800',
  submitted: 'bg-indigo-100 text-indigo-800',
  verified: 'bg-emerald-100 text-emerald-800',
  correction_requested: 'bg-orange-100 text-orange-800',
  'foreign languages review': 'bg-purple-100 text-purple-800',
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const key = status.toLowerCase()
  const style = statusStyles[key] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {status}
    </span>
  )
}
