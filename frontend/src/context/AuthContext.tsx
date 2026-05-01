import { createContext, useContext, useState, type ReactNode } from 'react'

interface AuthState {
  role: string | null
}

interface AuthContextValue extends AuthState {
  setRole: (role: string) => void
  clearAuth: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<string | null>(
    () => sessionStorage.getItem('role'),
  )

  function setRole(r: string) {
    sessionStorage.setItem('role', r)
    setRoleState(r)
  }

  function clearAuth() {
    sessionStorage.removeItem('role')
    setRoleState(null)
  }

  return (
    <AuthContext.Provider value={{ role, setRole, clearAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
