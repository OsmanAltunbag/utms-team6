import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { logout } from '../api/auth'
import { useAuth } from '../context/AuthContext'
import Spinner from '../components/Spinner'

export default function DashboardPage() {
  const { role, clearAuth } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)

  async function handleLogout() {
    setLoading(true)
    try {
      await logout()
    } finally {
      clearAuth()
      navigate('/login', { replace: true })
      toast.success('Logged out.')
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4">
      <div className="bg-white rounded-2xl shadow p-8 text-center max-w-sm w-full">
        <h1 className="text-2xl font-bold text-slate-800 mb-1">Dashboard</h1>
        <p className="text-slate-500 text-sm mb-6">
          Signed in as <span className="font-semibold text-blue-600">{role}</span>
        </p>
        <button
          onClick={handleLogout}
          disabled={loading}
          className="flex items-center justify-center gap-2 w-full rounded-lg border border-slate-200 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60 transition"
        >
          {loading && <Spinner size={4} />}
          Sign Out
        </button>
      </div>
    </div>
  )
}
