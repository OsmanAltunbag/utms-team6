import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import {
  FileText, CheckCircle, XCircle, AlertTriangle, Eye, RefreshCw, Mail, Megaphone,
} from 'lucide-react'
import {
  listStaffApplications,
  getStaffApplication,
  getStaffDocumentPreview,
  approveVerification,
  requestCorrection,
  rejectApplication,
} from '../api/staff'
import { extractErrorMessage } from '../api/auth'
import { getPreviewUrl } from '../api/applications'
import { Sidebar } from '../components/Sidebar'
import { StatusBadge } from '../components/StatusBadge'
import { DocumentPreviewModal } from '../components/DocumentPreviewModal'
import { NotificationLogPanel } from '../components/NotificationLogPanel'
import { ResultsAnnouncementPanel } from '../components/ResultsAnnouncementPanel'
import Spinner from '../components/Spinner'
import type { DocType, Document } from '../types/application'
import type {
  RejectionReasonCode,
  StaffApplicationDetail,
  StaffApplicationSummary,
} from '../types/staff'
import { REJECTION_REASON_LABELS } from '../types/staff'

const DOC_TYPE_LABELS: Record<DocType, string> = {
  TRANSCRIPT: 'Transcript',
  YKS_RESULT: 'YKS Score Report',
  LANGUAGE_CERT: 'Language Certificate',
  ID_COPY: 'ID Copy',
  MILITARY_STATUS: 'Military Status',
  DISCIPLINE_RECORD: 'Discipline Record',
  OTHER: 'Other',
}

interface StudentAffairsDashboardProps {
  userName: string
  onLogout: () => void
}

export default function StudentAffairsDashboard({ userName, onLogout }: StudentAffairsDashboardProps) {
  const [applications, setApplications] = useState<StaffApplicationSummary[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<StaffApplicationDetail | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('SUBMITTED')
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [showCorrectionModal, setShowCorrectionModal] = useState(false)
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [correctionNote, setCorrectionNote] = useState('')
  const [rejectReason, setRejectReason] = useState<RejectionReasonCode>('INVALID_DOCUMENT')
  const [rejectNote, setRejectNote] = useState('')
  const [activePanel, setActivePanel] = useState<'review' | 'notifications' | 'results'>('review')
  const [preview, setPreview] = useState<{
    open: boolean
    title: string
    streamUrl: string
    viewable: boolean
    contentType: string
    errorMessage: string | null
    loading: boolean
  }>({
    open: false,
    title: '',
    streamUrl: '',
    viewable: true,
    contentType: 'application/pdf',
    errorMessage: null,
    loading: false,
  })

  const loadList = useCallback(async () => {
    setLoadingList(true)
    try {
      const apps = await listStaffApplications({ status: statusFilter })
      setApplications(apps)
      setSelectedId((current) => {
        if (apps.length === 0) return null
        if (current && apps.some((a) => a.id === current)) return current
        return apps[0].id
      })
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setLoadingList(false)
    }
  }, [statusFilter])

  const loadDetail = useCallback(async (id: string) => {
    setLoadingDetail(true)
    try {
      const data = await getStaffApplication(id)
      setDetail(data)
    } catch (err) {
      toast.error(extractErrorMessage(err))
      setDetail(null)
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  useEffect(() => { loadList() }, [statusFilter])

  useEffect(() => {
    if (selectedId) loadDetail(selectedId)
    else setDetail(null)
  }, [selectedId, loadDetail])

  async function refresh() {
    await loadList()
    if (selectedId) await loadDetail(selectedId)
  }

  async function handleApprove() {
    if (!selectedId) return
    setActionLoading(true)
    try {
      const result = await approveVerification(selectedId)
      toast.success(`Application verified (${result.display_status})`)
      await refresh()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  async function handleRequestCorrection() {
    if (!selectedId || !correctionNote.trim()) {
      toast.error('Correction note is required')
      return
    }
    setActionLoading(true)
    try {
      await requestCorrection(selectedId, correctionNote.trim())
      toast.success('Correction requested — applicant notified')
      setShowCorrectionModal(false)
      setCorrectionNote('')
      await refresh()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  async function handleReject() {
    if (!selectedId) return
    setActionLoading(true)
    try {
      await rejectApplication(selectedId, rejectReason, rejectNote)
      toast.success('Application rejected — applicant notified')
      setShowRejectModal(false)
      setRejectNote('')
      await refresh()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setActionLoading(false)
    }
  }

  async function handlePreview(doc: Document) {
    if (!selectedId) return
    setPreview({
      open: true,
      title: DOC_TYPE_LABELS[doc.doc_type as DocType] ?? doc.file_name,
      streamUrl: getPreviewUrl(doc.id).preview_url,
      viewable: true,
      contentType: 'application/pdf',
      errorMessage: null,
      loading: true,
    })
    try {
      const result = await getStaffDocumentPreview(selectedId, doc.id)
      setPreview((p) => ({
        ...p,
        viewable: result.viewable,
        contentType: result.content_type,
        errorMessage: result.error_message,
        loading: false,
      }))
    } catch {
      setPreview((p) => ({
        ...p,
        viewable: false,
        errorMessage: 'Document Cannot Be Viewed – File May Be Corrupted.',
        loading: false,
      }))
    }
  }

  const canAct = detail?.status === 'SUBMITTED'
  const canRejectAfterDeadline =
    detail?.status === 'CORRECTION_REQUESTED' &&
    !!detail.correction_deadline &&
    new Date(detail.correction_deadline) < new Date()

  const stats = {
    pending: applications.filter((a) => a.status === 'SUBMITTED').length,
    correction: applications.filter((a) => a.status === 'CORRECTION_REQUESTED').length,
    inList: applications.length,
  }

  const pageHeader = {
    review: {
      title: 'Applications Management',
      subtitle: 'Review submitted documents (UC-03-01)',
    },
    notifications: {
      title: 'Notification Delivery Log',
      subtitle: 'Email delivery status for the selected application (SPEC-020)',
    },
    results: {
      title: 'Results & Announcement',
      subtitle: 'Publish final transfer results and notify applicants (UC-03-02)',
    },
  }[activePanel]

  return (
    <div className="flex flex-1 min-h-screen">
      <Sidebar userName={userName} role="Student Affairs" onLogout={onLogout}>
        <button
          onClick={() => setActivePanel('review')}
          className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm ${
            activePanel === 'review' ? 'bg-indigo-700 text-white' : 'text-indigo-200 hover:bg-indigo-800'
          }`}
        >
          <FileText className="w-5 h-5" /> Applications
        </button>
        <button
          onClick={() => setActivePanel('notifications')}
          className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm ${
            activePanel === 'notifications' ? 'bg-indigo-700 text-white' : 'text-indigo-200 hover:bg-indigo-800'
          }`}
        >
          <Mail className="w-5 h-5" /> Notifications
        </button>
        <button
          onClick={() => setActivePanel('results')}
          className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm ${
            activePanel === 'results' ? 'bg-indigo-700 text-white' : 'text-indigo-200 hover:bg-indigo-800'
          }`}
        >
          <Megaphone className="w-5 h-5" /> Results
        </button>
      </Sidebar>

      <div className="flex-1 flex flex-col min-h-screen bg-gray-50">
        <div className="px-6 py-4 bg-white border-b border-gray-200 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">{pageHeader.title}</h1>
            <p className="text-gray-500 text-sm">{pageHeader.subtitle}</p>
          </div>
          {activePanel === 'review' && (
            <button
              onClick={refresh}
              className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
          )}
        </div>

        {activePanel === 'results' ? (
          <div className="flex-1 overflow-y-auto">
            <ResultsAnnouncementPanel />
          </div>
        ) : (
          <>
        <div className="grid grid-cols-3 gap-4 p-4">
          {[
            { label: 'Pending Review', value: stats.pending, color: 'text-yellow-600' },
            { label: 'Correction Requested', value: stats.correction, color: 'text-orange-600' },
            { label: 'In List', value: stats.inList, color: 'text-indigo-600' },
          ].map((s) => (
            <div key={s.label} className="bg-white rounded-lg shadow-sm p-4">
              <p className="text-gray-500 text-xs mb-1">{s.label}</p>
              <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        <div className="flex-1 flex gap-4 px-4 pb-4 min-h-0">
          {/* List */}
          <div className="w-80 flex-shrink-0 bg-white rounded-lg shadow-sm flex flex-col overflow-hidden">
            <div className="p-3 border-b border-gray-100">
              <label className="block text-xs text-gray-500 mb-1">Filter by status</label>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value)
                  setSelectedId(null)
                }}
                className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm"
              >
                <option value="SUBMITTED">Submitted</option>
                <option value="CORRECTION_REQUESTED">Correction Requested</option>
                <option value="UNDER_REVIEW">Verified</option>
                <option value="REJECTED">Rejected</option>
              </select>
            </div>
            <div className="flex-1 overflow-y-auto">
              {loadingList ? (
                <div className="flex justify-center py-8"><Spinner /></div>
              ) : applications.length === 0 ? (
                <p className="text-gray-500 text-sm p-4">No applications to review.</p>
              ) : (
                applications.map((app) => (
                  <button
                    key={app.id}
                    onClick={() => setSelectedId(app.id)}
                    className={`w-full text-left p-3 border-b border-gray-50 hover:bg-indigo-50 transition-colors ${
                      selectedId === app.id ? 'bg-indigo-50 border-l-4 border-l-indigo-600' : ''
                    }`}
                  >
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {app.tracking_number ?? 'No tracking #'}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">{app.display_status}</p>
                    {app.submitted_at && (
                      <p className="text-xs text-gray-400">
                        {new Date(app.submitted_at).toLocaleDateString()}
                      </p>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>

          {/* Detail */}
          <div className="flex-1 bg-white rounded-lg shadow-sm overflow-y-auto">
            {activePanel === 'notifications' ? (
              <div className="p-6">
                <NotificationLogPanel applicationId={selectedId} />
              </div>
            ) : loadingDetail ? (
              <div className="flex justify-center py-16"><Spinner /></div>
            ) : !detail ? (
              <p className="text-gray-500 text-sm p-6">Select an application to review.</p>
            ) : (
              <div className="p-6 space-y-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">
                      {detail.tracking_number ?? 'Application'}
                    </h2>
                    <p className="text-sm text-gray-500">
                      {detail.applicant.first_name} {detail.applicant.last_name} · {detail.applicant.email}
                    </p>
                  </div>
                  <StatusBadge status={detail.display_status} />
                </div>

                {/* Applicant data */}
                <div className="grid grid-cols-2 gap-4 text-sm bg-gray-50 rounded-lg p-4">
                  <div><span className="text-gray-400 text-xs">National ID</span><p>{detail.applicant.national_id}</p></div>
                  <div><span className="text-gray-400 text-xs">Phone</span><p>{detail.applicant.phone ?? '—'}</p></div>
                  <div><span className="text-gray-400 text-xs">Submitted</span><p>{detail.submitted_at ? new Date(detail.submitted_at).toLocaleString() : '—'}</p></div>
                  {detail.correction_deadline && (
                    <div><span className="text-gray-400 text-xs">Correction deadline</span><p>{new Date(detail.correction_deadline).toLocaleString()}</p></div>
                  )}
                </div>

                {/* Auto validation */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">Automated Validation Results</h3>
                  <div className="space-y-1">
                    {detail.auto_validation_results.map((r, i) => (
                      <div key={i} className="flex items-center justify-between text-sm py-1 border-b border-gray-50">
                        <span className="text-gray-700">{r.rule_key}</span>
                        <div className="flex items-center gap-2">
                          {r.detail && <span className="text-xs text-gray-400 max-w-xs truncate">{r.detail}</span>}
                          <span className={`px-2 py-0.5 rounded-full text-xs ${r.passed ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                            {r.passed ? 'Met' : 'Not Met'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Documents */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 mb-2">Documents</h3>
                  <div className="space-y-2">
                    {detail.documents.map((doc) => (
                      <div key={doc.id} className="flex items-center justify-between py-2 border-b border-gray-100">
                        <div>
                          <p className="text-sm text-gray-900">{DOC_TYPE_LABELS[doc.doc_type as DocType] ?? doc.doc_type}</p>
                          <p className="text-xs text-gray-400">{doc.file_name}</p>
                        </div>
                        <button
                          onClick={() => handlePreview(doc)}
                          className="flex items-center gap-1 px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 rounded"
                        >
                          <Eye className="w-3 h-3" /> Preview
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Actions */}
                {(canAct || canRejectAfterDeadline) && (
                  <div className="flex flex-wrap gap-3 pt-4 border-t border-gray-200">
                    {canAct && (
                      <>
                        <button
                          onClick={handleApprove}
                          disabled={actionLoading}
                          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 disabled:opacity-50"
                        >
                          {actionLoading ? <Spinner /> : <CheckCircle className="w-4 h-4" />}
                          Approve Verification
                        </button>
                        <button
                          onClick={() => setShowCorrectionModal(true)}
                          disabled={actionLoading}
                          className="flex items-center gap-2 px-4 py-2 bg-yellow-500 text-white text-sm rounded-lg hover:bg-yellow-600 disabled:opacity-50"
                        >
                          <AlertTriangle className="w-4 h-4" /> Request Correction
                        </button>
                        <button
                          onClick={() => setShowRejectModal(true)}
                          disabled={actionLoading}
                          className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:opacity-50"
                        >
                          <XCircle className="w-4 h-4" /> Reject
                        </button>
                      </>
                    )}
                    {canRejectAfterDeadline && !canAct && (
                      <button
                        onClick={() => setShowRejectModal(true)}
                        disabled={actionLoading}
                        className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-700 disabled:opacity-50"
                      >
                        <XCircle className="w-4 h-4" /> Reject (deadline passed)
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
          </>
        )}
      </div>

      <DocumentPreviewModal
        open={preview.open}
        onClose={() => setPreview((p) => ({ ...p, open: false }))}
        title={preview.title}
        streamUrl={preview.streamUrl}
        viewable={preview.viewable}
        contentType={preview.contentType}
        errorMessage={preview.errorMessage}
        loading={preview.loading}
      />

      {/* Correction modal */}
      {showCorrectionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold mb-2">Request Correction</h3>
            <p className="text-sm text-gray-500 mb-4">Explain what the applicant needs to fix. They will be notified by email.</p>
            <textarea
              value={correctionNote}
              onChange={(e) => setCorrectionNote(e.target.value)}
              rows={4}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4"
              placeholder="e.g. Please upload a clearer scan of your transcript."
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowCorrectionModal(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleRequestCorrection} disabled={actionLoading} className="px-4 py-2 text-sm bg-yellow-500 text-white rounded-lg hover:bg-yellow-600 disabled:opacity-50">
                {actionLoading ? <Spinner /> : 'Send Request'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold mb-2">Reject Application</h3>
            <label className="block text-xs text-gray-500 mb-1">Reason code</label>
            <select
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value as RejectionReasonCode)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-3"
            >
              {Object.entries(REJECTION_REASON_LABELS).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
            <label className="block text-xs text-gray-500 mb-1">Note (optional)</label>
            <textarea
              value={rejectNote}
              onChange={(e) => setRejectNote(e.target.value)}
              rows={3}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm mb-4"
            />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowRejectModal(false)} className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">Cancel</button>
              <button onClick={handleReject} disabled={actionLoading} className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50">
                {actionLoading ? <Spinner /> : 'Confirm Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
