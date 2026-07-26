"use client"

import { ThemeToggle } from "@/components/layout/theme-toggle"
import { Bell } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

export function Header() {
  return (
    <header className="flex h-16 items-center justify-between border-b bg-card px-6">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">
          Mart Lead Generator
        </h1>
        <p className="text-sm text-muted-foreground">
          AI-powered lead management dashboard
        </p>
      </div>
      <div className="flex items-center gap-3">
        <ThemeToggle />
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          <span className="absolute right-1.5 top-1.5 flex h-2 w-2 rounded-full bg-destructive" />
        </Button>
        <Avatar className="h-8 w-8">
          <AvatarFallback className="text-xs font-medium bg-primary/10 text-primary">
            MG
          </AvatarFallback>
        </Avatar>
      </div>
    </header>
  )
}
