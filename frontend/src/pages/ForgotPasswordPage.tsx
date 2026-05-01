import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import AuthCard from '../components/AuthCard'
import FormInput from '../components/FormInput'
import Spinner from '../components/Spinner'
import { forgotPasswordSchema, type ForgotPasswordFormData } from '../schemas/auth'
import { forgotPassword, extractErrorMessage } from '../api/auth'

export default function ForgotPasswordPage() {
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormData>({ resolver: zodResolver(forgotPasswordSchema) })

  async function onSubmit(data: ForgotPasswordFormData) {
    setLoading(true)
    try {
      await forgotPassword(data.email)
      setSent(true)
    } catch (err) {
      toast.error(extractErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <AuthCard title="Check Your Email">
        <div className="flex flex-col items-center gap-4 py-4 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-100">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <p className="text-slate-700 font-medium text-sm leading-relaxed">
            If this email is registered, a password reset link has been sent.
          </p>
          <Link
            to="/login"
            className="mt-2 text-sm text-blue-600 hover:underline font-medium"
          >
            Back to Login
          </Link>
        </div>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title="Forgot Password"
      subtitle="Enter your university email and we'll send a reset link"
    >
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4 mt-6">
        <FormInput
          label="University Email"
          type="email"
          autoComplete="email"
          placeholder="you@iyte.edu.tr"
          error={errors.email}
          {...register('email')}
        />

        <button
          type="submit"
          disabled={loading}
          className="flex items-center justify-center gap-2 rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition"
        >
          {loading && <Spinner size={4} />}
          {loading ? 'Sending…' : 'Send Reset Link'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        <Link to="/login" className="text-blue-600 font-medium hover:underline">
          ← Back to Login
        </Link>
      </p>
    </AuthCard>
  )
}
