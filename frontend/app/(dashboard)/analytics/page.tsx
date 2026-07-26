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
  BarChart3,
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

const CHART_COLORS = ["hsl(var(--primary))", "hsl(var(--chart-2))", "hsl(var(--chart-3))", "hsl(var(--chart-4))", "hsl(var(--chart-5))"]

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
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-80 rounded-xl" />
          ))}
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted/50">
          <BarChart3 className="h-8 w-8 text-muted-foreground/60" />
        </div>
        <p className="mt-4 text-base font-semibold">No analytics data yet</p>
        <p className="mt-1 text-sm text-muted-foreground">Start collecting leads to see analytics</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Analytics</h2>
          <p className="text-base text-muted-foreground">Insights and metrics for your lead generation</p>
        </div>
        <div className="flex items-center gap-2 mt-2 sm:mt-0">
          <Button variant="outline" size="icon" onClick={fetchAnalytics} className="h-9 w-9">
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="sm" className="h-9 text-xs gap-1.5">
            <Download className="h-3.5 w-3.5" />
            Export
          </Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-3 sm:gap-4 grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Total Leads", value: data.total_leads, desc: "All collected leads", icon: Users, color: "bg-primary/10", iconColor: "text-primary" },
          { label: "Avg. Rating", value: data.avg_rating != null ? data.avg_rating.toFixed(1) : "—", desc: "Average Google rating", icon: Star, color: "bg-amber-500/10", iconColor: "text-amber-500" },
          { label: "Total Jobs", value: data.total_scraping_jobs, desc: "Scraping jobs created", icon: Bot, color: "bg-blue-500/10", iconColor: "text-blue-500" },
          { label: "Active Jobs", value: data.active_jobs, desc: "Currently running", icon: TrendingUp, color: "bg-green-500/10", iconColor: "text-green-500" },
        ].map((kpi) => {
          const Icon = kpi.icon
          return (
            <Card key={kpi.label} className="border shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2 pt-4 px-4">
                <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  {kpi.label}
                </CardTitle>
                <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${kpi.color}`}>
                  <Icon className={`h-3.5 w-3.5 ${kpi.iconColor}`} />
                </div>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                <p className="text-2xl font-bold">{kpi.value}</p>
                <p className="text-xs text-muted-foreground mt-0.5">{kpi.desc}</p>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Charts */}
      <div className="grid gap-3 sm:gap-4 md:grid-cols-2">
        {/* Leads by Priority */}
        <Card className="border shadow-sm">
          <CardHeader className="border-b bg-muted/20 py-3.5 px-4">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10">
                <BarChart3 className="h-3.5 w-3.5 text-primary" />
              </div>
              Leads by Priority
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            {data.leads_by_priority.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">No data available</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={data.leads_by_priority}
                    dataKey="count"
                    nameKey="priority"
                    cx="50%" cy="50%"
                    outerRadius={100}
                    label={(entry: any) => `${entry.priority} (${entry.count})`}
                  >
                    {data.leads_by_priority.map((entry, idx) => (
                      <Cell key={entry.priority} fill={COLORS[entry.priority as keyof typeof COLORS] || CHART_COLORS[idx % CHART_COLORS.length]} />
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
        <Card className="border shadow-sm">
          <CardHeader className="border-b bg-muted/20 py-3.5 px-4">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10">
                <BarChart3 className="h-3.5 w-3.5 text-primary" />
              </div>
              Leads by City
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            {data.leads_by_city.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">No data available</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data.leads_by_city}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted/50" />
                  <XAxis dataKey="city" className="text-xs" tick={{ fontSize: 11 }} />
                  <YAxis className="text-xs" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Leads by Call Status */}
        <Card className="border shadow-sm">
          <CardHeader className="border-b bg-muted/20 py-3.5 px-4">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10">
                <BarChart3 className="h-3.5 w-3.5 text-primary" />
              </div>
              Leads by Call Status
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            {data.leads_by_call_status.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">No data available</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={data.leads_by_call_status}
                    dataKey="count"
                    nameKey="call_status"
                    cx="50%" cy="50%"
                    outerRadius={100}
                    label={(entry: any) => `${entry.call_status} (${entry.count})`}
                  >
                    {data.leads_by_call_status.map((entry, idx) => (
                      <Cell key={entry.call_status} fill={COLORS[entry.call_status as keyof typeof COLORS] || CHART_COLORS[idx % CHART_COLORS.length]} />
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
        <Card className="border shadow-sm">
          <CardHeader className="border-b bg-muted/20 py-3.5 px-4">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10">
                <BarChart3 className="h-3.5 w-3.5 text-primary" />
              </div>
              Leads by Business Type
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4">
            {data.leads_by_business_type.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">No data available</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={data.leads_by_business_type}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted/50" />
                  <XAxis dataKey="business_type" className="text-xs" tick={{ fontSize: 11 }} />
                  <YAxis className="text-xs" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}