"use client"

import { useState, useMemo } from "react"
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type ColumnFiltersState,
  type VisibilityState,
} from "@tanstack/react-table"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Checkbox } from "@/components/ui/checkbox"
import { Skeleton } from "@/components/ui/skeleton"
import {
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Trash2,
  Columns3,
  Loader2,
  SearchX,
} from "lucide-react"
import { toast } from "sonner"
import type { Lead } from "@/types"
import { getLeadPriorityColor, getCallStatusColor } from "@/lib/utils"
import { leadsApi } from "@/lib/api-client"
import { LeadDetailSheet } from "./lead-detail-sheet"

interface LeadsTableProps {
  data: Lead[]
  isLoading: boolean
  onRefresh: () => void
}

export function LeadsTable({ data, isLoading, onRefresh }: LeadsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>({
    business_type: true,
    country: false,
    address: false,
    owner_manager: false,
    social_media_links: false,
    order_method: false,
    delivery_system: false,
    automation_status: false,
    reviews_count: false,
    notes: false,
    follow_up_date: false,
    created_at: false,
    updated_at: false,
  })
  const [rowSelection, setRowSelection] = useState({})
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [isExporting, setIsExporting] = useState(false)

  const columns: ColumnDef<Lead>[] = useMemo(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <Checkbox
            checked={table.getIsAllPageRowsSelected()}
            data-indeterminate={table.getIsSomePageRowsSelected() || undefined}
            onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
            aria-label="Select all"
          />
        ),
        cell: ({ row }) => (
          <Checkbox
            checked={row.getIsSelected()}
            onCheckedChange={(value) => row.toggleSelected(!!value)}
            aria-label="Select row"
          />
        ),
        enableSorting: false,
        enableHiding: false,
        size: 40,
      },
      {
        accessorKey: "business_name",
        header: ({ column }) => (
          <SortableHeader column={column} title="Business Name" />
        ),
        cell: ({ row }) => (
          <span className="font-semibold text-sm">{row.getValue("business_name") || "—"}</span>
        ),
      },
      {
        accessorKey: "business_type",
        header: ({ column }) => (
          <SortableHeader column={column} title="Type" />
        ),
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground">{row.getValue("business_type") || "—"}</span>
        ),
      },
      {
        accessorKey: "city",
        header: ({ column }) => (
          <SortableHeader column={column} title="City" />
        ),
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground">{row.getValue("city") || "—"}</span>
        ),
      },
      {
        accessorKey: "phone",
        header: "Phone",
        cell: ({ row }) => (
          <span className="text-sm font-mono text-muted-foreground">{row.getValue("phone") || "—"}</span>
        ),
      },
      {
        accessorKey: "email",
        header: "Email",
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground truncate max-w-45 block">
            {row.getValue("email") || "—"}
          </span>
        ),
      },
      {
        accessorKey: "website",
        header: "Website",
        cell: ({ row }) => {
          const website = row.getValue("website") as string
          return website ? (
            <a
              href={website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary/80 hover:text-primary hover:underline truncate max-w-37.5 block transition-colors"
            >
              {website}
            </a>
          ) : (
            <span className="text-sm text-muted-foreground/60">—</span>
          )
        },
      },
      {
        accessorKey: "google_rating",
        header: ({ column }) => (
          <SortableHeader column={column} title="Rating" />
        ),
        cell: ({ row }) => {
          const rating = row.getValue("google_rating") as number | null
          return rating != null ? (
            <span className="text-sm font-semibold text-amber-600 dark:text-amber-400">{rating.toFixed(1)}</span>
          ) : (
            <span className="text-sm text-muted-foreground/60">—</span>
          )
        },
      },
      {
        accessorKey: "lead_priority",
        header: ({ column }) => (
          <SortableHeader column={column} title="Priority" />
        ),
        cell: ({ row }) => {
          const priority = row.getValue("lead_priority") as string
          return (
            <Badge variant="outline" className={`text-[11px] font-semibold px-2 py-0 ${getLeadPriorityColor(priority)}`}>
              {priority}
            </Badge>
          )
        },
      },
      {
        accessorKey: "call_status",
        header: ({ column }) => (
          <SortableHeader column={column} title="Call Status" />
        ),
        cell: ({ row }) => {
          const status = row.getValue("call_status") as string
          return (
            <Badge variant="outline" className={`text-[11px] font-semibold px-2 py-0 ${getCallStatusColor(status)}`}>
              {status}
            </Badge>
          )
        },
      },
    ],
    []
  )

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      rowSelection,
    },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: { pageSize: 25 },
    },
  })

  async function handleExport() {
    setIsExporting(true)
    try {
      const response = await leadsApi.exportCsv()
      const blob = new Blob([response.data], { type: "text/csv" })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `leads-export-${new Date().toISOString().split("T")[0]}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
      toast.success("Leads exported successfully")
    } catch {
      toast.error("Failed to export leads")
    } finally {
      setIsExporting(false)
    }
  }

  async function handleBulkDelete() {
    const selectedIds = Object.keys(rowSelection).map(
      (idx) => data[parseInt(idx)]?.id
    ).filter(Boolean) as string[]

    if (!selectedIds.length) return

    try {
      await leadsApi.bulkDelete(selectedIds)
      toast.success(`${selectedIds.length} lead(s) deleted`)
      setRowSelection({})
      onRefresh()
    } catch {
      toast.error("Failed to delete leads")
    }
  }

  async function handleUpdateLead(id: string, updates: Partial<Lead>) {
    await leadsApi.update(id, updates)
    onRefresh()
  }

  const selectedCount = Object.keys(rowSelection).length

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="flex gap-2">
          <Skeleton className="h-9 w-24 rounded-lg" />
          <Skeleton className="h-9 w-24 rounded-lg" />
        </div>
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {selectedCount > 0 && (
            <>
              <span className="text-sm font-medium text-muted-foreground">
                {selectedCount} selected
              </span>
              <Button variant="destructive" size="sm" onClick={handleBulkDelete} className="h-8 text-xs">
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                Delete
              </Button>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleExport} disabled={isExporting} className="h-8 text-xs gap-1.5">
            {isExporting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5" />
            )}
            Export CSV
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="outline" size="sm" className="h-8 text-xs gap-1.5"><Columns3 className="h-3.5 w-3.5" />Columns</Button>} />
            <DropdownMenuContent align="end" className="w-44">
              {table.getAllColumns().filter((c) => c.getCanHide()).map((column) => (
                <DropdownMenuCheckboxItem
                  key={column.id}
                  checked={column.getIsVisible()}
                  onCheckedChange={(value) => column.toggleVisibility(!!value)}
                  className="text-xs"
                >
                  {column.id.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                </DropdownMenuCheckboxItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border bg-card shadow-sm">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="bg-muted/30 hover:bg-muted/30">
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id} className="h-10 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                  className="cursor-pointer transition-colors hover:bg-primary/5 border-b border-border/50 last:border-0"
                  onClick={() => {
                    setSelectedLead(row.original)
                    setDetailOpen(true)
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id} className="py-3">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-60 text-center">
                  <div className="flex flex-col items-center justify-center">
                    <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted/50 mb-3">
                      <SearchX className="h-6 w-6 text-muted-foreground/60" />
                    </div>
                    <p className="text-lg font-semibold text-muted-foreground">No leads found</p>
                    <p className="text-sm text-muted-foreground mt-1 max-w-sm">
                      Start a scraping job to collect leads, or add one manually.
                    </p>
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()}
        </p>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="h-8 w-8"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          {Array.from({ length: Math.min(table.getPageCount(), 5) }, (_, i) => i + 1).map((page) => (
            <Button
              key={page}
              variant={table.getState().pagination.pageIndex + 1 === page ? "default" : "outline"}
              size="icon"
              onClick={() => table.setPageIndex(page - 1)}
              className="h-8 w-8 text-xs"
            >
              {page}
            </Button>
          ))}
          <Button
            variant="outline"
            size="icon"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="h-8 w-8"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Detail Sheet */}
      <LeadDetailSheet
        lead={selectedLead}
        open={detailOpen}
        onOpenChange={setDetailOpen}
        onUpdate={handleUpdateLead}
      />
    </div>
  )
}

function SortableHeader({ column, title }: { column: any; title: string }) {
  const sorted = column.getIsSorted()
  return (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-3 h-7 text-[11px] font-semibold uppercase tracking-wider hover:bg-transparent"
      onClick={() => column.toggleSorting(sorted === "asc")}
    >
      {title}
      {sorted === "asc" ? (
        <ChevronUp className="ml-1 h-3 w-3" />
      ) : sorted === "desc" ? (
        <ChevronDown className="ml-1 h-3 w-3" />
      ) : (
        <ChevronsUpDown className="ml-1 h-3 w-3 opacity-30" />
      )}
    </Button>
  )
}