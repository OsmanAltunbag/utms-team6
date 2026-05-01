import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { AxiosError } from 'axios'
import AuthCard from '../components/AuthCard'
import Spinner from '../components/Spinner'
import { verifyEmail } from '../api/auth'

type Status = 'loading' | 'success' | 'expired' | 'error'

export default function VerifyEmailPage() {
  const { token } = useParams<{ token: string }>()
  const [status, setStatus] = useState<Status>('loading')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      return
    }
    verifyEmail(token)
      .then(() => setStatus('success'))
      .catch((err) => {
        const code = err instanceof AxiosError ? err.response?.status : null
        setStatus(code === 410 || code === 404 ? 'expired' : 'error')
      })
  }, [token])

  return (
    <AuthCard title="Email Verification">
      <div className="flex flex-col items-center gap-4 py-6 text-center">
        {status === 'loading' && (
          <>
            <Spinner size={8} />
            <p className="text-slate-500 text-sm">Verifying your email…</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="font-semibold text-slate-800">Email verified successfully!</p>
            <p className="text-sm text-slate-500">You can now sign in to your account.</p>
            <Link
              to="/login"
              className="mt-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition"
            >
              Go to Login
            </Link>
          </>
        )}

        {(status === 'expired' || status === 'error') && (
          <>
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
            </div>
            <p className="font-semibold text-slate-800">Link expired or invalid</p>
            <p className="text-sm text-slate-500">
              This verification link has expired or is invalid. Please register again.
            </p>
            <Link
              to="/register"
              className="mt-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition"
            >
              Register Again
            </Link>
          </>
        )}
      </div>
    </AuthCard>
  )
}
