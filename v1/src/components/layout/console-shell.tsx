"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  BrainCircuit,
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
  Network,
  PlugZap,
  Route,
  ServerCog,
  Settings,
  ShieldCheck,
  Sun,
  UserCog,
  Wrench,
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
import { SagadLogo, StatusPill } from "@/components/product/product-ui";
import { ConsoleRealtimeStatus } from "@/components/realtime/console-realtime-status";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark";

type NavItem = {
  href: string;
  label: string;
  code: string;
  icon: LucideIcon;
};

type NavSection = {
  label: string;
  items: NavItem[];
};

const navSections: NavSection[] = [
  {
    label: "Operations",
    items: [
      { href: "/", label: "Command Center", code: "CC", icon: Gauge },
      { href: "/review-queue", label: "Review Queue", code: "RQ", icon: ListChecks },
      { href: "/conversations", label: "Conversations", code: "CV", icon: ClipboardCheck },
      { href: "/drivers", label: "Contact Drivers", code: "DR", icon: Route },
      { href: "/reports", label: "Reports", code: "RP", icon: BarChart3 },
    ],
  },
  {
    label: "Agent Studio",
    items: [
      { href: "/agents", label: "Agents", code: "AG", icon: Bot },
      { href: "/skills", label: "Skills", code: "SK", icon: BrainCircuit },
      { href: "/graphs", label: "Graphs", code: "GR", icon: GitBranch },
      { href: "/tools", label: "Tools", code: "TL", icon: Wrench },
      { href: "/mcp-servers", label: "MCP Servers", code: "MC", icon: ServerCog },
      { href: "/traces", label: "Traces", code: "TR", icon: Network },
    ],
  },
  {
    label: "Knowledge & QA",
    items: [
      { href: "/knowledge", label: "Knowledge Base", code: "KB", icon: BookOpen },
      { href: "/qa", label: "Policy & QA", code: "QA", icon: ShieldCheck },
      { href: "/evaluations", label: "Evaluations", code: "EV", icon: FileText },
    ],
  },
  {
    label: "Platform",
    items: [
      { href: "/integrations", label: "Adapters", code: "AD", icon: PlugZap },
      { href: "/settings", label: "Settings", code: "ST", icon: Settings },
    ],
  },
];

const routeMeta: Array<{ match: string; title: string; description: string }> = [
  {
    match: "/review-queue",
    title: "Review Queue",
    description: "AI drafts and actions that need human judgment before anything leaves the system.",
  },
  {
    match: "/approvals",
    title: "Review Queue",
    description: "AI drafts and actions that need human judgment before anything leaves the system.",
  },
  {
    match: "/conversations",
    title: "Conversations",
    description: "Inspect the message, customer context, AI reasoning, knowledge, tools, approval, audit, and trace.",
  },
  {
    match: "/drivers",
    title: "Contact Drivers",
    description: "Track why customers contact the operation, which agent handles it, and where risk or cost is increasing.",
  },
  {
    match: "/analytics",
    title: "Reports",
    description: "Operational reporting for approvals, trust, escalations, knowledge gaps, and outcomes.",
  },
  {
    match: "/reports",
    title: "Reports",
    description: "Operational reporting for approvals, trust, escalations, knowledge gaps, and outcomes.",
  },
  {
    match: "/agents",
    title: "Agents",
    description: "Configure and monitor the AI workers assigned to service operations.",
  },
  {
    match: "/skills",
    title: "Skills",
    description: "Reusable playbooks that combine instructions, knowledge, tools, and approval rules.",
  },
  {
    match: "/workflows",
    title: "Graphs",
    description: "Stateful orchestration flows that route AI work through context, tools, approvals, and audit.",
  },
  {
    match: "/graphs",
    title: "Graphs",
    description: "Stateful orchestration flows that route AI work through context, tools, approvals, and audit.",
  },
  {
    match: "/tools",
    title: "Tools",
    description: "Approved actions agents can use, with risk levels, permissions, and approval requirements.",
  },
  {
    match: "/mcp-servers",
    title: "MCP Servers",
    description: "External capability servers that expose tools, resources, and prompts to approved Sagad agents.",
  },
  {
    match: "/traces",
    title: "Traces",
    description: "Developer observability for agent runs, tool calls, latency, errors, and LangSmith references.",
  },
  {
    match: "/knowledge",
    title: "Knowledge Base",
    description: "Approved sources, review state, retrieval tests, and missing topics.",
  },
  {
    match: "/qa",
    title: "Policy & QA",
    description: "Approval rules, risk gates, QA rubrics, and compliance checks for AI service work.",
  },
  {
    match: "/evaluations",
    title: "Evaluations",
    description: "Score agent work against policy, trust, tool reliability, and knowledge coverage.",
  },
  {
    match: "/integrations",
    title: "Adapters",
    description: "Provider-agnostic connections for channels, CRMs, knowledge, audit, webhooks, and workflows.",
  },
  {
    match: "/logs",
    title: "Traces",
    description: "Developer observability for audit events, AI drafts, retrieval, tool calls, approvals, and sends.",
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
        "grid content-start gap-4 overflow-y-auto",
        compact ? "px-2 py-3" : "px-3 py-4",
      )}
    >
      {navSections.map((section) => (
        <div className="grid gap-1" key={section.label}>
          {!compact ? (
            <div className="px-3 font-mono text-[10px] font-semibold uppercase text-muted-foreground">
              {section.label}
            </div>
          ) : null}
          {section.items.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            const content = (
              <Link
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex h-8 items-center gap-2.5 rounded-sm px-3 text-[13px] font-semibold text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                  active && "bg-[rgba(0,212,170,0.12)] text-foreground",
                  compact && "justify-center px-0",
                )}
                href={item.href}
              >
                <span
                  className={cn(
                    "grid size-5 shrink-0 place-items-center border border-current font-mono text-[9px] opacity-70 transition-opacity group-hover:opacity-100",
                    active && "text-[var(--accent-text)] opacity-100",
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
        </div>
      ))}
    </nav>
  );
}

function SidebarFooter() {
  return (
    <div className="mt-auto border-t border-border p-3">
      <div className="rounded-md border border-border bg-surface-2 p-3">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="font-mono text-[10px] font-semibold uppercase text-muted-foreground">
              Runtime
            </div>
            <div className="mt-1 truncate text-[13px] font-semibold text-foreground">
              Preview workspace
            </div>
          </div>
          <StatusPill tone="info">Seeded</StatusPill>
        </div>
        <div className="mt-3 grid gap-2 text-xs text-muted-foreground">
          <div className="flex items-center justify-between gap-2">
            <span>Outbound writes</span>
            <span className="font-mono text-[var(--accent-text)]">Approval-gated</span>
          </div>
          <div className="flex items-center justify-between gap-2">
            <span>Provider calls</span>
            <span>Server-side</span>
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
        title: "Command Center",
        description: "Live supervision surface for AI work, approval load, agent health, and missing knowledge.",
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
      <div className="grid min-h-screen lg:grid-cols-[248px_minmax(0,1fr)]">
        <aside className="hidden min-h-screen border-r border-border bg-card lg:flex lg:flex-col">
          <div className="flex min-h-14 items-center gap-3 border-b border-border px-4">
            <SagadLogo markOnly theme={theme} />
            <div className="min-w-0">
              <div className="text-[15px] font-bold">SagadOS</div>
              <div className="font-mono text-[10px] uppercase text-muted-foreground">Open-source AI Ops</div>
            </div>
            <div className="ml-auto flex items-center gap-1.5 font-mono text-[10px] uppercase text-muted-foreground">
              <span className="size-1.5 rounded-full bg-[var(--accent)] shadow-[0_0_0_3px_rgba(0,212,170,0.14)]" />
              gated
            </div>
          </div>
          <SidebarNav pathname={pathname} />
          <SidebarFooter />
        </aside>

        <div className="flex min-h-screen min-w-0 flex-col">
          <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur">
            <div className="flex min-h-14 items-center gap-3 px-4 lg:px-5">
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
                      <SagadLogo markOnly theme={theme} />
                      SagadOS
                    </SheetTitle>
                  </SheetHeader>
                  <SidebarNav closeOnNavigate pathname={pathname} />
                  <SidebarFooter />
                </SheetContent>
              </Sheet>

              <div className="min-w-0 flex-1">
                <h1 className="truncate text-lg font-bold lg:text-xl">
                  {meta.title}
                </h1>
                <p className="mt-0.5 hidden truncate text-xs text-muted-foreground md:block">
                  {meta.description}
                </p>
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
          <main className="min-w-0 flex-1 overflow-y-auto p-3 lg:p-4">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
