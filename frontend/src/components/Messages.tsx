import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { Send, RefreshCw } from 'lucide-react'
import Spinner from './Spinner'
import {
  listMyQuestions,
  createQuestion,
  listAllQuestions,
  replyToQuestion,
  type Question,
} from '../api/messages'

function errMsg(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string }
    if (first?.msg) return first.msg
  }
  return 'Something went wrong. Please try again.'
}

export function QuestionThread({ q, showApplicant }: { q: Question; showApplicant?: boolean }) {
  return (
    <div className="border border-gray-200 rounded-lg p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-gray-900">{q.subject}</p>
          {showApplicant && q.applicant_name && (
            <p className="text-xs text-gray-400">From: {q.applicant_name}</p>
          )}
        </div>
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${q.is_resolved ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
          {q.is_resolved ? 'Answered' : 'Awaiting reply'}
        </span>
      </div>
      <p className="text-sm text-gray-700 mt-2 whitespace-pre-wrap">{q.body}</p>
      <p className="text-xs text-gray-400 mt-1">{new Date(q.created_at).toLocaleString()}</p>

      {q.replies.length > 0 && (
        <div className="mt-3 space-y-2 border-l-2 border-indigo-100 pl-3">
          {q.replies.map(r => (
            <div key={r.id}>
              <p className="text-xs font-medium text-indigo-700">{r.staff_name}</p>
              <p className="text-sm text-gray-700 whitespace-pre-wrap">{r.body}</p>
              <p className="text-xs text-gray-400">{new Date(r.created_at).toLocaleString()}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ApplicantMessagesPanel({ applicationId }: { applicationId?: string | null }) {
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(true)
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)

  async function load() {
    try {
      setQuestions(await listMyQuestions())
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    if (!subject.trim() || !body.trim()) {
      toast.error('Please enter a subject and a message.')
      return
    }
    setSending(true)
    try {
      await createQuestion({ subject: subject.trim(), body: body.trim(), application_id: applicationId ?? null })
      toast.success('Message sent to Student Affairs.')
      setSubject('')
      setBody('')
      await load()
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Ask Student Affairs</h2>
        <form onSubmit={handleSend} className="space-y-3">
          <input
            value={subject}
            onChange={e => setSubject(e.target.value)}
            placeholder="Subject"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <textarea
            value={body}
            onChange={e => setBody(e.target.value)}
            rows={3}
            placeholder="Type your question…"
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <button
            type="submit"
            disabled={sending}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {sending ? <Spinner /> : <Send className="w-4 h-4" />}
            Send Message
          </button>
        </form>
      </div>

      <div className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Your Messages</h2>
        {loading ? (
          <div className="flex justify-center py-8"><Spinner /></div>
        ) : questions.length === 0 ? (
          <p className="text-gray-500 text-sm">No messages yet.</p>
        ) : (
          <div className="space-y-3">
            {questions.map(q => <QuestionThread key={q.id} q={q} />)}
          </div>
        )}
      </div>
    </div>
  )
}

export function StaffMessagesPanel() {
  const [questions, setQuestions] = useState<Question[]>([])
  const [loading, setLoading] = useState(true)
  const [replyText, setReplyText] = useState<Record<string, string>>({})
  const [replyingId, setReplyingId] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    try {
      setQuestions(await listAllQuestions())
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function handleReply(id: string) {
    const text = (replyText[id] ?? '').trim()
    if (!text) {
      toast.error('Please enter a reply.')
      return
    }
    setReplyingId(id)
    try {
      await replyToQuestion(id, text)
      toast.success('Reply sent.')
      setReplyText(t => ({ ...t, [id]: '' }))
      await load()
    } catch (err) {
      toast.error(errMsg(err))
    } finally {
      setReplyingId(null)
    }
  }

  return (
    <div className="bg-white rounded-lg shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Student Messages</h2>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          {loading ? <Spinner /> : <RefreshCw className="w-4 h-4" />}
          Refresh
        </button>
      </div>
      {loading ? (
        <div className="flex justify-center py-8"><Spinner /></div>
      ) : questions.length === 0 ? (
        <p className="text-gray-500 text-sm">No messages from students yet.</p>
      ) : (
        <div className="space-y-4">
          {questions.map(q => (
            <div key={q.id}>
              <QuestionThread q={q} showApplicant />
              <div className="flex gap-2 mt-2">
                <input
                  value={replyText[q.id] ?? ''}
                  onChange={e => setReplyText(t => ({ ...t, [q.id]: e.target.value }))}
                  placeholder="Write a reply…"
                  className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                />
                <button
                  onClick={() => handleReply(q.id)}
                  disabled={replyingId === q.id}
                  className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                >
                  {replyingId === q.id ? <Spinner /> : <Send className="w-4 h-4" />}
                  Reply
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
