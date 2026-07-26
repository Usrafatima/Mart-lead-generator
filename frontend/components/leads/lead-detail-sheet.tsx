"use client"

import { Badge } from "@/components/ui/badge"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Separator } from "@/components/ui/separator"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { formatDate, getLeadPriorityColor, getCallStatusColor } from "@/lib/utils"
import type { Lead } from "@/types"
import {
  Building2,
  Globe,
  Mail,
  Phone,
  MapPin,
  Star,
  User,
  ExternalLink,
  Loader2,
} from "lucide-react"
import { useState, useEffect } from "react"
import { toast } from "sonner"

interface LeadDetailSheetProps {
  lead: Lead | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpdate?: (id: string, data: Partial<Lead>) => Promise<void>
}

export function LeadDetailSheet({ lead, open, onOpenChange, onUpdate }: LeadDetailSheetProps) {
  const [isEditing, setIsEditing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [formData, setFormData] = useState<Partial<Lead>>({})

  useEffect(() => {
    if (lead) {
      setFormData({
        call_status: lead.call_status,
        lead_priority: lead.lead_priority,
        notes: lead.notes,
        follow_up_date: lead.follow_up_date,
      })
    }
  }, [lead])

  if (!lead) return null

  async function handleSave() {
    if (!onUpdate || !lead) return
    setIsSaving(true)
    try {
      await onUpdate(lead.id, formData)
      toast.success("Lead updated successfully")
      setIsEditing(false)
    } catch {
      toast.error("Failed to update lead")
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2 text-xl">
            <Building2 className="h-5 w-5 text-muted-foreground" />
            {lead.business_name}
          </SheetTitle>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Priority & Status */}
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className={getLeadPriorityColor(lead.lead_priority)}>
              {lead.lead_priority}
            </Badge>
            <Badge variant="outline" className={getCallStatusColor(lead.call_status)}>
              {lead.call_status}
            </Badge>
            {lead.business_type && (
              <Badge variant="secondary">{lead.business_type}</Badge>
            )}
          </div>

          {/* Contact Info */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-muted-foreground">Contact Information</h4>
            <div className="grid gap-3">
              {lead.phone && (
                <div className="flex items-center gap-3 text-sm">
                  <Phone className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span>{lead.phone}</span>
                </div>
              )}
              {lead.email && (
                <div className="flex items-center gap-3 text-sm">
                  <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
                  <a href={`mailto:${lead.email}`} className="hover:underline text-primary">
                    {lead.email}
                  </a>
                </div>
              )}
              {lead.website && (
                <div className="flex items-center gap-3 text-sm">
                  <Globe className="h-4 w-4 text-muted-foreground shrink-0" />
                  <a
                    href={lead.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 hover:underline text-primary"
                  >
                    {lead.website}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              )}
              {lead.owner_manager && (
                <div className="flex items-center gap-3 text-sm">
                  <User className="h-4 w-4 text-muted-foreground shrink-0" />
                  <span>{lead.owner_manager}</span>
                </div>
              )}
            </div>
          </div>

          <Separator />

          {/* Location */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-muted-foreground">Location</h4>
            <div className="flex items-center gap-3 text-sm">
              <MapPin className="h-4 w-4 text-muted-foreground shrink-0" />
              <span>
                {[lead.address, lead.city, lead.country].filter(Boolean).join(", ") || "—"}
              </span>
            </div>
          </div>

          <Separator />

          {/* Rating */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-muted-foreground">Rating & Reviews</h4>
            <div className="flex items-center gap-4 text-sm">
              <div className="flex items-center gap-1">
                <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                <span className="font-medium">{lead.google_rating ?? "—"}</span>
              </div>
              <span className="text-muted-foreground">
                {lead.reviews_count != null ? `${lead.reviews_count} reviews` : "No reviews"}
              </span>
            </div>
          </div>

          <Separator />

          {/* Classification */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-muted-foreground">AI Classification</h4>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-muted-foreground">Order Method:</span>{" "}
                <span className="font-medium capitalize">{lead.order_method || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Delivery:</span>{" "}
                <span className="font-medium capitalize">{lead.delivery_system || "—"}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Automation:</span>{" "}
                <span className="font-medium capitalize">{lead.automation_status || "—"}</span>
              </div>
            </div>
          </div>

          <Separator />

          {/* Editable fields */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-muted-foreground">Management</h4>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  if (isEditing) handleSave()
                  else setIsEditing(true)
                }}
                disabled={isSaving}
              >
                {isSaving && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                {isEditing ? "Save" : "Edit"}
              </Button>
            </div>

            <div className="space-y-3">
              <div className="space-y-1">
                <Label className="text-xs">Call Status</Label>
                {isEditing ? (
                  <Select
                    value={formData.call_status}
                    onValueChange={(v) => setFormData((prev) => ({ ...prev, call_status: v as Lead["call_status"] }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pending">Pending</SelectItem>
                      <SelectItem value="contacted">Contacted</SelectItem>
                      <SelectItem value="qualified">Qualified</SelectItem>
                      <SelectItem value="converted">Converted</SelectItem>
                      <SelectItem value="lost">Lost</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="text-sm capitalize">{lead.call_status}</p>
                )}
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Lead Priority</Label>
                {isEditing ? (
                  <Select
                    value={formData.lead_priority}
                    onValueChange={(v) => setFormData((prev) => ({ ...prev, lead_priority: v }))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="high">High</SelectItem>
                      <SelectItem value="medium">Medium</SelectItem>
                      <SelectItem value="low">Low</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="text-sm capitalize">{lead.lead_priority}</p>
                )}
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Follow-up Date</Label>
                {isEditing ? (
                  <Input
                    type="date"
                    value={formData.follow_up_date?.split("T")[0] || ""}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, follow_up_date: e.target.value || null }))
                    }
                  />
                ) : (
                  <p className="text-sm">{formatDate(lead.follow_up_date)}</p>
                )}
              </div>

              <div className="space-y-1">
                <Label className="text-xs">Notes</Label>
                {isEditing ? (
                  <textarea
                    className="w-full min-h-[80px] rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    value={formData.notes || ""}
                    onChange={(e) => setFormData((prev) => ({ ...prev, notes: e.target.value }))}
                  />
                ) : (
                  <p className="text-sm whitespace-pre-wrap">{lead.notes || "—"}</p>
                )}
              </div>
            </div>
          </div>

          {/* Social Media */}
          {lead.social_media_links && (
            <>
              <Separator />
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-muted-foreground">Social Media</h4>
                <p className="text-sm break-all">{lead.social_media_links}</p>
              </div>
            </>
          )}

          {/* Timestamps */}
          <Separator />
          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <div>
              Created: {formatDate(lead.created_at)}
            </div>
            <div>
              Updated: {formatDate(lead.updated_at)}
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
