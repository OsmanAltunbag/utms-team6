import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useParams, useNavigate, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { AxiosError } from 'axios'
import AuthCard from '../components/AuthCard'
import PasswordInput from '../components/PasswordInput'
import Spinner from '../components/Spinner'
import { resetPasswordSchema, type ResetPasswordFormData } from '../schemas/auth'
import { resetPassword, extractErrorMessage } from '../api/auth'

export default function ResetPasswordPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [expired, setExpired] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordFormData>({ resolver: zodResolver(resetPasswordSchema) })

  async function onSubmit(data: ResetPasswordFormData) {
    if (!token) return
    setLoading(true)
    try {
      await resetPassword(token, data.new_password, data.new_password_confirm)
      toast.success('Password updated successfully!')
      navigate('/login', { replace: true })
    } catch (err) {
      const status = err instanceof AxiosError ? err.response?.status : null
      if (status === 410 || status === 404) {
        setExpired(true)
      } else {
        toast.error(extractErrorMessage(err))
      }
    } finally {
      setLoading(false)
    }
  }

  if (expired) {
    return (
      <AuthCard title="Link Expired">
        <div className="flex flex-col items-center gap-4 py-6 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-100">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12A9 9 0 113 12a9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="font-semibold text-slate-800">This link has expired.</p>
          <p className="text-sm text-slate-500">Password reset links are only valid for a limited time.</p>
          <Link
            to="/forgot-password"
            className="mt-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition"
          >
            Request New Link
          </Link>
        </div>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Set New Password" subtitle="Enter a strong new password for your account">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4 mt-6">
        <PasswordInput
          label="New Password"
          autoComplete="new-password"
          error={errors.new_password}
          {...register('new_password')}
        />

        <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
          <ul className="text-xs text-slate-500 space-y-0.5 list-disc list-inside">
            <li>At least 8 characters</li>
            <li>One uppercase letter, one digit, one special character</li>
          </ul>
        </div>

        <PasswordInput
          label="Confirm New Password"
          autoComplete="new-password"
          error={errors.new_password_confirm}
          {...register('new_password_confirm')}
        />

        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex items-center justify-center gap-2 rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition"
        >
          {loading && <Spinner size={4} />}
          {loading ? 'Updating…' : 'Update Password'}
        </button>
      </form>
    </AuthCard>
  )
}
