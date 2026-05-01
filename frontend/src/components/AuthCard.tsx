import type { ReactNode } from 'react'

interface Props {
  title: string
  subtitle?: string
  children: ReactNode
}

export default function AuthCard({ title, subtitle, children }: Props) {
  return (
    <div className="relative min-h-screen flex items-center justify-center bg-slate-100 overflow-hidden p-4">

      {/* Blob 1 — top-left, blue */}
      <div className="pointer-events-none absolute -top-32 -left-32 w-[520px] h-[520px] rounded-full bg-blue-300/30 blur-[120px]" />
      {/* Blob 2 — bottom-right, slate/indigo */}
      <div className="pointer-events-none absolute -bottom-40 -right-24 w-[480px] h-[480px] rounded-full bg-slate-400/25 blur-[110px]" />
      {/* Blob 3 — center-right, lighter blue accent */}
      <div className="pointer-events-none absolute top-1/2 -translate-y-1/2 right-0 w-[320px] h-[320px] rounded-full bg-blue-200/20 blur-[90px]" />

      <div className="relative w-full max-w-md">
        {/* Brand header */}
        <div className="mb-6 text-center">
          <div className="inline-flex items-center justify-center w-11 h-11 rounded-xl bg-blue-600 mb-3 shadow-lg shadow-blue-500/30">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
              <path d="M6 12v5c3 3 9 3 12 0v-5"/>
            </svg>
          </div>
          <h1 className="text-base font-bold text-slate-800 tracking-tight leading-tight">
            Undergraduate Management System
          </h1>
          <p className="text-slate-500 text-xs mt-1">İzmir Institute of Technology</p>
        </div>

        {/* Glassmorphism card */}
        <div className="bg-white/70 backdrop-blur-lg border border-white/50 rounded-2xl shadow-xl shadow-slate-200/60 p-8">
          <h2 className="text-xl font-bold text-slate-800 mb-1">{title}</h2>
          {subtitle && <p className="text-sm text-slate-500 mb-6">{subtitle}</p>}
          {children}
        </div>
      </div>
    </div>
  )
}
