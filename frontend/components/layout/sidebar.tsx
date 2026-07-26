"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  LayoutDashboard,
  Users,
  BarChart3,
  Settings,
  Bot,
  Store,
  ChevronLeft,
  ChevronRight,
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
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={cn(
        "flex flex-col border-r bg-card transition-all duration-300",
        collapsed ? "w-16" : "w-64"
      )}
    >
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary">
          <Store className="h-4 w-4 text-primary-foreground" />
        </div>
        {!collapsed && (
          <span className="text-base font-semibold tracking-tight">LeadGenerator</span>
        )}
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 px-3 py-4">
        <nav className="flex flex-col gap-6">
          {sidebarLinks.map((group) => (
            <div key={group.group}>
              {!collapsed && (
                <p className="mb-2 px-2 text-xs font-medium text-muted-foreground uppercase tracking-wider">
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
                          "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                          isActive
                            ? "bg-primary/10 text-primary"
                            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                        )}
                      >
                        <item.icon className="h-4 w-4 shrink-0" />
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

      {/* Bottom: collapse toggle */}
      <div className="border-t p-3">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-muted-foreground hover:text-foreground"
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4 shrink-0" />
          ) : (
            <ChevronLeft className="h-4 w-4 shrink-0" />
          )}
          {!collapsed && <span className="ml-2">Collapse</span>}
        </Button>
      </div>
    </aside>
  )
}
