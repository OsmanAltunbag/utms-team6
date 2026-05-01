import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { AxiosError } from 'axios'
import AuthCard from '../components/AuthCard'
import FormInput from '../components/FormInput'
import PasswordInput from '../components/PasswordInput'
import Spinner from '../components/Spinner'
import { registerSchema, type RegisterFormData } from '../schemas/auth'
import { register as registerUser, extractErrorMessage } from '../api/auth'

export default function RegisterPage() {
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterFormData>({ resolver: zodResolver(registerSchema) })

  async function onSubmit(data: RegisterFormData) {
    setLoading(true)
    try {
      await registerUser(data)
      setSuccess(true)
    } catch (err) {
      const status = err instanceof AxiosError ? err.response?.status : null
      if (status === 409) {
        toast.error('An account with this information already exists.')
      } else if (status === 422) {
        toast.error(extractErrorMessage(err))
      } else {
        toast.error(extractErrorMessage(err))
      }
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <AuthCard title="Check Your Email">
        <div className="flex flex-col items-center gap-4 py-4 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <p className="text-slate-700 font-medium">Account created successfully.</p>
          <p className="text-sm text-slate-500">
            Please check your email for the verification link before signing in.
          </p>
          <Link
            to="/login"
            className="mt-2 rounded-lg bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 transition"
          >
            Go to Login
          </Link>
        </div>
      </AuthCard>
    )
  }

  return (
    <AuthCard title="Create Account" subtitle="Register for the transfer application system">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4 mt-6">
        <div className="grid grid-cols-2 gap-3">
          <FormInput
            label="First Name"
            type="text"
            autoComplete="given-name"
            placeholder="Ahmet"
            error={errors.first_name}
            {...register('first_name')}
          />
          <FormInput
            label="Last Name"
            type="text"
            autoComplete="family-name"
            placeholder="Yılmaz"
            error={errors.last_name}
            {...register('last_name')}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <FormInput
            label="National ID (TC)"
            type="text"
            inputMode="numeric"
            maxLength={11}
            placeholder="12345678901"
            error={errors.national_id}
            {...register('national_id')}
          />
          <FormInput
            label="Date of Birth"
            type="date"
            error={errors.date_of_birth}
            {...register('date_of_birth')}
          />
        </div>

        <FormInput
          label="University Email"
          type="email"
          autoComplete="email"
          placeholder="you@iyte.edu.tr"
          error={errors.university_email}
          {...register('university_email')}
        />

        <PasswordInput
          label="Password"
          autoComplete="new-password"
          error={errors.password}
          {...register('password')}
        />

        <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
          <p className="text-xs text-slate-500 font-medium mb-1">Password requirements:</p>
          <ul className="text-xs text-slate-500 space-y-0.5 list-disc list-inside">
            <li>At least 8 characters</li>
            <li>One uppercase letter (A–Z)</li>
            <li>One digit (0–9)</li>
            <li>One special character (!@#$%^&*…)</li>
          </ul>
        </div>

        <PasswordInput
          label="Confirm Password"
          autoComplete="new-password"
          error={errors.password_confirm}
          {...register('password_confirm')}
        />

        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex items-center justify-center gap-2 rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition"
        >
          {loading && <Spinner size={4} />}
          {loading ? 'Creating account…' : 'Create Account'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        Already have an account?{' '}
        <Link to="/login" className="text-blue-600 font-medium hover:underline">
          Sign in
        </Link>
      </p>
    </AuthCard>
  )
}
