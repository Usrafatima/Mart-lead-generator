"use client"

import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Search, X, SlidersHorizontal } from "lucide-react"

interface LeadFiltersProps {
  search: string
  onSearchChange: (value: string) => void
  priority: string
  onPriorityChange: (value: string) => void
  callStatus: string
  onCallStatusChange: (value: string) => void
  city: string
  onCityChange: (value: string) => void
  hasFilters: boolean
  onClearFilters: () => void
}

export function LeadsFilters({
  search,
  onSearchChange,
  priority,
  onPriorityChange,
  callStatus,
  onCallStatusChange,
  city,
  onCityChange,
  hasFilters,
  onClearFilters,
}: LeadFiltersProps) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-1 items-center gap-2">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by name, email, phone..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="h-9 pl-9 text-sm rounded-lg border-muted/70 focus-visible:border-primary/30"
          />
          {search && (
            <button
              onClick={() => onSearchChange("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground mr-1">
          <SlidersHorizontal className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Filter</span>
        </div>
        <Select value={priority} onValueChange={(v) => onPriorityChange(v ?? "all")}>
          <SelectTrigger className="h-9 w-30 text-xs rounded-lg border-muted/70">
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="text-xs">All Priorities</SelectItem>
            <SelectItem value="high" className="text-xs">High</SelectItem>
            <SelectItem value="medium" className="text-xs">Medium</SelectItem>
            <SelectItem value="low" className="text-xs">Low</SelectItem>
          </SelectContent>
        </Select>

        <Select value={callStatus} onValueChange={(v) => onCallStatusChange(v ?? "all")}>
          <SelectTrigger className="h-9 w-30 text-xs rounded-lg border-muted/70">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="text-xs">All Status</SelectItem>
            <SelectItem value="pending" className="text-xs">Pending</SelectItem>
            <SelectItem value="contacted" className="text-xs">Contacted</SelectItem>
            <SelectItem value="qualified" className="text-xs">Qualified</SelectItem>
            <SelectItem value="converted" className="text-xs">Converted</SelectItem>
            <SelectItem value="lost" className="text-xs">Lost</SelectItem>
          </SelectContent>
        </Select>

        <Select value={city} onValueChange={(v) => onCityChange(v ?? "all")}>
          <SelectTrigger className="h-9 w-30 text-xs rounded-lg border-muted/70">
            <SelectValue placeholder="City" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all" className="text-xs">All Cities</SelectItem>
          </SelectContent>
        </Select>

        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={onClearFilters} className="h-9 text-xs gap-1 text-muted-foreground">
            <X className="h-3.5 w-3.5" />
            Clear
          </Button>
        )}
      </div>
    </div>
  )
}