"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bell,
  Bot,
  BrainCircuit,
  ClipboardCheck,
  Gauge,
  Inbox,
  LayoutDashboard,
  Menu,
  PlugZap,
  Route,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import type { ReactNode } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ConsoleRealtimeStatus } from "@/components/realtime/console-realtime-status";
import { cn } from "@/lib/utils";

const navSections = [
  {
    label: "Operations",
    items: [
      { href: "/", label: "Command", icon: LayoutDashboard, badge: "Live" },
      { href: "/queue", label: "Queue", icon: Inbox },
      { href: "/conversations", label: "Review", icon: ClipboardCheck },
    ],
  },
  {
    label: "Orchestration",
    items: [
      { href: "/agents", label: "Agents & Pods", icon: Bot },
      { href: "/drivers", label: "Contact Drivers", icon: Route },
    ],
  },
  {
    label: "Context Engineering",
    items: [
      { href: "/knowledge", label: "Knowledge", icon: BrainCircuit },
      { href: "/qa", label: "QA/SOP", icon: ShieldCheck },
    ],
  },
  {
    label: "Platform",
    items: [
      { href: "/tools", label: "Integrations", icon: PlugZap },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || (href !== "/" && pathname.startsWith(href));
}

function SidebarNav({
  pathname,
  compact = false,
}: {
  pathname: string;
  compact?: boolean;
}) {
  return (
    <nav className={cn("flex flex-1 flex-col gap-5", compact ? "px-2 py-3" : "px-3 py-4")}>
      {navSections.map((section) => (
        <div key={section.label}>
          {!compact ? (
            <div className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              {section.label}
            </div>
          ) : null}
          <div className="space-y-1">
            {section.items.map((item) => {
              const Icon = item.icon;
              const active = isActive(pathname, item.href);
              const content = (
                <Link
                  className={cn(
                    "flex h-9 items-center gap-2 rounded-md px-3 text-sm font-medium transition-colors",
                    active
                      ? "bg-primary text-primary-foreground shadow-xs"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    compact && "justify-center px-0",
                  )}
                  href={item.href}
                >
                  <Icon aria-hidden="true" size={16} />
                  {!compact ? <span className="min-w-0 flex-1 truncate">{item.label}</span> : null}
                  {!compact && item.badge ? (
                    <Badge
                      className={cn(
                        "h-5 rounded px-1.5 text-[10px]",
                        active ? "bg-primary-foreground/15 text-primary-foreground" : "",
                      )}
                      variant={active ? "secondary" : "outline"}
                    >
                      {item.badge}
                    </Badge>
                  ) : null}
                </Link>
              );

              return compact ? (
                <Tooltip key={item.href}>
                  <TooltipTrigger asChild>{content}</TooltipTrigger>
                  <TooltipContent side="right">{item.label}</TooltipContent>
                </Tooltip>
              ) : (
                <div key={item.href}>{content}</div>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

export function ConsoleShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:flex lg:flex-col">
        <div className="border-b px-4 py-4">
          <div className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Gauge aria-hidden="true" size={18} />
            </span>
            <div className="min-w-0">
              <div className="text-sm font-semibold tracking-tight">Sagad OS</div>
              <div className="text-xs text-muted-foreground">Open-source AI Ops</div>
            </div>
          </div>
        </div>
        <SidebarNav pathname={pathname} />
        <div className="border-t p-3">
          <div className="rounded-lg border bg-muted/30 p-3">
            <div className="flex items-center gap-2 text-xs font-medium">
              <Activity className="text-emerald-600" size={14} />
              Johnred Workspace
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
              <span>Agent Studio</span>
              <Badge className="h-5 text-[10px]" variant="outline">
                Self-host
              </Badge>
            </div>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b bg-card/95 backdrop-blur">
          <div className="flex h-14 items-center gap-3 px-4 lg:px-6">
            <Sheet>
              <SheetTrigger asChild>
                <Button className="lg:hidden" size="icon" variant="outline">
                  <Menu aria-hidden="true" />
                  <span className="sr-only">Open navigation</span>
                </Button>
              </SheetTrigger>
              <SheetContent className="w-72 p-0" side="left">
                <SheetHeader className="border-b px-4 py-4 text-left">
                  <SheetTitle>Sagad OS</SheetTitle>
                </SheetHeader>
                <SidebarNav pathname={pathname} />
              </SheetContent>
            </Sheet>

            <div className="hidden min-w-0 flex-1 items-center gap-3 md:flex">
              <div className="relative w-full max-w-md">
                <Search
                  aria-hidden="true"
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                  size={15}
                />
                <Input
                  aria-label="Search console preview"
                  className="h-8 bg-muted/40 pl-8"
                  placeholder="Search conversations, drivers, integrations"
                  readOnly
                />
              </div>
              <Badge className="h-7 gap-1.5" variant="outline">
                <span className="size-1.5 rounded-full bg-sky-500" />
                Self-host preview
              </Badge>
              <Badge className="h-7 gap-1.5" variant="outline">
                <span className="size-1.5 rounded-full bg-emerald-500" />
                Console ready
              </Badge>
              <ConsoleRealtimeStatus />
              <Badge className="h-7 gap-1.5" variant="outline">
                <span className="size-1.5 rounded-full bg-amber-500" />
                Twenty external
              </Badge>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button size="icon" variant="ghost">
                    <SlidersHorizontal aria-hidden="true" />
                    <span className="sr-only">View controls</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>View controls</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button className="relative" size="icon" variant="ghost">
                    <Bell aria-hidden="true" />
                    <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-rose-500" />
                    <span className="sr-only">Alerts</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Alerts</TooltipContent>
              </Tooltip>
              <Separator className="hidden h-6 md:block" orientation="vertical" />
              <Avatar className="size-8">
                <AvatarFallback className="bg-primary text-xs text-primary-foreground">
                  JD
                </AvatarFallback>
              </Avatar>
            </div>
          </div>
        </header>
        <main className="min-w-0 flex-1 p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
