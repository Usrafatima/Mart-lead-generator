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
import { Search, X } from "lucide-react"
import type { LeadPriority, CallStatus, AutomationStatus } from "@/types"

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
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-1 items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search leads..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Select value={priority} onValueChange={onPriorityChange}>
          <SelectTrigger className="w-[130px]">
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Priorities</SelectItem>
            <SelectItem value="high">High</SelectItem>
            <SelectItem value="medium">Medium</SelectItem>
            <SelectItem value="low">Low</SelectItem>
          </SelectContent>
        </Select>

        <Select value={callStatus} onValueChange={onCallStatusChange}>
          <SelectTrigger className="w-[130px]">
            <SelectValue placeholder="Call Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="contacted">Contacted</SelectItem>
            <SelectItem value="qualified">Qualified</SelectItem>
            <SelectItem value="converted">Converted</SelectItem>
            <SelectItem value="lost">Lost</SelectItem>
          </SelectContent>
        </Select>

        <Select value={city} onValueChange={onCityChange}>
          <SelectTrigger className="w-[130px]">
            <SelectValue placeholder="City" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Cities</SelectItem>
          </SelectContent>
        </Select>

        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={onClearFilters}>
            <X className="mr-1 h-4 w-4" />
            Clear
          </Button>
        )}
      </div>
    </div>
  )
}
