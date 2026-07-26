"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useAuth } from "@/lib/auth-context"
import {
  LayoutDashboard,
  Users,
  BarChart3,
  Settings,
  Bot,
  Store,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  LogOut,
} from "lucide-react"
import { useState } from "react"

const sidebarLinks = [
  {
    group: "Main",
    items: [
      {
        title: "Dashboard",
        href: "/",
        icon: LayoutDashboard,
      },
    ],
  },
  {
    group: "Management",
    items: [
      {
        title: "Leads",
        href: "/leads",
        icon: Users,
      },
      {
        title: "Analytics",
        href: "/analytics",
        icon: BarChart3,
      },
    ],
  },
  {
    group: "Automation",
    items: [
      {
        title: "Scraping Jobs",
        href: "/scraping",
        icon: Bot,
      },
    ],
  },
  {
    group: "System",
    items: [
      {
        title: "Settings",
        href: "/settings",
        icon: Settings,
      },
    ],
  },
]

export function Sidebar() {
  const pathname = usePathname()
  const { logout, user } = useAuth()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={cn(
        "flex flex-col border-r bg-card transition-all duration-300 ease-in-out",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b px-4">
        <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-primary to-primary/60 shadow-sm shadow-primary/20">
          <Store className="h-5 w-5 text-primary-foreground" />
        </div>
        {!collapsed && (
          <div className="flex items-center gap-1.5">
            <span className="text-lg font-bold tracking-tight bg-linear-to-r from-foreground to-foreground/70 bg-clip-text">
              LeadFlow
            </span>
            <Sparkles className="h-3.5 w-3.5 text-primary/60" />
          </div>
        )}
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 px-3 py-5">
        <nav className="flex flex-col gap-7">
          {sidebarLinks.map((group) => (
            <div key={group.group}>
              {!collapsed && (
                <p className="mb-2.5 px-3 text-xs font-semibold text-muted-foreground uppercase tracking-[0.12em]">
                  {group.group}
                </p>
              )}
              <ul className="flex flex-col gap-1">
                {group.items.map((item) => {
                  const isActive =
                    item.href === "/"
                      ? pathname === "/"
                      : pathname.startsWith(item.href)
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        className={cn(
                          "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                          isActive
                            ? "bg-linear-to-r from-primary/10 to-primary/5 text-primary shadow-sm"
                            : "text-muted-foreground hover:bg-accent/60 hover:text-accent-foreground"
                        )}
                      >
                        {isActive && (
                          <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-full bg-primary" />
                        )}
                        <item.icon
                          className={cn(
                            "h-4.5 w-4.5 shrink-0 transition-transform duration-200",
                            isActive ? "text-primary" : "group-hover:scale-105"
                          )}
                        />
                        {!collapsed && <span>{item.title}</span>}
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </nav>
      </ScrollArea>

      {/* Bottom - User & Logout */}
      <div className="border-t p-3">
        {!collapsed && user && (
          <div className="mb-2 px-2">
            <p className="text-sm font-semibold truncate">{user.name}</p>
            <p className="text-xs text-muted-foreground truncate">{user.email}</p>
          </div>
        )}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "flex-1 justify-start gap-3 rounded-xl text-muted-foreground hover:text-destructive hover:bg-destructive/5 transition-all",
              collapsed && "justify-center px-0"
            )}
            onClick={logout}
          >
            <LogOut className="h-4 w-4 shrink-0" />
            {!collapsed && <span>Logout</span>}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 shrink-0 rounded-xl text-muted-foreground hover:text-foreground"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </aside>
  )
}