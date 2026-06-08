import { useState, useEffect, useCallback, useMemo } from 'react'
import toast from 'react-hot-toast'
import {
  GraduationCap, Languages, Trophy, CheckCircle, XCircle, FileText, Eye, LogOut,
} from 'lucide-react'
import Spinner from '../components/Spinner'
import { extractErrorMessage, getMe } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import {
  listYdyoApplications,
  approveEnglish,
  routeToExam,
  publishPendingExamResults,
  type YdyoApplicationSummary,
} from '../api/ydyo'
import { Bell } from 'lucide-react'

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Required score thresholds per exam type (hardcoded YDYO criteria). */
const REQUIRED_SCORE: Record<string, number> = {
  TOEFL_IBT: 80,
  TOEFL: 80,
  IELTS: 6.5,
  YDS: 65,
  YOKDIL: 65,
  IZTECH_EXAM: 70,
}

const EXAM_TYPE_LABELS: Record<string, string> = {
  TOEFL_IBT: 'TOEFL iBT',
  TOEFL: 'TOEFL',
  IELTS: 'IELTS',
  YDS: 'YDS',
  YOKDIL: 'YÖKDİL',
  IZTECH_EXAM: 'IYTE Exam',
}

function examLabel(code: string | undefined | null): string {
  if (!code) return '—'
  return EXAM_TYPE_LABELS[code] ?? code
}

function requiredFor(code: string | undefined | null): string {
  if (!code) return '—'
  const r = REQUIRED_SCORE[code]
  return r == null ? '—' : String(r)
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

type Tab = 'english' | 'exam-results'

// ---------------------------------------------------------------------------
// Sidebar (Figma-faithful: brand → user → nav → stats)
// ---------------------------------------------------------------------------

function YdyoSidebar({
  userName, tab, setTab, pending, approved, rejected, onLogout,
}: {
  userName: string
  tab: Tab
  setTab: (t: Tab) => void
  pending: number
  approved: number
  rejected: number
  onLogout: () => void
}) {
  return (
    <aside className="w-64 bg-indigo-900 text-white min-h-screen p-6 flex flex-col flex-shrink-0">
      {/* Brand */}
      <div className="flex items-center gap-2 mb-6">
        <GraduationCap className="w-7 h-7" />
        <span className="text-sm font-semibold tracking-wide">UTMS</span>
      </div>

      {/* User block */}
      <div className="border-t border-indigo-700 pt-4 mb-6">
        <p className="text-indigo-300 text-xs mb-1">Logged in as</p>
        <p className="font-medium text-sm truncate">{userName}</p>
        <p className="text-indigo-300 text-xs mt-1">Foreign Languages Office</p>
      </div>

      {/* Nav */}
      <nav className="space-y-2 mb-8">
        <button
          onClick={() => setTab('english')}
          className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm transition-colors ${
            tab === 'english'
              ? 'bg-indigo-500/30 text-white'
              : 'text-indigo-200 hover:bg-indigo-800/60'
          }`}
        >
          <Languages className="w-5 h-5 flex-shrink-0" />
          English Proficiency
        </button>
        <button
          onClick={() => setTab('exam-results')}
          className={`flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm transition-colors ${
            tab === 'exam-results'
              ? 'bg-indigo-500/30 text-white'
              : 'text-indigo-200 hover:bg-indigo-800/60'
          }`}
        >
          <Trophy className="w-5 h-5 flex-shrink-0" />
          YDYO Exam Results
        </button>
      </nav>

      {/* Stats */}
      <div className="space-y-3 mb-auto">
        <SidebarStat label="Pending Verification" value={pending}  accent="bg-indigo-500/20 text-white" />
        <SidebarStat label="Approved"             value={approved} accent="bg-emerald-500/20 text-emerald-200" />
        <SidebarStat label="Rejected"             value={rejected} accent="bg-rose-500/20 text-rose-200" />
      </div>

      <button
        onClick={onLogout}
        className="flex items-center gap-2 text-indigo-300 hover:text-white transition-colors mt-6 pt-4 border-t border-indigo-700"
      >
        <LogOut className="w-4 h-4" />
        <span className="text-sm">Logout</span>
      </button>
    </aside>
  )
}

function SidebarStat({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div className={`rounded-lg px-4 py-3 ${accent}`}>
      <p className="text-[11px] uppercase tracking-wider opacity-80">{label}</p>
      <p className="text-xl font-semibold mt-0.5">{value}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Status badge (top-right of each card)
// ---------------------------------------------------------------------------

function ApplicationStatusBadge({ app }: { app: YdyoApplicationSummary }) {
  const r = app.english_review
  if (r?.approved === true) {
    return <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700">Approved</span>
  }
  if (r?.approved === false) {
    return <span className="px-3 py-1 rounded-full text-xs font-medium bg-rose-100 text-rose-700">Rejected</span>
  }
  if (r?.must_take_exam) {
    return <span className="px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-700">Awaiting YDYO Exam</span>
  }
  return <span className="px-3 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700">Pending Verification</span>
}

// ---------------------------------------------------------------------------
// Application card
// ---------------------------------------------------------------------------

function ApplicationCard({
  app, onAfterAction,
}: {
  app: YdyoApplicationSummary
  onAfterAction: () => void
}) {
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState<null | 'approve' | 'reject'>(null)

  const cert = app.certificate
  // Informational only — never block the decision buttons
  const examTypeCode = cert?.extracted_data?.exam_type ?? app.english_review?.exam_type ?? null
  const scoreVal = cert?.extracted_data?.score ?? app.english_review?.exam_score ?? null
  const expires = cert?.extracted_data?.expires_on ?? null
  const expired = !!expires && new Date(expires) < new Date()

  const reviewApproved = app.english_review?.approved
  const mustTakeExam = app.english_review?.must_take_exam === true && reviewApproved == null
  const isPending =
    reviewApproved == null && !mustTakeExam && app.status === 'ENGLISH_REVIEW'

  function openCertPdf() {
    if (!cert) return
    window.open(`/api/documents/${cert.id}/stream`, '_blank', 'noopener,noreferrer')
  }

  async function handleApprove() {
    setBusy('approve')
    try {
      await approveEnglish(app.id, notes || undefined, examTypeCode ?? undefined, scoreVal != null ? Number(scoreVal) : undefined)
      toast.success('English proficiency approved. Application routed to Dean\'s Office.')
      onAfterAction()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function handleMustTakeExam() {
    setBusy('reject')
    try {
      await routeToExam(app.id, notes || 'Certificate insufficient — routed to YDYO proficiency exam.')
      toast.success('Routed to YDYO proficiency exam. Applicant will be notified.')
      onAfterAction()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-4">
      {/* Header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h3 className="text-base font-semibold text-gray-900">{app.applicant ?? '—'}</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Application ID: <span className="font-mono">{app.tracking_number ?? app.id.slice(0, 8)}</span>
          </p>
        </div>
        <ApplicationStatusBadge app={app} />
      </div>

      {/* Field grid (5 columns on desktop) */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 mb-4">
        <Field label="Target Department" value={app.program ?? '—'} />
        <Field label="Language" value="English" />
        <Field label="Test Type" value={examLabel(examTypeCode)} valueColor="text-rose-600" />
        <Field label="Score" value={scoreVal != null ? String(scoreVal) : '—'} valueColor="text-emerald-600" />
        <Field label="Required Score" value={requiredFor(examTypeCode)} />
      </div>

      {/* Cert links */}
      {cert ? (
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2 text-sm text-emerald-700">
            <CheckCircle className="w-4 h-4" />
            <span>{cert.file_name ?? 'Language certificate uploaded'}</span>
          </div>
          <button
            onClick={openCertPdf}
            className="flex items-center gap-2 text-sm text-indigo-600 hover:text-indigo-800 font-medium"
          >
            <Eye className="w-4 h-4" />
            Open Certificate PDF
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-2 text-sm text-amber-700 mb-4">
          <XCircle className="w-4 h-4" />
          <span>No language certificate uploaded</span>
        </div>
      )}

      {/* Action area */}
      {isPending ? (
        <>
          <label className="block text-xs font-medium text-gray-600 mb-1">Verification Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add notes about language requirement verification"
            rows={2}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-3"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <button
              onClick={handleApprove}
              disabled={busy !== null}
              className="flex items-center justify-center gap-2 px-4 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {busy === 'approve' ? <Spinner /> : <CheckCircle className="w-4 h-4" />}
              Approve English Proficiency
            </button>
            <button
              onClick={handleMustTakeExam}
              disabled={busy !== null}
              className="flex items-center justify-center gap-2 px-4 py-3 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {busy === 'reject' ? <Spinner /> : <XCircle className="w-4 h-4" />}
              Must Take Exam
            </button>
          </div>
        </>
      ) : reviewApproved === true ? (
        <div className="flex items-start gap-2 bg-emerald-50 border border-emerald-200 rounded-lg p-3 text-sm text-emerald-800">
          <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>English requirement satisfied. Application routed to Dean's Office. Notification sent to applicant.</span>
        </div>
      ) : reviewApproved === false ? (
        <div className="flex items-start gap-2 bg-rose-50 border border-rose-200 rounded-lg p-3 text-sm text-rose-800">
          <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>
            English requirement not met &mdash; applicant eliminated.
            {app.english_review?.notes ? ` Reason: ${app.english_review.notes}` : ''}
          </span>
        </div>
      ) : (
        <div className="flex items-start gap-2 bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm text-blue-800">
          <FileText className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <span>
            Routed to the YDYO proficiency exam. Publish the exam result on the
            "YDYO Exam Results" tab once the applicant has taken the exam.
            {app.english_review?.notes ? ` Note: ${app.english_review.notes}` : ''}
          </span>
        </div>
      )}
    </div>
  )
}

function Field({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-gray-500 mb-1">{label}</p>
      <p className={`text-sm font-medium ${valueColor ?? 'text-gray-900'}`}>{value}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// English Proficiency view
// ---------------------------------------------------------------------------

function EnglishProficiencyView({
  apps, loading, onAfterAction,
}: {
  apps: YdyoApplicationSummary[]
  loading: boolean
  onAfterAction: () => void
}) {
  const sorted = useMemo(() => {
    const order = (a: YdyoApplicationSummary) => {
      const r = a.english_review
      if (r?.approved == null && !r?.must_take_exam && a.status === 'ENGLISH_REVIEW') return 0
      if (r?.must_take_exam && r?.approved == null) return 1
      if (r?.approved === true) return 2
      if (r?.approved === false) return 3
      return 4
    }
    return [...apps].sort((a, b) => order(a) - order(b))
  }, [apps])

  return (
    <>
      <h1 className="text-lg font-semibold text-gray-700 mb-6">
        Foreign Languages Office &nbsp;—&nbsp; English Proficiency Review
      </h1>

      {loading ? (
        <div className="flex justify-center py-16"><Spinner /></div>
      ) : sorted.length === 0 ? (
        <div className="bg-white rounded-xl shadow-sm p-10 text-center text-sm text-gray-500">
          No applications in your purview yet.
        </div>
      ) : (
        sorted.map((a) => (
          <ApplicationCard key={a.id} app={a} onAfterAction={onAfterAction} />
        ))
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// YDYO Exam Results view (placeholder for SPEC-015)
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// UC-05-02 — Announce English Proficiency Exam Results
// ---------------------------------------------------------------------------

function ExamResultsView({
  apps, onAfterAction,
}: {
  apps: YdyoApplicationSummary[]
  onAfterAction: () => void
}) {
  // Every applicant routed to the YDYO proficiency exam with a recorded
  // score. Includes both not-yet-published and already-published rows
  // so the Figma table stays populated for the full exam cycle.
  const rows = apps.filter(
    (a) =>
      a.english_review?.must_take_exam &&
      a.english_review?.exam_score != null,
  )
  const pendingCount = rows.filter((a) => !a.english_review?.published_at).length

  // Pass/Fail computed automatically from the score (>= 70 for IZTECH_EXAM).
  const passCount = rows.filter((a) => {
    const s = a.english_review?.exam_score ?? -Infinity
    const req = requiredScoreNumeric(a.english_review?.exam_type) ?? Infinity
    return s >= req
  }).length
  const failCount = rows.length - passCount

  const [publishing, setPublishing] = useState(false)

  async function handlePublish() {
    if (pendingCount === 0) {
      toast('No new results to publish.')
      return
    }
    setPublishing(true)
    try {
      const r = await publishPendingExamResults()
      toast.success(
        `${r.processed} result${r.processed === 1 ? '' : 's'} announced — ${r.passed_count} Pass / ${r.failed_count} Fail.`,
      )
      onAfterAction()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setPublishing(false)
    }
  }

  return (
    <>
      {/* Header — title + subtitle + single Publish Results button */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">YDYO Exam Results</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Review and publish YDYO English proficiency exam results
          </p>
        </div>
        <button
          onClick={handlePublish}
          disabled={publishing || pendingCount === 0}
          className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg shadow-sm"
        >
          {publishing ? <Spinner /> : <Bell className="w-4 h-4" />}
          Publish Results
        </button>
      </div>

      {/* Results table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden mb-6">
        {rows.length === 0 ? (
          <div className="p-10 text-center text-sm text-gray-500">
            No exam results recorded yet.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3 text-left">Application ID</th>
                <th className="px-6 py-3 text-left">Applicant Name</th>
                <th className="px-6 py-3 text-left">Exam Date</th>
                <th className="px-6 py-3 text-left">Score</th>
                <th className="px-6 py-3 text-left">Required</th>
                <th className="px-6 py-3 text-left">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((a) => {
                const score = a.english_review?.exam_score
                const required = requiredScoreNumeric(a.english_review?.exam_type) ?? 70
                const passed = score != null && score >= required
                return (
                  <tr key={a.id}>
                    <td className="px-6 py-4 font-mono text-xs text-gray-700">
                      {a.tracking_number ?? a.id.slice(0, 8)}
                    </td>
                    <td className="px-6 py-4 text-gray-900">{a.applicant ?? '—'}</td>
                    <td className="px-6 py-4 text-gray-600">
                      {a.english_review?.exam_date ?? '—'}
                    </td>
                    <td className={`px-6 py-4 font-medium ${passed ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {score}
                    </td>
                    <td className="px-6 py-4 text-gray-700">{required}</td>
                    <td className="px-6 py-4">
                      <span
                        className={`inline-flex items-center px-3 py-0.5 rounded-full text-xs font-medium ${
                          passed
                            ? 'bg-emerald-100 text-emerald-700'
                            : 'bg-rose-100 text-rose-700'
                        }`}
                      >
                        {passed ? 'Pass' : 'Fail'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Result Statistics card */}
      <div className="bg-indigo-50/60 border border-indigo-100 rounded-xl p-5">
        <p className="text-sm font-semibold text-gray-700 mb-3">Result Statistics</p>
        <div className="grid grid-cols-3 gap-6">
          <StatItem label="Total Examined" value={rows.length} color="text-indigo-700" />
          <StatItem label="Pass"           value={passCount}   color="text-emerald-700" />
          <StatItem label="Fail"           value={failCount}   color="text-rose-700" />
        </div>
      </div>
    </>
  )
}

function StatItem({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`text-2xl font-semibold ${color}`}>{value}</p>
    </div>
  )
}

function requiredScoreNumeric(examType: string | null | undefined): number | null {
  if (!examType) return null
  const v = REQUIRED_SCORE[examType]
  return v ?? null
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

const YDYO_ALLOWED_ROLES = new Set(['YDYO', 'SYSTEM_ADMIN'])

export default function YDYODashboard({
  userName, onLogout,
}: {
  userName: string; onLogout: () => void
}) {
  const { setAuth, clearAuth } = useAuth()
  const [tab, setTab] = useState<Tab>('english')
  const [apps, setApps] = useState<YdyoApplicationSummary[]>([])
  const [loading, setLoading] = useState(true)

  // Keep sessionStorage in sync with the HttpOnly cookie so a stale role
  // (e.g. YDYO UI after logging in as Dean in another tab) cannot linger.
  useEffect(() => {
    let cancelled = false
    getMe()
      .then((me) => {
        if (cancelled) return
        if (!YDYO_ALLOWED_ROLES.has(me.role)) {
          toast.error(
            `Signed in as ${me.role}. Log out and use ydyo@iyte.edu.tr to review English proficiency.`,
          )
          clearAuth()
          window.location.href = '/login'
          return
        }
        setAuth(me.role, `${me.first_name} ${me.last_name}`, me.must_change_password)
      })
      .catch(() => {
        if (!cancelled) {
          clearAuth()
          window.location.href = '/login'
        }
      })
    return () => { cancelled = true }
  }, [setAuth, clearAuth])

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      const data = await listYdyoApplications('all')
      setApps(data)
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Sidebar counts: cert-verification track only (UC-05-01).
  // Excludes exam-track rows so UC-05-02 publications don't shift these.
  const pending  = apps.filter((a) => !a.english_review && a.status === 'ENGLISH_REVIEW').length
  const approved = apps.filter(
    (a) => a.english_review?.approved === true && !a.english_review?.must_take_exam,
  ).length
  const rejected = apps.filter(
    (a) => a.english_review?.approved === false && !a.english_review?.must_take_exam,
  ).length

  return (
    <div className="flex flex-1 min-h-screen">
      <YdyoSidebar
        userName={userName}
        tab={tab}
        setTab={setTab}
        pending={pending}
        approved={approved}
        rejected={rejected}
        onLogout={onLogout}
      />
      <main className="flex-1 p-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          {tab === 'english' && (
            <EnglishProficiencyView apps={apps} loading={loading} onAfterAction={refresh} />
          )}
          {tab === 'exam-results' && <ExamResultsView apps={apps} onAfterAction={refresh} />}
        </div>
      </main>
    </div>
  )
}
