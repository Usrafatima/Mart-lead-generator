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
import { Plus, Loader2, Bot, MapPin, Globe, Smartphone } from "lucide-react"
import { toast } from "sonner"
import { jobsApi } from "@/lib/api-client"

interface CreateJobDialogProps {
  onSuccess: () => void
}

const botTypes = [
  { value: "google_maps", label: "Google Maps", icon: MapPin },
  { value: "website_scraper", label: "Website Scraper", icon: Globe },
  { value: "social_scraper", label: "Social Media", icon: Smartphone },
]

export function CreateJobDialog({ onSuccess }: CreateJobDialogProps) {
  const [open, setOpen] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [botType, setBotType] = useState("google_maps")
  const [city, setCity] = useState("")
  const [category, setCategory] = useState("")

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!city || !category) {
      toast.error("City and category are required")
      return
    }

    setIsSubmitting(true)
    try {
      await jobsApi.create({ bot_type: botType, city, category })
      toast.success("Scraping job started!")
      setOpen(false)
      setCity("")
      setCategory("")
      onSuccess()
    } catch {
      toast.error("Failed to create job")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button><Plus className="mr-1 h-4 w-4" />New Scraping Job</Button>} />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Start New Scraping Job</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Bot Type</Label>
            <div className="grid grid-cols-3 gap-2">
              {botTypes.map((type) => {
                const Icon = type.icon
                const isSelected = botType === type.value
                return (
                  <button
                    key={type.value}
                    type="button"
                    className={`flex flex-col items-center gap-2 rounded-lg border p-3 text-sm transition-colors ${
                      isSelected
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border hover:bg-accent"
                    }`}
                    onClick={() => setBotType(type.value)}
                  >
                    <Icon className="h-5 w-5" />
                    {type.label}
                  </button>
                )
              })}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="city">City</Label>
            <Input
              id="city"
              placeholder="e.g. New York"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="category">Category</Label>
            <Input
              id="category"
              placeholder="e.g. Restaurants, Bakeries"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              required
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              Start Job
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
