export interface ApplicantResult {
  application_id: string
  position: number
  composite_score: number
  first_name?: string
  last_name?: string
  email?: string
}

export type RankingStatus = 'DRAFT' | 'APPROVED' | 'PUBLISHED'

export interface ResultsResponse {
  ranking_id: string
  status: RankingStatus
  published_at: string | null
  primary: ApplicantResult[]
  waitlisted: ApplicantResult[]
}

export interface PublishResultsResponse {
  announced_count: number
}
