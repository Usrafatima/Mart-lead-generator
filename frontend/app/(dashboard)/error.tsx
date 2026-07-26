"use client"

import { Button } from "@/components/ui/button"
import { AlertTriangle } from "lucide-react"

export default function DashboardError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string }
  unstable_retry: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
        <AlertTriangle className="h-8 w-8 text-destructive" />
      </div>
      <h2 className="text-xl font-semibold">Dashboard Error</h2>
      <p className="mt-2 text-sm text-muted-foreground max-w-md text-center">
        Something went wrong while loading this page. Please try again.
      </p>
      <Button onClick={() => unstable_retry()} className="mt-6">
        Try Again
      </Button>
    </div>
  )
}
