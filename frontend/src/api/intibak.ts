import axios from 'axios'

const client = axios.create({
  baseURL: '/api/ygk',
  withCredentials: true,
  timeout: 15000,
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

export interface ParsedCourse {
  course_code: string
  course_name: string
  credits: number
  grade: string
  semester: string
}

export type EquivalenceType = 'FULL' | 'PARTIAL' | 'NONE'

export interface CourseMapping {
  id: string
  source_course_code: string | null
  source_course_name: string
  source_credits: number
  target_course_code: string | null
  target_course_name: string | null
  target_credits: number | null
  equivalence_type: EquivalenceType
  notes: string | null
}

export interface IntibakTable {
  id: string
  application_id: string
  status: string
  mappings: CourseMapping[]
}

export interface SuggestedCourse {
  course_code: string
  course_name: string
  credits: number
}

export async function createIntibakTable(applicationId: string): Promise<IntibakTable> {
  const { data } = await client.post<IntibakTable>(`/applications/${applicationId}/intibak`)
  return data
}

export async function getIntibakTable(tableId: string): Promise<IntibakTable> {
  const { data } = await client.get<IntibakTable>(`/intibak/${tableId}`)
  return data
}

export async function getIntibakTableByApplication(applicationId: string): Promise<IntibakTable> {
  const { data } = await client.get<IntibakTable>(`/applications/${applicationId}/intibak`)
  return data
}

export async function parseTranscript(tableId: string): Promise<{ courses: ParsedCourse[] }> {
  const { data } = await client.post<{ courses: ParsedCourse[] }>(`/intibak/${tableId}/parse-transcript`)
  return data
}

export async function suggestMatch(
  courseName: string,
  programId: string,
): Promise<SuggestedCourse[]> {
  const { data } = await client.get<SuggestedCourse[]>('/intibak/suggest-match', {
    params: { course_name: courseName, program_id: programId },
  })
  return data
}

export async function addMapping(
  tableId: string,
  payload: {
    source_course_code?: string
    source_course_name: string
    source_credits: number
    target_course_code?: string
    target_course_name?: string
    target_credits?: number
    equivalence_type: EquivalenceType
    notes?: string
  },
): Promise<CourseMapping> {
  const { data } = await client.post<CourseMapping>(`/intibak/${tableId}/mappings`, payload)
  return data
}

export async function updateMapping(
  tableId: string,
  mappingId: string,
  payload: {
    target_course_code?: string
    target_course_name?: string
    target_credits?: number
    equivalence_type?: EquivalenceType
    notes?: string
  },
): Promise<CourseMapping> {
  const { data } = await client.put<CourseMapping>(
    `/intibak/${tableId}/mappings/${mappingId}`,
    payload,
  )
  return data
}

export async function submitIntibakTable(tableId: string): Promise<IntibakTable> {
  const { data } = await client.post<IntibakTable>(`/intibak/${tableId}/submit`)
  return data
}
