import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Megaphone, RefreshCw } from 'lucide-react'
import { getResultsList, publishResults } from '../api/staff'
import { listOpenPeriods, listPrograms } from '../api/applications'
import { extractErrorMessage } from '../api/auth'
import type { PeriodOption, ProgramOption } from '../api/applications'
import type { ApplicantResultEntry, ResultsListResponse } from '../types/staff'
import Spinner from './Spinner'

function ResultTable({
  title,
  subtitle,
  rows,
}: {
  title: string
  subtitle: string
  rows: ApplicantResultEntry[]
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 bg-gray-50">
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        <p className="text-xs text-gray-500">{subtitle}</p>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-gray-500 p-4">No candidates on this list.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                <th className="px-4 py-2 font-medium">#</th>
                <th className="px-4 py-2 font-medium">Tracking</th>
                <th className="px-4 py-2 font-medium">Applicant</th>
                <th className="px-4 py-2 font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.application_id} className="border-b border-gray-50">
                  <td className="px-4 py-2">{row.position}</td>
                  <td className="px-4 py-2 font-mono text-xs">{row.tracking_number ?? '—'}</td>
                  <td className="px-4 py-2">
                    {row.first_name} {row.last_name}
                    <span className="block text-xs text-gray-400">{row.email}</span>
                  </td>
                  <td className="px-4 py-2">{row.composite_score.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function ResultsAnnouncementPanel() {
  const [programs, setPrograms] = useState<ProgramOption[]>([])
  const [periods, setPeriods] = useState<PeriodOption[]>([])
  const [programId, setProgramId] = useState('')
  const [periodId, setPeriodId] = useState('')
  const [results, setResults] = useState<ResultsListResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  useEffect(() => {
    Promise.all([listPrograms(), listOpenPeriods()])
      .then(([p, per]) => {
        setPrograms(p)
        setPeriods(per)
        if (p.length > 0) setProgramId(p[0].id)
        if (per.length > 0) setPeriodId(per[0].id)
      })
      .catch(() => toast.error('Failed to load programs or periods'))
  }, [])

  const loadResults = useCallback(async () => {
    if (!programId || !periodId) return
    setLoading(true)
    try {
      const data = await getResultsList(periodId, programId)
      setResults(data)
    } catch (err) {
      setResults(null)
      toast.error(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [programId, periodId])

  useEffect(() => {
    if (programId && periodId) loadResults()
  }, [programId, periodId, loadResults])

  async function handlePublish() {
    if (!programId || !periodId) return
    setPublishing(true)
    try {
      const result = await publishResults(periodId, programId)
      toast.success(
        `Results published — ${result.announced_count} applicants notified (${result.notifications_enqueued} emails queued)`,
      )
      setShowConfirm(false)
      await loadResults()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setPublishing(false)
    }
  }

  const isPublished = results?.ranking_status === 'PUBLISHED'

  return (
    <div className="p-6 space-y-6 max-w-5xl">
      <div className="flex items-start justify-end">
        <button
          onClick={loadResults}
          className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
        >
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 max-w-xl">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Program</label>
          <select
            value={programId}
            onChange={(e) => setProgramId(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm"
          >
            {programs.map((p) => (
              <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">Period</label>
          <select
            value={periodId}
            onChange={(e) => setPeriodId(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm"
          >
            {periods.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Spinner /></div>
      ) : results ? (
        <>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="px-2 py-1 rounded-full bg-indigo-100 text-indigo-800 text-xs font-medium">
              {results.program_name} · {results.period_label}
            </span>
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
              isPublished ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
            }`}>
              {isPublished ? 'Published' : 'Pending Publication'}
            </span>
            {results.published_at && (
              <span className="text-gray-500 text-xs">
                Published {new Date(results.published_at).toLocaleString()}
              </span>
            )}
          </div>

          <ResultTable
            title="Primary List (Asil)"
            subtitle="Candidates accepted for transfer"
            rows={results.primary}
          />
          <ResultTable
            title="Waitlist (Yedek)"
            subtitle="Reserve candidates"
            rows={results.waitlisted}
          />

          {results.can_publish && (
            <div className="pt-4 border-t border-gray-200">
              <button
                onClick={() => setShowConfirm(true)}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700"
              >
                <Megaphone className="w-4 h-4" /> Notify Results
              </button>
              <p className="text-xs text-gray-500 mt-2">
                This action is irreversible. All applicants in RANKING status will be announced and notified by email.
              </p>
            </div>
          )}

          {isPublished && (
            <p className="text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg p-3">
              Results have been published. Applicants can view outcomes on their dashboard and will receive email notifications.
            </p>
          )}
        </>
      ) : (
        <p className="text-gray-500 text-sm">Select a program and period to load results.</p>
      )}

      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold mb-2">Confirm Result Publication</h3>
            <p className="text-sm text-gray-600 mb-4">
              You are about to permanently publish transfer results and send email notifications to all
              applicants. This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handlePublish}
                disabled={publishing}
                className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
              >
                {publishing ? <Spinner /> : 'Confirm & Notify'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
