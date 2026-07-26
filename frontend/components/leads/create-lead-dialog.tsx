"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Plus, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { leadsApi } from "@/lib/api-client"

interface CreateLeadDialogProps {
  onSuccess: () => void
}

export function CreateLeadDialog({ onSuccess }: CreateLeadDialogProps) {
  const [open, setOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [form, setForm] = useState({
    business_name: "",
    business_type: "",
    country: "",
    city: "",
    address: "",
    phone: "",
    email: "",
    website: "",
    owner_manager: "",
    notes: "",
  })

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.business_name) {
      toast.error("Business name is required")
      return
    }

    setIsSubmitting(true)
    try {
      await leadsApi.create(form)
      toast.success("Lead created successfully")
      setOpen(false)
      setForm({
        business_name: "",
        business_type: "",
        country: "",
        city: "",
        address: "",
        phone: "",
        email: "",
        website: "",
        owner_manager: "",
        notes: "",
      })
      onSuccess()
    } catch {
      toast.error("Failed to create lead")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button><Plus className="mr-1 h-4 w-4" />Add Lead</Button>} />
      <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add New Lead</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="business_name">Business Name *</Label>
              <Input
                id="business_name"
                value={form.business_name}
                onChange={(e) => setForm((p) => ({ ...p, business_name: e.target.value }))}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="business_type">Business Type</Label>
              <Input
                id="business_type"
                value={form.business_type}
                onChange={(e) => setForm((p) => ({ ...p, business_type: e.target.value }))}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="website">Website</Label>
            <Input
              id="website"
              type="url"
              placeholder="https://"
              value={form.website}
              onChange={(e) => setForm((p) => ({ ...p, website: e.target.value }))}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                value={form.phone}
                onChange={(e) => setForm((p) => ({ ...p, phone: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="country">Country</Label>
              <Input
                id="country"
                value={form.country}
                onChange={(e) => setForm((p) => ({ ...p, country: e.target.value }))}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="city">City</Label>
              <Input
                id="city"
                value={form.city}
                onChange={(e) => setForm((p) => ({ ...p, city: e.target.value }))}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="address">Address</Label>
            <Input
              id="address"
              value={form.address}
              onChange={(e) => setForm((p) => ({ ...p, address: e.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="owner_manager">Owner / Manager</Label>
            <Input
              id="owner_manager"
              value={form.owner_manager}
              onChange={(e) => setForm((p) => ({ ...p, owner_manager: e.target.value }))}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <Textarea
              id="notes"
              rows={3}
              value={form.notes}
              onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))}
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              Create Lead
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
