"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileText,
  Gauge,
  GitBranch,
  Layers3,
  ListChecks,
  LogOut,
  Menu,
  Moon,
  PlugZap,
  Search,
  Settings,
  Sun,
  UserCog,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useMemo, useState } from "react";
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
  SheetClose,
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
import { LogoPlaceholder, StatusPill } from "@/components/product/product-ui";
import { ConsoleRealtimeStatus } from "@/components/realtime/console-realtime-status";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark";

type NavItem = {
  href: string;
  label: string;
  code: string;
  icon: LucideIcon;
};

const navItems: NavItem[] = [
  { href: "/", label: "Overview", code: "OV", icon: Gauge },
  { href: "/conversations", label: "Conversations", code: "CV", icon: ClipboardCheck },
  { href: "/approvals", label: "Approvals", code: "AP", icon: ListChecks },
  { href: "/customers", label: "Customers", code: "CU", icon: Users },
  { href: "/knowledge", label: "Knowledge", code: "KB", icon: BookOpen },
  { href: "/workflows", label: "Workflows", code: "WF", icon: GitBranch },
  { href: "/integrations", label: "Integrations", code: "IN", icon: PlugZap },
  { href: "/analytics", label: "Analytics", code: "AN", icon: BarChart3 },
  { href: "/logs", label: "Logs", code: "LG", icon: FileText },
  { href: "/settings", label: "Settings", code: "ST", icon: Settings },
];

const routeMeta: Array<{ match: string; title: string; description: string }> = [
  {
    match: "/conversations",
    title: "Conversations",
    description: "Supervisor queue, AI drafts, approvals, and routing state.",
  },
  {
    match: "/approvals",
    title: "Approvals",
    description: "Low-confidence replies, escalation gates, and supervisor decisions.",
  },
  {
    match: "/customers",
    title: "Customers",
    description: "CRM context, lead stage, service history, and pending tasks.",
  },
  {
    match: "/knowledge",
    title: "Knowledge",
    description: "Approved sources, review state, retrieval tests, and missing topics.",
  },
  {
    match: "/workflows",
    title: "Workflows",
    description: "Agent routing flows, approval thresholds, and tool checkpoints.",
  },
  {
    match: "/integrations",
    title: "Integrations",
    description: "Operator-facing adapter health and approval-gated connection state.",
  },
  {
    match: "/analytics",
    title: "Analytics",
    description: "Automation, approval, rejection, escalation, and trust-score reporting.",
  },
  {
    match: "/logs",
    title: "Logs",
    description: "Audit events for AI drafts, retrieval, tool calls, approvals, and sends.",
  },
  {
    match: "/settings",
    title: "Settings",
    description: "Runtime policy, approval thresholds, prompts, and developer payloads.",
  },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || (href !== "/" && pathname.startsWith(href));
}

function useConsoleTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") return "dark";
    const stored = window.localStorage.getItem("sagados-theme");
    if (stored === "light" || stored === "dark") {
      return stored;
    }

    return "dark";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.classList.toggle("dark", theme === "dark");
    document.body.dataset.theme = theme;
    document.body.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem("sagados-theme", theme);
  }, [theme]);

  return {
    theme,
    toggleTheme: () => setTheme((current) => (current === "dark" ? "light" : "dark")),
  };
}

function SidebarNav({
  pathname,
  compact = false,
  closeOnNavigate = false,
}: {
  pathname: string;
  compact?: boolean;
  closeOnNavigate?: boolean;
}) {
  return (
    <nav
      aria-label="Product navigation"
      className={cn(
        "grid content-start gap-1 overflow-y-auto",
        compact ? "px-2 py-3" : "px-3 py-4",
      )}
    >
      {navItems.map((item) => {
        const Icon = item.icon;
        const active = isActive(pathname, item.href);
        const content = (
          <Link
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-10 items-center gap-2.5 rounded-md px-3 text-sm font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
              active && "bg-[rgba(0,212,170,0.12)] text-foreground",
              compact && "justify-center px-0",
            )}
            href={item.href}
          >
            <span
              className={cn(
                "grid size-5 shrink-0 place-items-center rounded-sm border border-current font-mono text-[9px] opacity-75",
                active && "text-[var(--accent-text)]",
              )}
            >
              {compact ? <Icon aria-hidden="true" size={13} /> : item.code}
            </span>
            {!compact ? <span className="min-w-0 flex-1 truncate">{item.label}</span> : null}
          </Link>
        );

        const wrappedContent = closeOnNavigate ? (
          <SheetClose asChild>{content}</SheetClose>
        ) : (
          content
        );

        return compact ? (
          <Tooltip key={item.href}>
            <TooltipTrigger asChild>{wrappedContent}</TooltipTrigger>
            <TooltipContent side="right">{item.label}</TooltipContent>
          </Tooltip>
        ) : (
          <div key={item.href}>{wrappedContent}</div>
        );
      })}
    </nav>
  );
}

function SidebarFooter() {
  return (
    <div className="mt-auto border-t border-border p-3">
      <div className="rounded-lg border border-border bg-surface-2 p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              Environment
            </div>
            <div className="mt-1 truncate text-sm font-semibold text-foreground">
              Local / Preview / Production
            </div>
          </div>
          <StatusPill tone="good">Healthy</StatusPill>
        </div>
        <div className="mt-3 grid gap-2 text-xs text-muted-foreground">
          <div className="flex items-center justify-between gap-2">
            <span>System status</span>
            <span className="font-mono text-[var(--accent-text)]">Healthy / Degraded</span>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span>Operator role</span>
            <span>Supervisor</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ConsoleShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { theme, toggleTheme } = useConsoleTheme();
  const meta = useMemo(
    () =>
      routeMeta.find((item) => pathname.startsWith(item.match)) ?? {
        title: "Overview",
        description: "SagadOS operator console for supervised AI customer operations.",
      },
    [pathname],
  );

  return (
    <div
      className={cn(
        "min-h-screen bg-background text-foreground",
        theme === "dark" && "dark",
      )}
      data-theme={theme}
    >
      <div className="grid min-h-screen lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="hidden min-h-screen border-r border-border bg-card lg:flex lg:flex-col">
          <div className="flex min-h-16 items-center gap-3 border-b border-border px-5">
            <LogoPlaceholder />
            <div className="min-w-0">
              <div className="text-[15px] font-bold tracking-tight">SagadOS</div>
              <div className="text-[11px] text-muted-foreground">AI customer ops</div>
            </div>
            <div className="ml-auto flex items-center gap-1.5 font-mono text-[10px] uppercase text-muted-foreground">
              <span className="size-1.5 rounded-full bg-[var(--accent)] shadow-[0_0_0_3px_rgba(0,212,170,0.14)]" />
              local
            </div>
          </div>
          <SidebarNav pathname={pathname} />
          <SidebarFooter />
        </aside>

        <div className="flex min-h-screen min-w-0 flex-col">
          <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur">
            <div className="flex min-h-16 items-center gap-3 px-4 lg:px-6">
              <Sheet>
                <SheetTrigger asChild>
                  <Button className="lg:hidden" size="icon" variant="outline">
                    <Menu aria-hidden="true" />
                    <span className="sr-only">Open navigation</span>
                  </Button>
                </SheetTrigger>
                <SheetContent className="w-72 border-border bg-card p-0" side="left">
                  <SheetHeader className="border-b border-border px-4 py-4 text-left">
                    <SheetTitle className="flex items-center gap-3">
                      <LogoPlaceholder />
                      SagadOS
                    </SheetTitle>
                  </SheetHeader>
                  <SidebarNav closeOnNavigate pathname={pathname} />
                  <SidebarFooter />
                </SheetContent>
              </Sheet>

              <div className="min-w-0 flex-1">
                <h1 className="truncate text-xl font-bold tracking-tight lg:text-2xl">
                  {meta.title}
                </h1>
                <p className="mt-0.5 hidden truncate text-xs text-muted-foreground md:block">
                  {meta.description}
                </p>
              </div>

              <div className="hidden min-w-64 max-w-sm flex-1 xl:block">
                <div className="relative">
                  <Search
                    aria-hidden="true"
                    className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                    size={15}
                  />
                  <Input
                    aria-label="Search console preview"
                    className="h-9 bg-muted pl-8"
                    placeholder="Search conversations, customers, logs"
                    readOnly
                  />
                </div>
              </div>

              <div className="hidden items-center gap-2 lg:flex">
                <Badge className="h-7 gap-1.5 border-border" variant="outline">
                  <Activity aria-hidden="true" size={13} />
                  Preview
                </Badge>
                <Badge className="h-7 gap-1.5 border-border" variant="outline">
                  <Database aria-hidden="true" size={13} />
                  Agent Studio gated
                </Badge>
                <ConsoleRealtimeStatus />
              </div>

              <div className="ml-auto flex items-center gap-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button onClick={toggleTheme} size="icon" type="button" variant="outline">
                      {theme === "dark" ? (
                        <Sun aria-hidden="true" />
                      ) : (
                        <Moon aria-hidden="true" />
                      )}
                      <span className="sr-only">Toggle theme</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {theme === "dark" ? "Light mode" : "Dark mode"}
                  </TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button className="relative" size="icon" variant="ghost">
                      <Bell aria-hidden="true" />
                      <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-danger" />
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
                        <AvatarFallback className="bg-surface-2 text-xs text-foreground">
                          JD
                        </AvatarFallback>
                      </Avatar>
                      <span className="sr-only">Open user menu</span>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56">
                    <DropdownMenuLabel>
                      <div className="text-xs font-semibold text-foreground">
                        Johnred Workspace
                      </div>
                      <div className="mt-0.5 text-[11px] text-muted-foreground">
                        Owner preview
                      </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem asChild>
                      <Link href="/settings">
                        <UserCog aria-hidden="true" size={14} />
                        Profile settings
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/settings">
                        <Layers3 aria-hidden="true" size={14} />
                        Advanced payloads
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/knowledge">
                        <CheckCircle2 aria-hidden="true" size={14} />
                        Knowledge governance
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
    </div>
  );
}
