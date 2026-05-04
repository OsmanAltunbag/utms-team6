import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { AxiosError } from 'axios'
import { GraduationCap, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react'
import { verifyEmail } from '../api/auth'

type Status = 'loading' | 'success' | 'expired' | 'error'

export default function VerifyEmailPage() {
  const { token } = useParams<{ token: string }>()
  const [status, setStatus] = useState<Status>('loading')

  useEffect(() => {
    if (!token) { setStatus('error'); return }
    verifyEmail(token)
      .then(() => setStatus('success'))
      .catch((err) => {
        const code = err instanceof AxiosError ? err.response?.status : null
        setStatus(code === 410 || code === 404 ? 'expired' : 'error')
      })
  }, [token])

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <GraduationCap className="w-10 h-10 text-indigo-600 mx-auto mb-2" />
          <p className="text-indigo-900 font-semibold">IZTECH UTMS</p>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-8 text-center">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">Email Verification</h2>

          {status === 'loading' && (
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="w-12 h-12 text-indigo-500 animate-spin" />
              <p className="text-gray-500 text-sm">Verifying your email…</p>
            </div>
          )}

          {status === 'success' && (
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                <CheckCircle className="w-8 h-8 text-green-600" />
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Email verified successfully!</p>
                <p className="text-sm text-gray-500">You can now sign in to your account.</p>
              </div>
              <Link
                to="/login"
                className="w-full bg-indigo-600 text-white py-2.5 px-4 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition-colors"
              >
                Go to Login
              </Link>
            </div>
          )}

          {(status === 'expired' || status === 'error') && (
            <div className="flex flex-col items-center gap-4">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center">
                <AlertTriangle className="w-8 h-8 text-red-500" />
              </div>
              <div>
                <p className="font-semibold text-gray-900 mb-1">Link expired or invalid</p>
                <p className="text-sm text-gray-500">
                  This verification link has expired or is invalid. Please register again.
                </p>
              </div>
              <Link
                to="/register"
                className="w-full bg-indigo-600 text-white py-2.5 px-4 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition-colors"
              >
                Register Again
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
