import axios from 'axios'
import type { StaffMember, StaffCreatePayload, RoleUpdatePayload } from '../types/admin'

const client = axios.create({
  baseURL: '/api/admin',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        await axios.post('/api/auth/refresh', {}, { withCredentials: true })
        return client(original)
      } catch {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export async function listStaff(): Promise<StaffMember[]> {
  const { data } = await client.get<StaffMember[]>('/staff')
  return data
}

export async function createStaff(payload: StaffCreatePayload): Promise<StaffMember> {
  const { data } = await client.post<StaffMember>('/staff', payload)
  return data
}

export async function updateStaffRole(staffId: string, payload: RoleUpdatePayload): Promise<StaffMember> {
  const { data } = await client.patch<StaffMember>(`/staff/${staffId}/role`, payload)
  return data
}

export async function deactivateStaff(staffId: string): Promise<void> {
  await client.delete(`/staff/${staffId}`)
}

export async function activateStaff(staffId: string): Promise<StaffMember> {
  const { data } = await client.post<StaffMember>(`/staff/${staffId}/activate`)
  return data
}
