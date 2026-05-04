import { createContext, useContext, useState, type ReactNode } from 'react'

interface AuthState {
  role: string | null
  userName: string | null
}

interface AuthContextValue extends AuthState {
  setAuth: (role: string, userName: string) => void
  setRole: (role: string) => void
  clearAuth: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [role, setRoleState] = useState<string | null>(
    () => sessionStorage.getItem('role'),
  )
  const [userName, setUserNameState] = useState<string | null>(
    () => sessionStorage.getItem('userName'),
  )

  function setAuth(r: string, name: string) {
    sessionStorage.setItem('role', r)
    sessionStorage.setItem('userName', name)
    setRoleState(r)
    setUserNameState(name)
  }

  function setRole(r: string) {
    sessionStorage.setItem('role', r)
    setRoleState(r)
  }

  function clearAuth() {
    sessionStorage.removeItem('role')
    sessionStorage.removeItem('userName')
    setRoleState(null)
    setUserNameState(null)
  }

  return (
    <AuthContext.Provider value={{ role, userName, setAuth, setRole, clearAuth }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
