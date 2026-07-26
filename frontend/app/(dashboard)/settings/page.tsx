"use client"

import { useAuth } from "@/lib/auth-context"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { User, Shield, Palette, Store, Server } from "lucide-react"

export default function SettingsPage() {
  const { user } = useAuth()

  const initials = user?.name
    ? user.name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2)
    : "U"

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Settings</h2>
          <p className="text-base text-muted-foreground">Application configuration and preferences</p>
      </div>

      {/* Profile */}
      <Card className="border shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg font-semibold">
            <User className="h-5 w-5 text-muted-foreground" />
            Profile
          </CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Avatar className="h-16 w-16 ring-2 ring-border ring-offset-2 ring-offset-background">
              <AvatarFallback className="text-lg font-bold bg-linear-to-br from-primary/10 to-primary/5 text-primary">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="text-xl font-bold">{user?.name || "User"}</p>
              <p className="text-sm text-muted-foreground">{user?.email || ""}</p>
              <Badge variant="secondary" className="mt-1.5 capitalize text-xs">
                <Shield className="mr-1 h-3 w-3" />
                {user?.role || "user"}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* API Configuration */}
      <Card className="border shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg font-semibold">
            <Server className="h-5 w-5 text-muted-foreground" />
            API Configuration
          </CardTitle>
          <CardDescription>Backend connection settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-center justify-between rounded-lg border bg-muted/20 p-3">
            <div>
              <p className="font-medium">API Base URL</p>
              <p className="text-sm text-muted-foreground">Backend server endpoint</p>
            </div>
            <code className="rounded-md bg-muted px-2.5 py-1 text-xs font-mono text-foreground">
              http://localhost:8000/api/v1
            </code>
          </div>
          <p className="text-xs text-muted-foreground">
            Configure via <code className="rounded bg-muted px-1.5 py-0.5">NEXT_PUBLIC_API_URL</code> in <code className="rounded bg-muted px-1.5 py-0.5">.env.local</code>
          </p>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card className="border shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg font-semibold">
            <Palette className="h-5 w-5 text-muted-foreground" />
            Appearance
          </CardTitle>
          <CardDescription>Customize the look and feel</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-base font-medium">Theme</p>
              <p className="text-sm text-muted-foreground">Toggle between light and dark mode</p>
            </div>
            <ThemeToggle />
          </div>
        </CardContent>
      </Card>

      {/* About */}
      <Card className="border shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg font-semibold">
            <Store className="h-5 w-5 text-muted-foreground" />
            About
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>Mart Lead Generator v1.0.0</p>
          <p>AI-powered lead generation system for retail businesses.</p>
          <Separator />
          <p className="text-xs">
            Built with Next.js 16, React 19, Tailwind CSS, and shadcn/ui
          </p>
        </CardContent>
      </Card>
    </div>
  )
}