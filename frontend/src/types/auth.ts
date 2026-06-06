export interface TokenResponse {
  token_type: string
  role: string
  must_change_password: boolean
}

export interface MeResponse {
  id: string
  email: string
  role: string
  first_name: string
  last_name: string
  must_change_password: boolean
}

export interface ApiError {
  detail: string | ValidationError[]
}

export interface ValidationError {
  loc: (string | number)[]
  msg: string
  type: string
}
