import axios, { AxiosError, InternalAxiosRequestConfig } from "axios"
import type { Lead, CreateJobRequest } from "@/types"

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
})

// Request interceptor to attach JWT token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("auth_token")
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor to handle auth errors
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail: string }>) => {
    if (error.response?.status === 401) {
      if (typeof window !== "undefined") {
        localStorage.removeItem("auth_token")
        localStorage.removeItem("auth_user")
        // Only redirect if not already on an auth page
        if (!window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/register")) {
          window.location.href = "/login"
        }
      }
    }
    return Promise.reject(error)
  }
)

export default apiClient

// Auth API
export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post("/auth/login", { email, password }),

  register: (name: string, email: string, password: string) =>
    apiClient.post("/auth/register", { name, email, password }),

  me: () => apiClient.get("/auth/me"),
}

// Leads API
export const leadsApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get("/leads", { params }),

  getById: (id: string) =>
    apiClient.get(`/leads/${id}`),

  create: (data: Partial<Lead>) =>
    apiClient.post("/leads", data),

  update: (id: string, data: Partial<Lead>) =>
    apiClient.patch(`/leads/${id}`, data),

  delete: (id: string) =>
    apiClient.delete(`/leads/${id}`),

  bulkDelete: (ids: string[]) =>
    apiClient.post("/leads/bulk-delete", { ids }),

  exportCsv: (params?: Record<string, string | number | undefined>) =>
    apiClient.get("/leads/export/csv", { params, responseType: "blob" }),
}

// Scraping Jobs API
export const jobsApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get("/jobs", { params }),

  create: (data: CreateJobRequest) =>
    apiClient.post("/jobs", data),

  getById: (id: string) =>
    apiClient.get(`/jobs/${id}`),

  stop: (id: string) =>
    apiClient.post(`/jobs/${id}/stop`),
}

// Analytics API
export const analyticsApi = {
  summary: () =>
    apiClient.get("/analytics/summary"),
}

// Businesses API (for scraping tasks)
export const businessesApi = {
  list: (params?: Record<string, string | number | undefined>) =>
    apiClient.get("/businesses", { params }),
}

// Bots API
export const botsApi = {
  list: () =>
    apiClient.get("/bots"),
}

// Duplicate detection
export const duplicatesApi = {
  check: () =>
    apiClient.get("/leads/duplicates"),
}
