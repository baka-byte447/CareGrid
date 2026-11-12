import { useState, useEffect, useCallback, type ReactNode } from 'react'
import { AuthContext } from './AuthContext'
import type { AuthUser, LoginRequest, TokenResponse } from './types'
import {
  apiPost,
  apiGet,
  setAccessToken,
  getAccessToken,
  clearAccessToken,
} from '../api/client'
interface AuthProviderProps {
  children: ReactNode
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const logout = useCallback(() => {
    clearAccessToken()
    setUser(null)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const credentials: LoginRequest = { username, password }

    const tokenResponse = await apiPost<TokenResponse>(
      '/auth/login',
      credentials,
    )

    setAccessToken(tokenResponse.access_token)

    try {
      const currentUser = await apiGet<AuthUser>('/auth/me')
      setUser(currentUser)
    } catch (error) {
      clearAccessToken()
      setUser(null)
      throw error
    }
  }, [])

  useEffect(() => {
    const restoreSession = async () => {
      const token = getAccessToken()

      if (!token) {
        setIsLoading(false)
        return
      }

      try {
        const currentUser = await apiGet<AuthUser>('/auth/me')
        setUser(currentUser)
      } catch {
        clearAccessToken()
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    void restoreSession()
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}