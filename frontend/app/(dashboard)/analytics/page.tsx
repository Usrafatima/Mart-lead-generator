"use client"

import { useState, useEffect, useCallback } from "react"
import { analyticsApi } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts"
import {
  Users,
  Star,
  TrendingUp,
  Bot,
  RefreshCw,
  Download,
} from "lucide-react"
import { toast } from "sonner"
import type { AnalyticsSummary } from "@/types"

const COLORS = {
  high: "#ef4444",
  medium: "#f59e0b",
  low: "#22c55e",
  pending: "#6b7280",
  contacted: "#3b82f6",
  qualified: "#a855f7",
  converted: "#22c55e",
  lost: "#ef4444",
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchAnalytics = useCallback(async () => {
    setIsLoading(true)
    try {
      const response = await analyticsApi.summary()
      setData(response.data)
    } catch {
      toast.error("Failed to load analytics")
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAnalytics()
  }, [fetchAnalytics])

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-48" />
          <Skeleton className="mt-1 h-4 w-72" />
        </div>
        <div className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-80" />
          ))}
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <TrendingUp className="h-16 w-16 text-muted-foreground/50" />
        <p className="mt-4 text-lg font-medium">No analytics data yet</p>
        <p className="text-sm text-muted-foreground">Start collecting leads to see analytics</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Analytics</h2>
          <p className="text-sm text-muted-foreground">
            Insights and metrics for your lead generation
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={fetchAnalytics}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm">
            <Download className="mr-1 h-4 w-4" />
            Export
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Leads
            </CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{data.total_leads}</p>
            <p className="text-xs text-muted-foreground">All collected leads</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg. Rating
            </CardTitle>
            <Star className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {data.avg_rating != null ? data.avg_rating.toFixed(1) : "—"}
            </p>
            <p className="text-xs text-muted-foreground">Average Google rating</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Jobs
            </CardTitle>
            <Bot className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{data.total_scraping_jobs}</p>
            <p className="text-xs text-muted-foreground">Scraping jobs created</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Active Jobs
            </CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">{data.active_jobs}</p>
            <p className="text-xs text-muted-foreground">Currently running</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Leads by Priority */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">Leads by Priority</CardTitle>
          </CardHeader>
          <CardContent>
            {data.leads_by_priority.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
                No data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={data.leads_by_priority}
                    dataKey="count"
                    nameKey="priority"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label={(entry: any) => `${entry.priority} (${entry.count})`}
                  >
                    {data.leads_by_priority.map((entry) => (
                      <Cell
                        key={entry.priority}
                        fill={COLORS[entry.priority as keyof typeof COLORS] || "#6b7280"}
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Leads by City */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">Leads by City</CardTitle>
          </CardHeader>
          <CardContent>
            {data.leads_by_city.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
                No data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data.leads_by_city}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="city" className="text-xs" />
                  <YAxis className="text-xs" />
                  <Tooltip />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Leads by Call Status */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">Leads by Call Status</CardTitle>
          </CardHeader>
          <CardContent>
            {data.leads_by_call_status.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
                No data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={data.leads_by_call_status}
                    dataKey="count"
                    nameKey="call_status"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label={(entry: any) => `${entry.call_status} (${entry.count})`}
                  >
                    {data.leads_by_call_status.map((entry) => (
                      <Cell
                        key={entry.call_status}
                        fill={COLORS[entry.call_status as keyof typeof COLORS] || "#6b7280"}
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Leads by Business Type */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base font-medium">Leads by Business Type</CardTitle>
          </CardHeader>
          <CardContent>
            {data.leads_by_business_type.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
                No data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data.leads_by_business_type}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="business_type" className="text-xs" />
                  <YAxis className="text-xs" />
                  <Tooltip />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
