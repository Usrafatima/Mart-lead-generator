"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Separator } from "@/components/ui/separator"
import { ThemeToggle } from "@/components/layout/theme-toggle"
import { Palette, Store, Server, Globe } from "lucide-react"

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Settings</h2>
        <p className="text-sm text-muted-foreground">
          Application configuration and preferences
        </p>
      </div>

      {/* API Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg font-medium">
            <Server className="h-5 w-5 text-muted-foreground" />
            API Configuration
          </CardTitle>
          <CardDescription>Backend connection settings</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="font-medium">API Base URL</p>
              <p className="text-muted-foreground">Backend server endpoint</p>
            </div>
            <code className="rounded bg-muted px-2 py-1 text-xs font-mono">
              http://localhost:8000/api/v1
            </code>
          </div>
          <p className="text-xs text-muted-foreground">
            Configure via <code className="rounded bg-muted px-1">NEXT_PUBLIC_API_URL</code> in <code className="rounded bg-muted px-1">.env.local</code>
          </p>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg font-medium">
            <Palette className="h-5 w-5 text-muted-foreground" />
            Appearance
          </CardTitle>
          <CardDescription>Customize the look and feel</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">Theme</p>
              <p className="text-sm text-muted-foreground">Toggle between light and dark mode</p>
            </div>
            <ThemeToggle />
          </div>
        </CardContent>
      </Card>

      {/* About */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg font-medium">
            <Store className="h-5 w-5 text-muted-foreground" />
            About
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>Mart Lead Generator v1.0.0</p>
          <p>AI-powered lead generation system for retail businesses.</p>
          <Separator />
          <div className="flex items-center gap-2 text-xs">
            <Globe className="h-3 w-3" />
            Built with Next.js 16, React 19, Tailwind CSS, and shadcn/ui
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
