export type UserRole = 'admin' | 'doctor' | 'nurse' | 'operator'

export interface AuthUser {
  id: number
  username: string
  email: string
  role: UserRole
  is_active: boolean
}

export interface LoginRequest {
  username: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}