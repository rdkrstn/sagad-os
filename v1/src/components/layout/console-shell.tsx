"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Bell,
  Bot,
  BrainCircuit,
  BookOpen,
  ClipboardCheck,
  Gauge,
  Inbox,
  LayoutDashboard,
  LogOut,
  Menu,
  PlugZap,
  Route,
  Search,
  Settings,
  ShieldCheck,
  UserCog,
} from "lucide-react";
import type { ReactNode } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
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
      { href: "/queue", label: "Exceptions", icon: Inbox },
      { href: "/conversations", label: "Live Work", icon: ClipboardCheck },
      { href: "/reports", label: "Reports", icon: BarChart3 },
    ],
  },
  {
    label: "Orchestration",
    items: [
      { href: "/agents", label: "AI Pods", icon: Bot },
      { href: "/drivers", label: "Drivers", icon: Route },
    ],
  },
  {
    label: "Context Engineering",
    items: [
      { href: "/qa", label: "QA", icon: ShieldCheck },
      { href: "/knowledge", label: "Knowledge", icon: BrainCircuit },
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
    <nav
      className={cn(
        "flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto",
        compact ? "px-2 py-3" : "px-3 py-4",
      )}
    >
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
                      ? "bg-[#008F7A] text-white shadow-xs"
                      : "text-[#6F746F] hover:bg-[#F8F6F1] hover:text-[#08111F]",
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
                        active
                          ? "border-white/20 bg-white/15 text-white"
                          : "border-[#D8D3C8]",
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
    <div className="flex h-screen overflow-hidden bg-[#F4F0E8] text-[#08111F]">
      <aside className="hidden h-screen w-64 shrink-0 border-r border-[#D8D3C8] bg-white lg:flex lg:flex-col">
        <div className="shrink-0 border-b border-[#D8D3C8] px-4 py-4">
          <div className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-lg bg-[#08111F] text-white">
              <Gauge aria-hidden="true" size={18} />
            </span>
            <div className="min-w-0">
              <div className="text-sm font-semibold tracking-tight">Sagad OS</div>
              <div className="text-xs text-muted-foreground">Open-source AI Ops</div>
            </div>
          </div>
        </div>
        <SidebarNav pathname={pathname} />
        <div className="shrink-0 border-t border-[#D8D3C8] p-3">
          <Link
            className="group block rounded-lg border border-[#D8D3C8] bg-[#F8F6F1] p-3 transition-colors hover:border-[#008F7A]/50 hover:bg-white"
            href="/settings"
          >
            <div className="flex items-center justify-between gap-2 text-xs font-medium text-[#08111F]">
              <span className="flex min-w-0 items-center gap-2">
                <Activity className="shrink-0 text-[#008F7A]" size={14} />
                <span className="truncate">Northstar Workspace</span>
              </span>
              <Settings
                aria-hidden="true"
                className="shrink-0 text-[#6F746F] transition-colors group-hover:text-[#008F7A]"
                size={14}
              />
            </div>
            <div className="mt-2 text-[11px] leading-4 text-[#6F746F]">
              Agent Studio status and workspace settings
            </div>
            <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-[#6F746F]">
              <span>Connected</span>
              <Badge className="h-5 border-[#D8D3C8] text-[10px]" variant="outline">
                Self-host
              </Badge>
            </div>
          </Link>
        </div>
      </aside>

      <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <header className="z-30 shrink-0 border-b border-[#D8D3C8] bg-white/95 backdrop-blur">
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
                  className="h-8 border-[#D8D3C8] bg-[#F8F6F1] pl-8"
                  placeholder="Search conversations, drivers, integrations"
                  readOnly
                />
              </div>
              <Badge className="h-7 gap-1.5 border-[#D8D3C8]" variant="outline">
                <span className="size-1.5 rounded-full bg-[#008F7A]" />
                Self-host preview
              </Badge>
              <Badge className="h-7 gap-1.5 border-[#D8D3C8]" variant="outline">
                <span className="size-1.5 rounded-full bg-emerald-500" />
                Console ready
              </Badge>
              <ConsoleRealtimeStatus />
              <Badge className="h-7 gap-1.5 border-[#D8D3C8]" variant="outline">
                <span className="size-1.5 rounded-full bg-amber-500" />
                Twenty external
              </Badge>
            </div>

            <div className="ml-auto flex items-center gap-2">
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
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button className="size-8 rounded-full p-0" variant="ghost">
                    <Avatar className="size-8">
                      <AvatarFallback className="bg-[#08111F] text-xs text-white">
                        JD
                      </AvatarFallback>
                    </Avatar>
                    <span className="sr-only">Open user menu</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel>
                    <div className="text-xs font-medium text-foreground">Johnred Workspace</div>
                    <div className="mt-0.5 text-[11px] text-muted-foreground">Owner preview</div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link href="/settings">
                      <UserCog aria-hidden="true" size={14} />
                      Profile settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href="/superadmin">
                      <ShieldCheck aria-hidden="true" size={14} />
                      SuperAdmin Console
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuItem asChild>
                    <Link href="/settings">
                      <BookOpen aria-hidden="true" size={14} />
                      Read documentation
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link href="/api/auth/signout">
                      <LogOut aria-hidden="true" size={14} />
                      Log out
                    </Link>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </header>
        <main className="min-w-0 flex-1 overflow-y-auto p-4 lg:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
