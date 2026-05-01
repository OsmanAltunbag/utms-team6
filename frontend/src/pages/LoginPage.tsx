import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { AxiosError } from 'axios'
import AuthCard from '../components/AuthCard'
import FormInput from '../components/FormInput'
import PasswordInput from '../components/PasswordInput'
import Spinner from '../components/Spinner'
import { loginSchema, type LoginFormData } from '../schemas/auth'
import { login, extractErrorMessage } from '../api/auth'
import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const navigate = useNavigate()
  const { setRole } = useAuth()
  const [loading, setLoading] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({ resolver: zodResolver(loginSchema) })

  async function onSubmit(data: LoginFormData) {
    setLoading(true)
    try {
      const res = await login(data)
      setRole(res.role)
      toast.success('Welcome back!')
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const status = err instanceof AxiosError ? err.response?.status : null
      if (status === 401) {
        toast.error('Invalid email or password.')
      } else if (status === 423) {
        toast.error('Account locked. Too many failed attempts.')
      } else {
        toast.error(extractErrorMessage(err))
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthCard title="Sign in to UTMS" subtitle="Use your university account to continue">
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4 mt-6">
        <FormInput
          label="University Email"
          type="email"
          autoComplete="email"
          placeholder="you@iyte.edu.tr"
          error={errors.email}
          {...register('email')}
        />

        <PasswordInput
          label="Password"
          autoComplete="current-password"
          error={errors.password}
          {...register('password')}
        />

        <div className="text-right -mt-2">
          <Link to="/forgot-password" className="text-xs text-blue-600 hover:text-blue-700 hover:underline">
            Forgot password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="mt-2 flex items-center justify-center gap-2 rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition"
        >
          {loading && <Spinner size={4} />}
          {loading ? 'Signing in…' : 'Sign In'}
        </button>
      </form>

      <p className="mt-6 text-center text-sm text-slate-500">
        Don't have an account?{' '}
        <Link to="/register" className="text-blue-600 font-medium hover:underline">
          Create one
        </Link>
      </p>
    </AuthCard>
  )
}
