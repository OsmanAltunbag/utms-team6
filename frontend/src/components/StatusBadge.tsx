interface StatusBadgeProps {
  status: string
}

const statusStyles: Record<string, string> = {
  // Application lifecycle statuses (keys match status.toLowerCase())
  draft: 'bg-gray-100 text-gray-600',
  submitted: 'bg-indigo-100 text-indigo-800',
  under_review: 'bg-yellow-100 text-yellow-800',
  english_review: 'bg-purple-100 text-purple-800',
  dept_eval: 'bg-blue-100 text-blue-800',
  ranking: 'bg-cyan-100 text-cyan-800',
  dean_approved: 'bg-emerald-100 text-emerald-800',
  announced: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  correction_requested: 'bg-orange-100 text-orange-800',
}

const statusLabels: Record<string, string> = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under Review',
  english_review: 'English Review',
  dept_eval: 'Dept. Evaluation',
  ranking: 'Ready for Ranking',
  dean_approved: "Dean's Approval",
  announced: 'Announced',
  rejected: 'Rejected',
  correction_requested: 'Correction Requested',
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const key = status.toLowerCase()
  const style = statusStyles[key] ?? 'bg-gray-100 text-gray-600'
  const label = statusLabels[key] ?? status
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style}`}>
      {label}
    </span>
  )
}
