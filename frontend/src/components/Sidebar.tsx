import { GraduationCap, LogOut } from 'lucide-react'

interface SidebarProps {
  userName: string
  role: string
  onLogout: () => void
  children?: React.ReactNode
}

export function Sidebar({ userName, role, onLogout, children }: SidebarProps) {
  return (
    <div className="w-64 bg-indigo-900 text-white min-h-screen p-6 flex flex-col flex-shrink-0">
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-6">
          <GraduationCap className="w-8 h-8" />
          <span className="text-sm font-medium">UTMS</span>
        </div>
        <div className="border-t border-indigo-700 pt-4">
          <p className="text-indigo-300 text-xs mb-1">Logged in as</p>
          <p className="font-medium text-sm truncate">{userName}</p>
          <p className="text-indigo-300 text-xs mt-1">{role}</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1">{children}</nav>

      <button
        onClick={onLogout}
        className="flex items-center gap-2 text-indigo-300 hover:text-white transition-colors mt-auto pt-4"
      >
        <LogOut className="w-5 h-5" />
        <span className="text-sm">Logout</span>
      </button>
    </div>
  )
}
