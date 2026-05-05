import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { AxiosError } from 'axios'
import { User, Eye, EyeOff, ArrowLeft, Mail } from 'lucide-react'
import { register as registerUser ,extractErrorMessage } from '../api/auth'

// ─── Types ───────────────────────────────────────────────────────────────────
type RegisterFormData = {
    full_name: string
    email: string
    phone: string
    password: string
    password_confirm: string
}

// ─── Phone mask helper: formats input as (5xx) xxx-xxxx ──────────────────────
function formatPhone(value: string): string {
    const digits = value.replace(/\D/g, '').slice(0, 10)
    if (digits.length <= 3) return digits.length ? `(${digits}` : ''
    if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`
}

// ─── Shared input className ───────────────────────────────────────────────────
const inputCls =
    'w-full px-4 py-2.5 border border-gray-200 rounded-lg text-sm bg-gray-50 ' +
    'focus:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 ' +
    'focus:border-transparent transition-colors placeholder:text-gray-400'

export default function RegisterPage() {
    const [loading, setLoading] = useState(false)
    const [success, setSuccess] = useState(false)
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirm, setShowConfirm] = useState(false)
    const [phoneDisplay, setPhoneDisplay] = useState('')

    const {
        register,
        handleSubmit,
        watch,
        setValue,
        formState: { errors },
    } = useForm<RegisterFormData>()

    // ─── Submit ─────────────────────────────────────────────────────────────────
    async function onSubmit(data: RegisterFormData) {
        setLoading(true)
        try {
            await registerUser(data)
            setSuccess(true)
        } catch (err) {
            const status = err instanceof AxiosError ? err.response?.status : null
            if (status === 409) {
                toast.error('An account with this information already exists.')
            } else {
                toast.error(extractErrorMessage(err))
            }
        } finally {
            setLoading(false)
        }
    }

    // ─── Success screen ──────────────────────────────────────────────────────────
    if (success) {
        return (
            <div className="min-h-screen bg-[#dde6f5] flex items-center justify-center p-4">
                <div className="w-full max-w-md">
                    <div className="bg-white rounded-2xl shadow-md p-8 text-center">
                        <div className="flex items-center justify-center mb-4">
                            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
                                <Mail className="w-8 h-8 text-green-600" />
                            </div>
                        </div>
                        <h2 className="text-xl font-semibold text-gray-900 mb-2">Check Your Email</h2>
                        <p className="text-gray-600 text-sm mb-2">Account created successfully.</p>
                        <p className="text-gray-500 text-sm mb-6">
                            Please check your email for the verification link before signing in.
                        </p>
                        <Link
                            to="/login"
                            className="inline-block bg-indigo-700 text-white px-6 py-2.5 rounded-lg text-sm font-semibold hover:bg-indigo-800 transition-colors"
                        >
                            Go to Login
                        </Link>
                    </div>
                </div>
            </div>
        )
    }

    // ─── Main form ───────────────────────────────────────────────────────────────
    return (
        <div className="min-h-screen bg-[#dde6f5] flex items-center justify-center p-4">
            <div className="w-full max-w-md">

                {/* Back navigation */}
                <Link
                    to="/role-select"
                    className="flex items-center gap-1.5 text-indigo-700 hover:text-indigo-800 mb-5 text-sm"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to role selection
                </Link>

                <div className="bg-white rounded-2xl shadow-md p-8">

                    {/* Header */}
                    <div className="flex flex-col items-center mb-7">
                        <div className="mb-3">
                            <User className="w-10 h-10 text-indigo-700" strokeWidth={1.8} />
                        </div>
                        <h1 className="text-lg font-semibold text-gray-900">Applicant Registration</h1>
                        <p className="text-gray-500 text-sm mt-1 text-center">
                            Create an account to apply for transfer to IZTECH.
                        </p>
                    </div>

                    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">

                        {/* Full Name */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                            <input
                                type="text"
                                autoComplete="name"
                                placeholder="Ahmet Yılmaz"
                                {...register('full_name', {
                                    required: 'Full name is required.',
                                    minLength: { value: 3, message: 'Name must be at least 3 characters.' },
                                })}
                                className={inputCls}
                            />
                            {errors.full_name && (
                                <p className="mt-1 text-xs text-red-600">{errors.full_name.message}</p>
                            )}
                        </div>

                        {/* Email — must end with .edu */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                            <input
                                type="email"
                                autoComplete="email"
                                placeholder="you@university.edu"
                                {...register('email', {
                                    required: 'Email is required.',
                                    // Real-time .edu domain check
                                    validate: (val) =>
                                        val.toLowerCase().endsWith('.edu') ||
                                        val.toLowerCase().endsWith('.edu.tr') ||
                                        'Please use a valid institutional (.edu or .edu.tr) email address to register.',
                                })}
                                className={inputCls}
                            />
                            {errors.email && (
                                <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
                            )}
                        </div>

                        {/* Phone — masked as (5xx) xxx-xxxx */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
                            <input
                                type="tel"
                                inputMode="numeric"
                                placeholder="(5xx) xxx-xxxx"
                                value={phoneDisplay}
                                {...register('phone', {
                                    required: 'Phone number is required.',
                                    validate: (val) =>
                                        val.replace(/\D/g, '').length === 10 || 'Enter a valid 10-digit phone number.',
                                })}
                                onChange={(e) => {
                                    // Apply mask on each keystroke, store raw digits in form state
                                    const masked = formatPhone(e.target.value)
                                    setPhoneDisplay(masked)
                                    setValue('phone', masked, { shouldValidate: true })
                                }}
                                className={inputCls}
                            />
                            {errors.phone && (
                                <p className="mt-1 text-xs text-red-600">{errors.phone.message}</p>
                            )}
                        </div>

                        {/* Password */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                            <div className="relative">
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    autoComplete="new-password"
                                    placeholder="••••••••"
                                    {...register('password', {
                                        required: 'Password is required.',
                                        minLength: { value: 8, message: 'At least 8 characters.' },
                                        pattern: {
                                            value: /^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9])/,
                                            message: 'Needs uppercase, a digit, and a special character.',
                                        },
                                    })}
                                    className={`${inputCls} pr-10`}
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                    tabIndex={-1}
                                >
                                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                </button>
                            </div>
                            {errors.password && (
                                <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
                            )}
                        </div>

                        {/* Confirm Password — must match */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
                            <div className="relative">
                                <input
                                    type={showConfirm ? 'text' : 'password'}
                                    autoComplete="new-password"
                                    placeholder="••••••••"
                                    {...register('password_confirm', {
                                        required: 'Please confirm your password.',
                                        // Cross-field match check
                                        validate: (val) =>
                                            val === watch('password') || 'Passwords do not match.',
                                    })}
                                    className={`${inputCls} pr-10`}
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowConfirm(!showConfirm)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                                    tabIndex={-1}
                                >
                                    {showConfirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                </button>
                            </div>
                            {errors.password_confirm && (
                                <p className="mt-1 text-xs text-red-600">{errors.password_confirm.message}</p>
                            )}
                        </div>

                        {/* Submit */}
                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-indigo-700 text-white py-2.5 px-4 rounded-lg text-sm font-semibold hover:bg-indigo-800 disabled:opacity-60 disabled:cursor-not-allowed transition-colors mt-1"
                        >
                            {loading ? 'Creating account…' : 'Register'}
                        </button>
                    </form>

                    {/* Footer */}
                    <div className="mt-5 text-center">
                        <Link to="/login" className="text-indigo-600 hover:text-indigo-700 text-sm">
                            Already have an account? Login
                        </Link>
                    </div>
                </div>
            </div>
        </div>
    )
}