import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useParams, useNavigate, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { AxiosError } from 'axios'
import { GraduationCap, Eye, EyeOff, AlertTriangle } from 'lucide-react'
import { resetPasswordSchema, type ResetPasswordFormData } from '../schemas/auth'
import { resetPassword, extractErrorMessage } from '../api/auth'

export default function ResetPasswordPage() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [expired, setExpired] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <GraduationCap className="w-10 h-10 text-indigo-600 mx-auto mb-2" />
          <p className="text-indigo-900 font-semibold">IZTECH UTMS</p>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-8">
          {expired ? (
            <div className="text-center space-y-4">
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
                <AlertTriangle className="w-8 h-8 text-red-500" />
              </div>
              <h2 className="text-xl font-semibold text-gray-900">Link Expired</h2>
              <p className="text-gray-500 text-sm">This password reset link has expired. Please request a new one.</p>
              <Link
                to="/forgot-password"
                className="inline-block w-full bg-indigo-600 text-white py-2.5 px-4 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition-colors text-center"
              >
                Request New Link
              </Link>
            </div>
          ) : (
            <>
              <h2 className="text-xl font-semibold text-gray-900 text-center mb-1">Set New Password</h2>
              <p className="text-gray-500 text-sm text-center mb-6">Enter a strong new password for your account</p>

              <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      placeholder="••••••••"
                      {...register('new_password')}
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent pr-10"
                    />
                    <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600" tabIndex={-1}>
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.new_password && <p className="mt-1 text-xs text-red-600">{errors.new_password.message}</p>}
                  <div className="mt-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                    <p className="text-xs text-gray-500">Min 8 chars · One uppercase · One digit · One special character</p>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
                  <div className="relative">
                    <input
                      type={showConfirm ? 'text' : 'password'}
                      autoComplete="new-password"
                      placeholder="••••••••"
                      {...register('new_password_confirm')}
                      className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent pr-10"
                    />
                    <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600" tabIndex={-1}>
                      {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.new_password_confirm && <p className="mt-1 text-xs text-red-600">{errors.new_password_confirm.message}</p>}
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full bg-indigo-600 text-white py-2.5 px-4 rounded-lg text-sm font-semibold hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Updating…' : 'Update Password'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
