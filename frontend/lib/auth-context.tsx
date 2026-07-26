"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { useRouter } from "next/navigation"
import { authApi } from "./api-client"
import type { User } from "@/types"

interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  const isAuthenticated = !!token && !!user

  // Restore session on mount
  useEffect(() => {
    const storedToken = localStorage.getItem("auth_token")
    const storedUser = localStorage.getItem("auth_user")

    if (storedToken && storedUser) {
      setToken(storedToken)
      try {
        setUser(JSON.parse(storedUser))
      } catch {
        localStorage.removeItem("auth_token")
        localStorage.removeItem("auth_user")
      }
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const response = await authApi.login(email, password)
    const { access_token, user: userData } = response.data

    localStorage.setItem("auth_token", access_token)
    localStorage.setItem("auth_user", JSON.stringify(userData))

    setToken(access_token)
    setUser(userData)
  }, [])

  const register = useCallback(async (name: string, email: string, password: string) => {
    const response = await authApi.register(name, email, password)
    const { access_token, user: userData } = response.data

    localStorage.setItem("auth_token", access_token)
    localStorage.setItem("auth_user", JSON.stringify(userData))

    setToken(access_token)
    setUser(userData)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem("auth_token")
    localStorage.removeItem("auth_user")
    setToken(null)
    setUser(null)
    router.push("/login")
  }, [router])

  return (
    <AuthContext.Provider value={{ user, token, isLoading, isAuthenticated, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider")
  }
  return context
}
