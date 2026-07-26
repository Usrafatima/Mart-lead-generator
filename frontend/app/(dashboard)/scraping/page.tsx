"use client"

import { useState, useEffect, useCallback } from "react"
import { jobsApi } from "@/lib/api-client"
import { CreateJobDialog } from "@/components/leads/create-job-dialog"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { formatDateTime, getScrapingStatusColor } from "@/lib/utils"
import {
  Bot,
  RefreshCw,
  Square,
  Loader2,
  MapPin,
  Globe,
  Smartphone,
  Clock,
  CheckCircle2,
  XCircle,
  Activity,
} from "lucide-react"
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
  const completedJobs = jobs.filter((j) => j.status === "completed")
  const failedJobs = jobs.filter((j) => j.status === "failed")

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Scraping Jobs</h2>
          <p className="text-base text-muted-foreground">Manage automated lead collection from various sources</p>
        </div>
        <div className="flex items-center gap-2 mt-2 sm:mt-0">
          <Button variant="outline" size="icon" onClick={fetchJobs} disabled={isLoading} className="h-9 w-9">
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
          <CreateJobDialog onSuccess={fetchJobs} />
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-3 sm:gap-4 grid-cols-1 sm:grid-cols-3">
        <Card className="border shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 pt-4 px-4">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Active Jobs
            </CardTitle>
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-500/10">
              <Activity className="h-3.5 w-3.5 text-blue-500" />
            </div>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <p className="text-2xl font-bold">{activeJobs.length}</p>
            <p className="text-xs text-muted-foreground mt-0.5">Running or pending</p>
          </CardContent>
        </Card>
        <Card className="border shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 pt-4 px-4">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Completed
            </CardTitle>
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-green-500/10">
              <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
            </div>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <p className="text-2xl font-bold">{completedJobs.length}</p>
            <p className="text-xs text-muted-foreground mt-0.5">Successfully finished</p>
          </CardContent>
        </Card>
        <Card className="border shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 pt-4 px-4">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Failed
            </CardTitle>
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-red-500/10">
              <XCircle className="h-3.5 w-3.5 text-red-500" />
            </div>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <p className="text-2xl font-bold">{failedJobs.length}</p>
            <p className="text-xs text-muted-foreground mt-0.5">Encountered errors</p>
          </CardContent>
        </Card>
      </div>

      {/* Jobs List */}
      <Card className="border shadow-sm overflow-hidden">
        <CardHeader className="border-b bg-muted/20 pb-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
              <Bot className="h-4 w-4 text-primary" />
            </div>
            All Jobs
            {!isLoading && (
              <span className="ml-auto text-xs font-normal text-muted-foreground">{jobs.length} total</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-6">
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full rounded-xl" />
              ))}
            </div>
          ) : jobs.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/50">
                <Bot className="h-7 w-7 text-muted-foreground/60" />
              </div>
              <p className="mt-4 text-base font-semibold">No scraping jobs yet</p>
              <p className="mt-1 text-sm text-muted-foreground max-w-sm">
                Start your first scraping job to begin collecting leads from Google Maps, websites, or social media.
              </p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {jobs.map((job) => {
                const Icon = botIcons[job.bot_type] || Bot
                return (
                  <div
                    key={job.id}
                    className="group flex items-center justify-between rounded-xl border bg-card p-4 transition-all duration-200 hover:border-primary/20 hover:shadow-sm"
                  >
                    <div className="flex items-start gap-3 min-w-0">
                      <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-primary/10 to-primary/5">
                        <Icon className="h-5 w-5 text-primary" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-semibold">{botLabels[job.bot_type] || job.bot_type}</span>
                          <Badge variant="outline" className={`text-[11px] px-2 py-0 font-medium ${getScrapingStatusColor(job.status)}`}>
                            {job.status}
                          </Badge>
                        </div>
                        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                          <span className="inline-flex items-center gap-1">
                            <MapPin className="h-3 w-3" />
                            {job.city}
                          </span>
                          <span className="text-muted-foreground/60">·</span>
                          <span>{job.category}</span>
                          {job.progress != null && (
                            <>
                              <span className="text-muted-foreground/60">·</span>
                              <span className="font-medium text-foreground/70">{job.progress}%</span>
                            </>
                          )}
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {formatDateTime(job.created_at)}
                          </span>
                          {job.scraped_count != null && (
                            <>
                              <span className="text-muted-foreground/60">·</span>
                              <span>{job.scraped_count} scraped</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      {job.status === "running" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleStopJob(job.id)}
                          disabled={stoppingId === job.id}
                          className="h-8 text-xs"
                        >
                          {stoppingId === job.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                          ) : (
                            <Square className="h-3.5 w-3.5 mr-1" />
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