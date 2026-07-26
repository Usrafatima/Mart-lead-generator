"use client"

import { useState, useEffect, useCallback } from "react"
import { leadsApi } from "@/lib/api-client"
import { LeadsTable } from "@/components/leads/leads-table"
import { LeadsFilters } from "@/components/leads/leads-filters"
import { CreateLeadDialog } from "@/components/leads/create-lead-dialog"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Users, RefreshCw, ListFilter } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { Lead } from "@/types"
import { toast } from "sonner"

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [priorityFilter, setPriorityFilter] = useState("all")
  const [callStatusFilter, setCallStatusFilter] = useState("all")
  const [cityFilter, setCityFilter] = useState("all")

  const fetchLeads = useCallback(async () => {
    try {
      const params: Record<string, string | number> = {}
      if (search) params.search = search
      if (priorityFilter !== "all") params.lead_priority = priorityFilter
      if (callStatusFilter !== "all") params.call_status = callStatusFilter

      const response = await leadsApi.list(params)
      setLeads(response.data.data || response.data)
    } catch {
      toast.error("Failed to fetch leads")
    } finally {
      setIsLoading(false)
    }
  }, [search, priorityFilter, callStatusFilter])

  useEffect(() => {
    fetchLeads()
  }, [fetchLeads])

  const hasFilters = !!search || priorityFilter !== "all" || callStatusFilter !== "all" || cityFilter !== "all"

  function clearFilters() {
    setSearch("")
    setPriorityFilter("all")
    setCallStatusFilter("all")
    setCityFilter("all")
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Leads</h2>
          <p className="text-sm text-muted-foreground">Manage and view all collected business leads</p>
        </div>
        <div className="flex items-center gap-2 mt-2 sm:mt-0">
          <Button variant="outline" size="icon" onClick={fetchLeads} disabled={isLoading} className="h-9 w-9">
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
          </Button>
          <CreateLeadDialog onSuccess={fetchLeads} />
        </div>
      </div>

      {/* Content Card */}
      <Card className="border shadow-sm overflow-hidden">
        <CardHeader className="border-b bg-muted/20 pb-3">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
              <Users className="h-4 w-4 text-primary" />
            </div>
            All Leads
            {!isLoading && (
              <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-primary/5 px-3 py-1 text-xs font-medium text-primary">
                <ListFilter className="h-3 w-3" />
                {leads.length} lead{leads.length !== 1 ? "s" : ""}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-6">
          <div className="space-y-4">
            <LeadsFilters
              search={search}
              onSearchChange={setSearch}
              priority={priorityFilter}
              onPriorityChange={setPriorityFilter}
              callStatus={callStatusFilter}
              onCallStatusChange={setCallStatusFilter}
              city={cityFilter}
              onCityChange={setCityFilter}
              hasFilters={hasFilters}
              onClearFilters={clearFilters}
            />
            <LeadsTable
              data={leads}
              isLoading={isLoading}
              onRefresh={fetchLeads}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}