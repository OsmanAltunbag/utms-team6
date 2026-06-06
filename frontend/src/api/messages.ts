import axios from 'axios'

const client = axios.create({
  baseURL: '/api/messages',
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

export interface Reply {
  id: string
  body: string
  staff_name: string
  created_at: string
}

export interface Question {
  id: string
  subject: string
  body: string
  application_id: string | null
  applicant_name: string | null
  is_resolved: boolean
  created_at: string
  replies: Reply[]
}

// Applicant
export async function listMyQuestions(): Promise<Question[]> {
  const { data } = await client.get<Question[]>('')
  return data
}

export async function createQuestion(payload: {
  subject: string
  body: string
  application_id?: string | null
}): Promise<Question> {
  const { data } = await client.post<Question>('', payload)
  return data
}

// Student Affairs
export async function listAllQuestions(): Promise<Question[]> {
  const { data } = await client.get<Question[]>('/all')
  return data
}

export async function replyToQuestion(questionId: string, body: string): Promise<Question> {
  const { data } = await client.post<Question>(`/${questionId}/replies`, { body })
  return data
}
