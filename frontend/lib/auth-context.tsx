"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"
import { useRouter } from "next/navigation"
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

// Storage keys
const STORAGE_KEY_USER = "leadflow_user"
const STORAGE_KEY_TOKEN = "leadflow_token"
const STORAGE_KEY_USERS = "leadflow_users" // Store registered users

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  const isAuthenticated = !!token && !!user

  // Restore session on mount
  useEffect(() => {
    const storedToken = localStorage.getItem(STORAGE_KEY_TOKEN)
    const storedUser = localStorage.getItem(STORAGE_KEY_USER)

    if (storedToken && storedUser) {
      setToken(storedToken)
      try {
        setUser(JSON.parse(storedUser))
      } catch {
        localStorage.removeItem(STORAGE_KEY_TOKEN)
        localStorage.removeItem(STORAGE_KEY_USER)
      }
    }
    setIsLoading(false)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    // Get registered users from localStorage
    const usersJson = localStorage.getItem(STORAGE_KEY_USERS)
    const users: Record<string, { name: string; password: string }> = usersJson ? JSON.parse(usersJson) : {}

    // Check if user exists
    const existingUser = users[email.toLowerCase()]
    if (!existingUser) {
      throw new Error("No account found with this email. Please sign up first.")
    }

    // Check password
    if (existingUser.password !== password) {
      throw new Error("Invalid password. Please try again.")
    }

    // Create session
    const newToken = "dummy_token_" + Date.now()
    const userData: User = {
      id: "user_" + Date.now(),
      name: existingUser.name,
      email: email.toLowerCase(),
      role: "admin",
      created_at: new Date().toISOString(),
    }

    localStorage.setItem(STORAGE_KEY_TOKEN, newToken)
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(userData))
    setToken(newToken)
    setUser(userData)
  }, [])

  const register = useCallback(async (name: string, email: string, password: string) => {
    // Get existing users
    const usersJson = localStorage.getItem(STORAGE_KEY_USERS)
    const users: Record<string, { name: string; password: string }> = usersJson ? JSON.parse(usersJson) : {}

    const emailLower = email.toLowerCase()

    // Check if already registered
    if (users[emailLower]) {
      throw new Error("An account with this email already exists. Please login instead.")
    }

    // Save user
    users[emailLower] = { name, password }
    localStorage.setItem(STORAGE_KEY_USERS, JSON.stringify(users))

    // Auto login after register
    const newToken = "dummy_token_" + Date.now()
    const userData: User = {
      id: "user_" + Date.now(),
      name,
      email: emailLower,
      role: "admin",
      created_at: new Date().toISOString(),
    }

    localStorage.setItem(STORAGE_KEY_TOKEN, newToken)
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(userData))
    setToken(newToken)
    setUser(userData)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY_TOKEN)
    localStorage.removeItem(STORAGE_KEY_USER)
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