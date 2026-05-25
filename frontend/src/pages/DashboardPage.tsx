import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import {
  Home, FileText, Send, CheckCircle, Clock, Users,
  Settings, BarChart2, Upload, Eye, RefreshCw, PlusCircle,
} from 'lucide-react'
import { logout } from '../api/auth'
import {
  listApplications,
  getApplication,
  getApplicationStatus,
  createApplication,
  fetchAcademicData,
  submitApplication,
  listDocuments,
  uploadDocument,
  verifyDocument,
  getPreviewUrl,
  listPrograms,
  listOpenPeriods,
  type ProgramOption,
  type PeriodOption,
} from '../api/applications'
import { useAuth } from '../context/AuthContext'
import { Sidebar } from '../components/Sidebar'
import { StatusBadge } from '../components/StatusBadge'
import Spinner from '../components/Spinner'
import type { ApplicationDetail, ApplicationStatus, AcademicRecord, Document, DocType } from '../types/application'
import { extractErrorMessage } from '../api/auth'

const ROLE_LABELS: Record<string, string> = {
  APPLICANT: 'Applicant',
  STUDENT_AFFAIRS: 'Student Affairs',
  TRANSFER_COMMISSION: 'Transfer Commission',
  YDYO: 'Foreign Languages Office',
  DEAN_OFFICE: "Dean's Office",
  SYSTEM_ADMIN: 'IT Administrator',
}

const DOC_TYPE_LABELS: Record<DocType, string> = {
  TRANSCRIPT: 'Transcript',
  YKS_RESULT: 'YKS Score Report',
  LANGUAGE_CERT: 'Language Certificate',
  ID_COPY: 'ID Copy',
  MILITARY_STATUS: 'Military Status',
  DISCIPLINE_RECORD: 'Discipline Record',
  OTHER: 'Other',
}

const REQUIRED_DOCS: DocType[] = ['TRANSCRIPT', 'YKS_RESULT', 'ID_COPY']

function NavBtn({ active, onClick, icon: Icon, label }: {
  active: boolean; onClick: () => void; icon: React.ElementType; label: string
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-3 w-full px-4 py-3 rounded-lg text-sm transition-colors ${
        active ? 'bg-indigo-700 text-white' : 'text-indigo-200 hover:bg-indigo-800 hover:text-white'
      }`}
    >
      <Icon className="w-5 h-5 flex-shrink-0" />
      {label}
    </button>
  )
}

// ---------------------------------------------------------------------------
// New Application Form
// ---------------------------------------------------------------------------

function NewApplicationForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [programs, setPrograms] = useState<ProgramOption[]>([])
  const [periods, setPeriods] = useState<PeriodOption[]>([])
  const [programId, setProgramId] = useState('')
  const [periodId, setPeriodId] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingOptions, setLoadingOptions] = useState(true)

  useEffect(() => {
    Promise.all([listPrograms(), listOpenPeriods()])
      .then(([progs, pers]) => {
        setPrograms(progs)
        setPeriods(pers)
        if (progs.length > 0) setProgramId(progs[0].id)
        if (pers.length > 0) setPeriodId(pers[0].id)
      })
      .catch(() => toast.error('Failed to load programs or periods.'))
      .finally(() => setLoadingOptions(false))
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!programId || !periodId) {
      toast.error('Please select a program and a period.')
      return
    }
    setLoading(true)
    try {
      const result = await createApplication({ program_id: programId, period_id: periodId })
      toast.success('Application created!')
      onCreated(result.application_id)
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (loadingOptions) {
    return (
      <div className="bg-white rounded-lg shadow-sm p-6 flex justify-center">
        <Spinner />
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-2">Start a New Application</h2>
      <p className="text-gray-500 text-sm mb-6">Select the program and application period for your transfer application.</p>

      {periods.length === 0 && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-800">
          No open application periods at this time. Please check back later.
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4 max-w-md">
        <div>
          <label className="block text-sm text-gray-700 mb-1">Program</label>
          <select
            value={programId}
            onChange={e => setProgramId(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          >
            {programs.length === 0 && <option value="">No programs available</option>}
            {programs.map(p => (
              <option key={p.id} value={p.id}>
                {p.code} — {p.name} ({p.faculty})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-gray-700 mb-1">Application Period</label>
          <select
            value={periodId}
            onChange={e => setPeriodId(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          >
            {periods.length === 0 && <option value="">No open periods</option>}
            {periods.map(p => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>
        <button
          type="submit"
          disabled={loading || periods.length === 0 || programs.length === 0}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {loading ? <Spinner /> : <PlusCircle className="w-4 h-4" />}
          Create Application
        </button>
      </form>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Extracted data label helpers
// ---------------------------------------------------------------------------

const EXTRACTION_LABELS: Record<string, string> = {
  gpa: 'GPA',
  completed_credits: 'Completed Credits',
  total_credits: 'Total Credits',
  institution: 'Institution',
  score: 'Score',
  score_type: 'Score Type',
  exam_year: 'Exam Year',
  certificate_type: 'Certificate Type',
  validity_date: 'Valid Until',
  national_id_verified: 'National ID Verified',
}

function ExtractionCard({
  applicationId,
  documentId,
  data,
  confirmed,
  onConfirmed,
}: {
  applicationId: string
  documentId: string
  data: Record<string, unknown>
  confirmed: boolean
  onConfirmed: () => void
}) {
  const [confirming, setConfirming] = useState(false)

  const missing = (data._missing as string[] | undefined) ?? []
  const found = Object.entries(data).filter(([k]) => k !== '_missing')
  const isIncomplete = missing.length > 0
  const hasNothing = found.length === 0

  async function handleConfirm() {
    setConfirming(true)
    try {
      await verifyDocument(applicationId, documentId)
      toast.success('Document verified.')
      onConfirmed()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setConfirming(false)
    }
  }

  if (confirmed) {
    return (
      <div className="mt-2 rounded-lg border border-green-200 bg-green-50 p-3">
        <p className="text-xs font-medium text-green-700 mb-1">Extracted Information (Confirmed)</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {found.map(([key, val]) => (
            <div key={key}>
              <span className="text-gray-400 text-xs">{EXTRACTION_LABELS[key] ?? key}: </span>
              <span className="text-gray-800 text-xs font-medium">{String(val)}</span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (isIncomplete || hasNothing) {
    const noExtractionDefined = found.length === 0 && missing.length === 0
    return (
      <div className="mt-2 rounded-lg border border-red-200 bg-red-50 p-3">
        <p className="text-xs font-medium text-red-700 mb-2">
          {noExtractionDefined
            ? 'No automatic extraction available for this document type'
            : hasNothing
              ? 'No information could be extracted from this file'
              : 'Some information could not be extracted'}
        </p>

        {found.length > 0 && (
          <div className="mb-2">
            <p className="text-xs text-gray-500 mb-1">Found:</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {found.map(([key, val]) => (
                <div key={key}>
                  <span className="text-gray-400 text-xs">{EXTRACTION_LABELS[key] ?? key}: </span>
                  <span className="text-gray-800 text-xs font-medium">{String(val)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {missing.length > 0 && (
          <div className="mb-2">
            <p className="text-xs text-gray-500 mb-1">Missing:</p>
            <div className="grid grid-cols-2 gap-x-4 gap-y-1">
              {missing.map((key) => (
                <div key={key}>
                  <span className="text-gray-400 text-xs">{EXTRACTION_LABELS[key] ?? key}: </span>
                  <span className="text-red-500 text-xs font-medium">Not found</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="text-xs text-red-600 mb-2">
          {noExtractionDefined
            ? 'Please confirm you have uploaded the correct document.'
            : 'Please check that you uploaded the correct document. You may re-upload or confirm anyway.'}
        </p>
        <button
          onClick={handleConfirm}
          disabled={confirming}
          className="flex items-center gap-1 px-2 py-1 text-xs bg-red-500 text-white rounded hover:bg-red-600 disabled:opacity-50"
        >
          {confirming ? <Spinner /> : <CheckCircle className="w-3 h-3" />}
          Confirm Anyway
        </button>
      </div>
    )
  }

  return (
    <div className="mt-2 rounded-lg border border-yellow-200 bg-yellow-50 p-3">
      <p className="text-xs font-medium text-yellow-700 mb-2">Extracted Information — Please verify</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 mb-2">
        {found.map(([key, val]) => (
          <div key={key}>
            <span className="text-gray-400 text-xs">{EXTRACTION_LABELS[key] ?? key}: </span>
            <span className="text-gray-800 text-xs font-medium">{String(val)}</span>
          </div>
        ))}
      </div>
      <button
        onClick={handleConfirm}
        disabled={confirming}
        className="flex items-center gap-1 px-2 py-1 text-xs bg-yellow-500 text-white rounded hover:bg-yellow-600 disabled:opacity-50"
      >
        {confirming ? <Spinner /> : <CheckCircle className="w-3 h-3" />}
        Confirm
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Document upload row
// ---------------------------------------------------------------------------

function DocumentUploadRow({
  applicationId,
  docType,
  existing,
  onUploaded,
}: {
  applicationId: string
  docType: DocType
  existing: Document | undefined
  onUploaded: () => void
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.type !== 'application/pdf') {
      toast.error('Invalid file format. Please upload a PDF file.')
      return
    }
    if (file.size > 5_242_880) {
      toast.error('File exceeds 5 MB limit.')
      return
    }

    setUploading(true)
    try {
      await uploadDocument(applicationId, docType, file)
      toast.success(`${DOC_TYPE_LABELS[docType]} uploaded.`)
      onUploaded()
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function handlePreview() {
    if (!existing) return
    const { preview_url } = getPreviewUrl(existing.id)
    window.open(preview_url, '_blank')
  }

  const hasExtraction = existing?.extracted_data !== null && existing?.extracted_data !== undefined

  return (
    <div className="py-3 border-b border-gray-100 last:border-0">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-2 h-2 rounded-full ${existing ? 'bg-green-500' : 'bg-gray-300'}`} />
          <div>
            <p className="text-sm text-gray-900">{DOC_TYPE_LABELS[docType]}</p>
            {existing && (
              <p className="text-xs text-gray-400">{existing.file_name} · {existing.status}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {existing && (
            <button
              onClick={handlePreview}
              className="flex items-center gap-1 px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50 rounded"
            >
              <Eye className="w-3 h-3" /> Preview
            </button>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1 px-3 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
          >
            {uploading ? <Spinner /> : <Upload className="w-3 h-3" />}
            {existing ? 'Replace' : 'Upload'}
          </button>
        </div>
      </div>
      {existing && hasExtraction && (
        <div className="ml-5">
          <ExtractionCard
            applicationId={applicationId}
            documentId={existing.id}
            data={existing.extracted_data as Record<string, unknown>}
            confirmed={existing.extraction_confirmed}
            onConfirmed={onUploaded}
          />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Applicant Dashboard
// ---------------------------------------------------------------------------

function ApplicantDashboardContent({ userName, onLogout }: { userName: string; onLogout: () => void }) {
  const [activeTab, setActiveTab] = useState<'overview' | 'application' | 'messages' | 'results'>('overview')
  const [application, setApplication] = useState<ApplicationDetail | null>(null)
  const [appStatus, setAppStatus] = useState<ApplicationStatus | null>(null)
  const [documents, setDocuments] = useState<Document[]>([])
  const [academicRecord, setAcademicRecord] = useState<AcademicRecord | null>(null)
  const [loadingApp, setLoadingApp] = useState(true)
  const [fetchingAcademic, setFetchingAcademic] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [hasNoApp, setHasNoApp] = useState(false)

  async function loadApplication(id?: string) {
    try {
      let appId = id
      if (!appId) {
        const apps = await listApplications()
        if (apps.length === 0) { setHasNoApp(true); setLoadingApp(false); return }
        appId = apps[0].id
      }
      const [detail, statusData, docs] = await Promise.all([
        getApplication(appId),
        getApplicationStatus(appId),
        listDocuments(appId),
      ])
      setApplication(detail)
      setAppStatus(statusData)
      setHasNoApp(false)
      setDocuments(docs)
    } catch {
      setHasNoApp(true)
    } finally {
      setLoadingApp(false)
    }
  }

  useEffect(() => { loadApplication() }, [])

  // SSE: auto-refresh on status change
  useEffect(() => {
    if (!application) return
    const terminal = ['ANNOUNCED', 'REJECTED']
    if (terminal.includes(application.status)) return

    const es = new EventSource(`/api/applications/${application.id}/events`, { withCredentials: true })
    es.onmessage = () => { loadApplication(application.id) }
    es.onerror = () => { es.close() }
    return () => es.close()
  }, [application?.id, application?.status])

  async function handleFetchAcademic() {
    if (!application) return
    setFetchingAcademic(true)
    try {
      const record = await fetchAcademicData(application.id)
      setAcademicRecord(record)
      if (record.errors?.length) {
        toast.error(`Partial data: ${record.errors.join(', ')}`)
      } else {
        toast.success('Academic data fetched successfully.')
      }
      await loadApplication(application.id)
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setFetchingAcademic(false)
    }
  }

  async function handleSubmit() {
    if (!application) return
    setSubmitting(true)
    try {
      const result = await submitApplication(application.id)
      toast.success(`Submitted! Tracking number: ${result.tracking_number}`)
      await loadApplication(application.id)
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDocUploaded() {
    if (application) {
      const docs = await listDocuments(application.id)
      setDocuments(docs)
    }
  }

  if (loadingApp) {
    return (
      <div className="flex flex-1 min-h-screen items-center justify-center bg-gray-50">
        <Spinner />
      </div>
    )
  }

  return (
    <div className="flex flex-1 min-h-screen">
      <Sidebar userName={userName} role="Applicant" onLogout={onLogout}>
        <NavBtn active={activeTab === 'overview'} onClick={() => setActiveTab('overview')} icon={Home} label="Overview" />
        <NavBtn active={activeTab === 'application'} onClick={() => setActiveTab('application')} icon={FileText} label="My Application" />
        <NavBtn active={activeTab === 'messages'} onClick={() => setActiveTab('messages')} icon={Send} label="Messages" />
        <NavBtn active={activeTab === 'results'} onClick={() => setActiveTab('results')} icon={CheckCircle} label="Results" />
      </Sidebar>

      <div className="flex-1 p-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-2xl font-semibold text-gray-900 mb-1">IZTECH Transfer Application</h1>
          <p className="text-gray-500 text-sm mb-8">Izmir Institute of Technology</p>

          {/* ── Overview tab ──────────────────────────────────────────── */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {hasNoApp ? (
                <NewApplicationForm onCreated={(id) => { setLoadingApp(true); loadApplication(id) }} />
              ) : application ? (
                <>
                  {/* CORRECTION_REQUESTED banner */}
                  {application.status === 'CORRECTION_REQUESTED' && (
                    <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4 flex items-start gap-3">
                      <Clock className="w-5 h-5 text-yellow-600 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-yellow-800">Correction Required</p>
                        <p className="text-xs text-yellow-700 mt-0.5">Your documents need corrections. Please upload the updated files in the Documents tab.</p>
                      </div>
                    </div>
                  )}

                  {/* REJECTED banner */}
                  {application.status === 'REJECTED' && (
                    <div className="bg-red-50 border border-red-300 rounded-lg p-4">
                      <p className="text-sm font-semibold text-red-800 mb-1">Application Rejected</p>
                      {appStatus?.result?.reason && (
                        <p className="text-sm text-red-700">{appStatus.result.reason}</p>
                      )}
                    </div>
                  )}

                  {/* Status card */}
                  <div className="bg-white rounded-lg shadow-sm p-6">
                    <div className="flex items-start justify-between mb-6">
                      <div>
                        <h2 className="text-lg font-semibold text-gray-900 mb-1">Application Status</h2>
                        <p className="text-gray-500 text-sm">
                          {application.tracking_number
                            ? `Tracking: ${application.tracking_number}`
                            : 'Not yet submitted'}
                        </p>
                      </div>
                      <StatusBadge status={application.status} />
                    </div>
                    <div className="grid grid-cols-2 gap-6">
                      {academicRecord?.institution && (
                        <div><p className="text-gray-400 text-xs mb-1">Institution</p><p className="text-gray-900 text-sm">{academicRecord.institution}</p></div>
                      )}
                      {academicRecord?.gpa_4 != null && (
                        <div><p className="text-gray-400 text-xs mb-1">GPA (4.0)</p><p className="text-gray-900 text-sm">{academicRecord.gpa_4}</p></div>
                      )}
                      {academicRecord?.yks_score != null && (
                        <div><p className="text-gray-400 text-xs mb-1">YKS Score</p><p className="text-gray-900 text-sm">{academicRecord.yks_score}</p></div>
                      )}
                      <div><p className="text-gray-400 text-xs mb-1">Created</p><p className="text-gray-900 text-sm">{new Date(application.created_at).toLocaleDateString()}</p></div>
                      {application.submitted_at && (
                        <div><p className="text-gray-400 text-xs mb-1">Submitted</p><p className="text-gray-900 text-sm">{new Date(application.submitted_at).toLocaleDateString()}</p></div>
                      )}
                    </div>
                  </div>

                  {/* Progress — vertical step list (Figma style) */}
                  <div className="bg-white rounded-lg shadow-sm p-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-6">Application Progress</h2>
                    <div className="space-y-4">
                      {appStatus ? appStatus.progress.stages.map((stage, i) => (
                        <div key={i} className="flex items-start gap-4">
                          <div className="mt-0.5">
                            {stage.completed ? (
                              <CheckCircle className="w-5 h-5 text-green-600" />
                            ) : stage.active ? (
                              <Clock className="w-5 h-5 text-blue-600" />
                            ) : (
                              <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
                            )}
                          </div>
                          <div className="flex-1 flex items-center justify-between">
                            <div>
                              <p className="text-sm text-gray-900">{stage.label_en}</p>
                              <p className="text-xs text-gray-400">{stage.label_tr}</p>
                            </div>
                            <StatusBadge status={stage.completed ? 'completed' : stage.active ? 'pending' : 'waiting'} />
                          </div>
                        </div>
                      )) : application.progress.steps.map((step, i) => (
                        <div key={i} className="flex items-start gap-4">
                          <div className="mt-0.5">
                            {step.completed ? (
                              <CheckCircle className="w-5 h-5 text-green-600" />
                            ) : step.active ? (
                              <Clock className="w-5 h-5 text-blue-600" />
                            ) : (
                              <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
                            )}
                          </div>
                          <div className="flex-1 flex items-center justify-between">
                            <p className="text-sm text-gray-900">{step.step.replace(/_/g, ' ')}</p>
                            <StatusBadge status={step.completed ? 'completed' : step.active ? 'pending' : 'waiting'} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Status history */}
                  {appStatus && appStatus.history.length > 0 && (
                    <div className="bg-white rounded-lg shadow-sm p-6">
                      <h2 className="text-lg font-semibold text-gray-900 mb-4">Status History</h2>
                      <div className="space-y-4">
                        {appStatus.history.map((entry, i) => (
                          <div key={i} className="flex items-start gap-4">
                            <div className="mt-0.5">
                              <CheckCircle className="w-5 h-5 text-indigo-400" />
                            </div>
                            <div className="flex-1 flex items-center justify-between">
                              <div>
                                <p className="text-sm text-gray-900">{entry.status.replace(/_/g, ' ')}</p>
                                {entry.note && <p className="text-xs text-gray-400">{entry.note}</p>}
                                {entry.changed_by_role && <p className="text-xs text-gray-400">{entry.changed_by_role.replace(/_/g, ' ')}</p>}
                              </div>
                              <span className="text-xs text-gray-400">{new Date(entry.changed_at).toLocaleDateString()}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Eligibility checks */}
                  {application.eligibility_checks.length > 0 && (
                    <div className="bg-white rounded-lg shadow-sm p-6">
                      <h2 className="text-lg font-semibold text-gray-900 mb-4">Eligibility Checks</h2>
                      <div className="space-y-2">
                        {application.eligibility_checks.map((c, i) => (
                          <div key={i} className="flex items-center justify-between text-sm">
                            <span className="text-gray-700">{c.rule_key}</span>
                            <div className="flex items-center gap-2">
                              <span className="text-gray-500 text-xs">{c.detail}</span>
                              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${c.passed ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                {c.passed ? 'Pass' : 'Fail'}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          )}

          {/* ── Application tab ───────────────────────────────────────── */}
          {activeTab === 'application' && (
            <div className="space-y-6">
              {!application ? (
                <div className="bg-white rounded-lg shadow-sm p-6">
                  <p className="text-gray-500 text-sm">No application yet. Go to Overview to create one.</p>
                </div>
              ) : (
                <>
                  {/* Academic data */}
                  <div className="bg-white rounded-lg shadow-sm p-6">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h2 className="text-lg font-semibold text-gray-900">Academic Data</h2>
                        <p className="text-gray-500 text-xs mt-0.5">Fetched automatically from UBYS, YÖKSİS, and ÖSYM</p>
                      </div>
                      <button
                        onClick={handleFetchAcademic}
                        disabled={fetchingAcademic}
                        className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
                      >
                        {fetchingAcademic ? <Spinner /> : <RefreshCw className="w-4 h-4" />}
                        Fetch Academic Data
                      </button>
                    </div>
                    {academicRecord ? (
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div><p className="text-gray-400 text-xs mb-0.5">Institution</p><p>{academicRecord.institution ?? '—'}</p></div>
                        <div><p className="text-gray-400 text-xs mb-0.5">GPA (4.0)</p><p>{academicRecord.gpa_4 ?? '—'}</p></div>
                        <div><p className="text-gray-400 text-xs mb-0.5">YKS Score</p><p>{academicRecord.yks_score ?? '—'}</p></div>
                        <div><p className="text-gray-400 text-xs mb-0.5">Credits Completed</p><p>{academicRecord.credits_completed ?? '—'}</p></div>
                        <div><p className="text-gray-400 text-xs mb-0.5">Source</p><p>{academicRecord.source ?? '—'}</p></div>
                      </div>
                    ) : (
                      <p className="text-gray-400 text-sm">No academic data yet. Click "Fetch Academic Data".</p>
                    )}
                  </div>

                  {/* Documents */}
                  <div className="bg-white rounded-lg shadow-sm p-6">
                    <h2 className="text-lg font-semibold text-gray-900 mb-1">Documents</h2>
                    <p className="text-gray-500 text-xs mb-4">PDF only · max 5 MB per file · required: Transcript, YKS Result, ID Copy</p>
                    <div>
                      {([...REQUIRED_DOCS, 'LANGUAGE_CERT', 'MILITARY_STATUS', 'DISCIPLINE_RECORD'] as DocType[]).map((dt) => (
                        <DocumentUploadRow
                          key={dt}
                          applicationId={application.id}
                          docType={dt}
                          existing={documents.find(d => d.doc_type === dt)}
                          onUploaded={handleDocUploaded}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Submit */}
                  {application.status === 'DRAFT' && (
                    <div className="bg-white rounded-lg shadow-sm p-6">
                      <h2 className="text-lg font-semibold text-gray-900 mb-2">Submit Application</h2>
                      <p className="text-gray-500 text-sm mb-4">
                        Make sure all required documents are uploaded and academic data is fetched before submitting.
                      </p>
                      <button
                        onClick={handleSubmit}
                        disabled={submitting}
                        className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                      >
                        {submitting ? <Spinner /> : <Send className="w-4 h-4" />}
                        Submit Application
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Messages tab ──────────────────────────────────────────── */}
          {activeTab === 'messages' && (
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Messages with Student Affairs</h2>
              <p className="text-gray-500 text-sm">No messages yet.</p>
            </div>
          )}

          {/* ── Results tab ───────────────────────────────────────────── */}
          {activeTab === 'results' && (
            <div className="bg-white rounded-lg shadow-sm p-6">
              {application?.status === 'ANNOUNCED' ? (
                <div className="text-center py-8">
                  <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
                  <h3 className="text-gray-900 font-semibold mb-1">Transfer Accepted</h3>
                  <p className="text-gray-500 text-sm">Congratulations! Your transfer application has been approved.</p>
                </div>
              ) : application?.status === 'REJECTED' ? (
                <div className="text-center py-8">
                  <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                    <span className="text-red-600 text-2xl font-bold">✗</span>
                  </div>
                  <h3 className="text-gray-900 font-semibold mb-1">Application Rejected</h3>
                  <p className="text-gray-500 text-sm">Unfortunately, your application was not approved.</p>
                </div>
              ) : (
                <div className="text-center py-12">
                  <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                  <h3 className="text-gray-700 font-medium mb-2">Results Not Yet Announced</h3>
                  <p className="text-gray-500 text-sm">Your application is still being processed.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Staff Dashboard (unchanged)
// ---------------------------------------------------------------------------

function StaffDashboardContent({ userName, roleLabel, icon: Icon, onLogout }: {
  userName: string; roleLabel: string; icon: React.ElementType; onLogout: () => void
}) {
  return (
    <div className="flex flex-1 min-h-screen">
      <Sidebar userName={userName} role={roleLabel} onLogout={onLogout}>
        <NavBtn active={true} onClick={() => {}} icon={Home} label="Dashboard" />
        <NavBtn active={false} onClick={() => {}} icon={Users} label="Applications" />
        <NavBtn active={false} onClick={() => {}} icon={BarChart2} label="Reports" />
        <NavBtn active={false} onClick={() => {}} icon={Settings} label="Settings" />
      </Sidebar>
      <div className="flex-1 p-8 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
              <Icon className="w-6 h-6 text-indigo-600" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-gray-900">{roleLabel}</h1>
              <p className="text-gray-500 text-sm">Izmir Institute of Technology</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-6 mb-8">
            {[
              { label: 'Pending Review', value: '—', color: 'text-yellow-600' },
              { label: 'Approved', value: '—', color: 'text-green-600' },
              { label: 'Rejected', value: '—', color: 'text-red-600' },
            ].map((stat) => (
              <div key={stat.label} className="bg-white rounded-lg shadow-sm p-6">
                <p className="text-gray-500 text-sm mb-1">{stat.label}</p>
                <p className={`text-3xl font-bold ${stat.color}`}>{stat.value}</p>
              </div>
            ))}
          </div>
          <div className="bg-white rounded-lg shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Applications</h2>
            <p className="text-gray-500 text-sm">No applications to review at this time.</p>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { role, userName, clearAuth } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    try {
      await logout()
    } finally {
      clearAuth()
      navigate('/login', { replace: true })
      toast.success('Logged out.')
    }
  }

  const displayName = userName ?? 'User'
  const roleLabel = ROLE_LABELS[role ?? ''] ?? role ?? 'User'

  switch (role) {
    case 'APPLICANT':
      return <ApplicantDashboardContent userName={displayName} onLogout={handleLogout} />
    case 'STUDENT_AFFAIRS':
      return <StaffDashboardContent userName={displayName} roleLabel="Student Affairs" icon={FileText} onLogout={handleLogout} />
    case 'TRANSFER_COMMISSION':
      return <StaffDashboardContent userName={displayName} roleLabel="Transfer Commission" icon={Users} onLogout={handleLogout} />
    case 'YDYO':
      return <StaffDashboardContent userName={displayName} roleLabel="Foreign Languages Office" icon={CheckCircle} onLogout={handleLogout} />
    case 'DEAN_OFFICE':
      return <StaffDashboardContent userName={displayName} roleLabel="Dean's Office" icon={BarChart2} onLogout={handleLogout} />
    case 'SYSTEM_ADMIN':
      return <StaffDashboardContent userName={displayName} roleLabel="IT Administrator" icon={Settings} onLogout={handleLogout} />
    default:
      return <StaffDashboardContent userName={displayName} roleLabel={roleLabel} icon={Home} onLogout={handleLogout} />
  }
}
