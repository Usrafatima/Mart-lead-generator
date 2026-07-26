// Lead types based on README data model
export interface Lead {
  id: string
  business_name: string
  business_type: string
  country: string
  city: string
  address: string
  phone: string
  email: string
  website: string
  website_url: string
  owner_manager: string
  social_media_links: string
  order_method: string
  delivery_system: string
  automation_status: string
  google_rating: number | null
  reviews_count: number | null
  lead_priority: LeadPriority
  notes: string
  call_status: CallStatus
  follow_up_date: string | null
  created_at: string
  updated_at: string
}

export type LeadPriority = "high" | "medium" | "low"
export type CallStatus = "pending" | "contacted" | "qualified" | "converted" | "lost"
export type AutomationStatus = "automated" | "semi-automated" | "manual"
export type OrderMethod = "online" | "phone" | "in-person" | "whatsapp" | "unknown"
export type DeliverySystem = "in-house" | "third-party" | "both" | "none"
export type ScrapingJobStatus = "pending" | "running" | "completed" | "failed"

export interface User {
  id: string
  name: string
  email: string
  role: "admin" | "user"
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user: User
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  name: string
  email: string
  password: string
}

export interface ScrapingJob {
  id: string
  bot_type: "google_maps" | "social_scraper" | "website_scraper"
  city: string
  category: string
  status: ScrapingJobStatus
  progress: number
  total_businesses: number | null
  scraped_count: number | null
  error_message: string | null
  created_by: string
  created_at: string
  updated_at: string
  completed_at: string | null
}

export interface CreateJobRequest {
  bot_type: string
  city: string
  category: string
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ApiError {
  detail: string
  status_code: number
}

export interface AnalyticsSummary {
  total_leads: number
  leads_by_priority: { priority: string; count: number }[]
  leads_by_city: { city: string; count: number }[]
  leads_by_business_type: { business_type: string; count: number }[]
  leads_by_call_status: { call_status: string; count: number }[]
  avg_rating: number | null
  total_scraping_jobs: number
  active_jobs: number
}

export interface LeadFilters {
  search?: string
  city?: string
  business_type?: string
  lead_priority?: LeadPriority
  call_status?: CallStatus
  automation_status?: AutomationStatus
  page?: number
  page_size?: number
  sort_by?: string
  sort_order?: "asc" | "desc"
}
