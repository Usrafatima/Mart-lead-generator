"use client"

import { useState, useEffect, useCallback } from "react"
import { jobsApi } from "@/lib/api-client"
import { CreateJobDialog } from "@/components/leads/create-job-dialog"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime, getScrapingStatusColor } from "@/lib/utils"
import { Bot, RefreshCw, Square, Loader2, MapPin, Globe, Smartphone, Clock, CheckCircle2, XCircle } from "lucide-react"
import { toast } from "sonner"
import type { ScrapingJob } from "@/types"

const botIcons: Record<string, typeof MapPin> = {
  google_maps: MapPin,
  website_scraper: Globe,
  social_scraper: Smartphone,
}

const botLabels: Record<string, string> = {
  google_maps: "Google Maps",
  website_scraper: "Website Scraper",
  social_scraper: "Social Media",
}

export default function ScrapingPage() {
  const [jobs, setJobs] = useState<ScrapingJob[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [stoppingId, setStoppingId] = useState<string | null>(null)

  const fetchJobs = useCallback(async () => {
    try {
      const response = await jobsApi.list()
      setJobs(response.data.data || response.data)
    } catch {
      toast.error("Failed to fetch jobs")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchJobs()
  }, [fetchJobs])

  async function handleStopJob(jobId: string) {
    setStoppingId(jobId)
    try {
      await jobsApi.stop(jobId)
      toast.success("Job stopped")
      fetchJobs()
    } catch {
      toast.error("Failed to stop job")
    } finally {
      setStoppingId(null)
    }
  }

  const activeJobs = jobs.filter((j) => j.status === "running" || j.status === "pending")

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Scraping Jobs</h2>
          <p className="text-sm text-muted-foreground">
            Manage automated lead collection from various sources
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={fetchJobs} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
          <CreateJobDialog onSuccess={fetchJobs} />
        </div>
      </div>

      {/* Active Jobs */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Bot className="h-4 w-4 text-blue-500" />
              Active Jobs
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{activeJobs.length}</p>
            <p className="text-xs text-muted-foreground">Currently running or pending</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              Completed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{jobs.filter((j) => j.status === "completed").length}</p>
            <p className="text-xs text-muted-foreground">Successfully finished</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <XCircle className="h-4 w-4 text-red-500" />
              Failed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{jobs.filter((j) => j.status === "failed").length}</p>
            <p className="text-xs text-muted-foreground">Encountered errors</p>
          </CardContent>
        </Card>
      </div>

      {/* Jobs List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg font-medium">
            All Jobs
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Bot className="h-12 w-12 text-muted-foreground/50" />
              <p className="mt-4 text-lg font-medium">No scraping jobs yet</p>
              <p className="text-sm text-muted-foreground">
                Start your first scraping job to collect leads
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {jobs.map((job) => {
                const Icon = botIcons[job.bot_type] || Bot
                return (
                  <div
                    key={job.id}
                    className="flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-accent/50"
                  >
                    <div className="flex items-start gap-4">
                      <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                        <Icon className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{botLabels[job.bot_type] || job.bot_type}</span>
                          <Badge variant="outline" className={getScrapingStatusColor(job.status)}>
                            {job.status}
                          </Badge>
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <MapPin className="h-3 w-3" />
                            {job.city}
                          </span>
                          <span>{job.category}</span>
                          {job.progress != null && (
                            <span>{job.progress}%</span>
                          )}
                          <span className="flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDateTime(job.created_at)}
                          </span>
                          {job.scraped_count != null && (
                            <span>{job.scraped_count} businesses scraped</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {job.status === "running" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleStopJob(job.id)}
                          disabled={stoppingId === job.id}
                        >
                          {stoppingId === job.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Square className="h-4 w-4" />
                          )}
                          Stop
                        </Button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
