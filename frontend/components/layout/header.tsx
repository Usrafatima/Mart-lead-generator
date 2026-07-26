"use client"

import { ThemeToggle } from "@/components/layout/theme-toggle"
import { useAuth } from "@/lib/auth-context"
import { Bell } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

export function Header() {
  const { user } = useAuth()

  const initials = user?.name
    ? user.name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
    : "U"

  return (
    <header className="flex h-16 items-center justify-between gap-4 border-b bg-card/80 backdrop-blur-sm px-6">
      <div className="hidden sm:block">
        <h1 className="text-xl font-bold tracking-tight">Mart Lead Generator</h1>
        <p className="text-sm text-muted-foreground">AI-powered lead management dashboard</p>
      </div>

      <div className="flex items-center gap-3 ml-auto">
        <ThemeToggle />
        <Button variant="ghost" size="icon" className="relative text-muted-foreground hover:text-foreground">
          <Bell className="h-4.5 w-4.5" />
          <span className="absolute right-2 top-2 flex h-2 w-2 rounded-full bg-destructive shadow-sm shadow-destructive/50" />
        </Button>
        <div className="flex items-center gap-2.5 pl-2 border-l">
          <div className="hidden sm:block text-right">
            <p className="text-sm font-semibold leading-tight">{user?.name || "User"}</p>
            <p className="text-xs text-muted-foreground">{user?.email || ""}</p>
          </div>
          <Avatar className="h-9 w-9 ring-2 ring-border ring-offset-2 ring-offset-background transition-shadow hover:ring-primary/30">
            <AvatarFallback className="text-xs font-bold bg-linear-to-br from-primary/10 to-primary/5 text-primary">
              {initials}
            </AvatarFallback>
          </Avatar>
        </div>
      </div>
    </header>
  )
}