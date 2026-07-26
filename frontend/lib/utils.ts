import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateString: string | null): string {
  if (!dateString) return "—"
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export function formatDateTime(dateString: string | null): string {
  if (!dateString) return "—"
  return new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function getLeadPriorityColor(priority: string): string {
  switch (priority) {
    case "high":
      return "text-red-600 border-red-200 bg-red-50 dark:bg-red-950/30 dark:border-red-800 dark:text-red-400"
    case "medium":
      return "text-amber-600 border-amber-200 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-400"
    case "low":
      return "text-green-600 border-green-200 bg-green-50 dark:bg-green-950/30 dark:border-green-800 dark:text-green-400"
    default:
      return "text-gray-600 border-gray-200 bg-gray-50 dark:bg-gray-950/30 dark:border-gray-800 dark:text-gray-400"
  }
}

export function getCallStatusColor(status: string): string {
  switch (status) {
    case "pending":
      return "text-gray-600 border-gray-200 bg-gray-50 dark:bg-gray-950/30 dark:border-gray-800 dark:text-gray-400"
    case "contacted":
      return "text-blue-600 border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-800 dark:text-blue-400"
    case "qualified":
      return "text-purple-600 border-purple-200 bg-purple-50 dark:bg-purple-950/30 dark:border-purple-800 dark:text-purple-400"
    case "converted":
      return "text-green-600 border-green-200 bg-green-50 dark:bg-green-950/30 dark:border-green-800 dark:text-green-400"
    case "lost":
      return "text-red-600 border-red-200 bg-red-50 dark:bg-red-950/30 dark:border-red-800 dark:text-red-400"
    default:
      return "text-gray-600 border-gray-200 bg-gray-50 dark:bg-gray-950/30 dark:border-gray-800 dark:text-gray-400"
  }
}

export function getScrapingStatusColor(status: string): string {
  switch (status) {
    case "completed":
      return "text-green-600 border-green-200 bg-green-50 dark:bg-green-950/30 dark:border-green-800 dark:text-green-400"
    case "running":
      return "text-blue-600 border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-800 dark:text-blue-400"
    case "pending":
      return "text-amber-600 border-amber-200 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-400"
    case "failed":
      return "text-red-600 border-red-200 bg-red-50 dark:bg-red-950/30 dark:border-red-800 dark:text-red-400"
    default:
      return "text-gray-600 border-gray-200 bg-gray-50 dark:bg-gray-950/30 dark:border-gray-800 dark:text-gray-400"
  }
}
