import axios from 'axios'
import type { ResultsResponse, PublishResultsResponse } from '../types/staff'

const client = axios.create({
  baseURL: '/api/staff',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

let _refreshing: Promise<void> | null = null

client.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        if (!_refreshing) {
          _refreshing = axios
            .post('/api/auth/refresh', {}, { withCredentials: true })
            .then(() => { _refreshing = null })
            .catch((e) => { _refreshing = null; throw e })
        }
        await _refreshing
        return client(original)
      } catch {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export async function getResults(
  periodId: string,
  programId: string,
): Promise<ResultsResponse> {
  const { data } = await client.get<ResultsResponse>(`/results/${periodId}/${programId}`)
  return data
}

export async function publishResults(
  periodId: string,
  programId: string,
): Promise<PublishResultsResponse> {
  const { data } = await client.post<PublishResultsResponse>(
    `/results/${periodId}/${programId}/publish`,
  )
  return data
}
