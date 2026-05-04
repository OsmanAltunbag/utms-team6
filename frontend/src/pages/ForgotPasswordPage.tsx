import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { User, ArrowLeft, Mail } from 'lucide-react'
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Link
          to="/login"
          className="flex items-center gap-2 text-indigo-600 hover:text-indigo-700 mb-6 text-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to login
        </Link>

        <div className="bg-white rounded-xl shadow-lg p-8">
          {sent ? (
            <div className="text-center space-y-4">
              <div className="flex items-center justify-center mb-2">
                <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                  <Mail className="w-8 h-8 text-green-600" />
                </div>
              </div>
              <h2 className="text-xl font-semibold text-gray-900">Check Your Email</h2>
              <p className="text-gray-600 text-sm">
                If this email is registered, a password reset link has been sent.
              </p>
              <p className="text-gray-500 text-sm">
                Please check your inbox and follow the link to reset your password.
              </p>
              <Link
                to="/login"
                className="inline-block w-full bg-indigo-600 text-white py-2.5 px-4 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition-colors text-center"
              >
                Back to Login
              </Link>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-center mb-6">
                <User className="w-12 h-12 text-indigo-600" />
              </div>

              <h2 className="text-xl font-semibold text-gray-900 text-center mb-1">Forgot Password</h2>
              <p className="text-gray-500 text-sm text-center mb-6">Enter your email to reset your password.</p>

              <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                  <input
                    type="email"
                    autoComplete="email"
                    placeholder="Enter your email"
                    {...register('email')}
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                  {errors.email && <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>}
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-indigo-600 text-white py-2.5 px-4 rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Sending…' : 'Send Reset Link'}
                </button>

                <Link
                  to="/login"
                  className="block w-full text-center text-indigo-600 hover:text-indigo-700 text-sm"
                >
                  Back to Login
                </Link>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
