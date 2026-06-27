"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, Power } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { StatusPill, toneFromProductStatus } from "@/components/product/product-ui";
import { cn } from "@/lib/utils";
import type { MemberView } from "@/lib/admin/members";

const ROLES: MemberView["role"][] = ["owner", "admin", "supervisor", "agent", "qa", "viewer"];

type Feedback = { status: "idle" | "error" | "saved"; message: string } | null;

export function MembersConsole({
  initialMembers,
  currentUserId,
}: {
  initialMembers: MemberView[];
  currentUserId: string | null;
}) {
  const [members, setMembers] = useState<MemberView[]>(initialMembers);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);

  async function refresh(): Promise<void> {
    try {
      const response = await fetch("/api/admin/members", { cache: "no-store" });
      if (response.ok) {
        const data = (await response.json()) as { members: MemberView[] };
        setMembers(data.members);
      }
    } catch {
      // keep current list on refresh failure
    }
  }

  async function updateRole(member: MemberView, role: MemberView["role"]): Promise<void> {
    if (role === member.role) return;
    setBusyId(member.user_id);
    setFeedback(null);
    try {
      const response = await fetch(`/api/admin/members/${member.user_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role }),
      });
      const data = (await response.json()) as { detail?: string };
      if (response.ok) {
        setFeedback({ status: "saved", message: `${member.name ?? member.email ?? "Member"} is now ${role}.` });
        await refresh();
      } else {
        setFeedback({ status: "error", message: data.detail ?? `Update failed (HTTP ${response.status}).` });
      }
    } catch (error) {
      setFeedback({ status: "error", message: error instanceof Error ? error.message : "Update failed." });
    } finally {
      setBusyId(null);
    }
  }

  async function disableMember(member: MemberView): Promise<void> {
    setBusyId(member.user_id);
    setFeedback(null);
    try {
      const response = await fetch(`/api/admin/members/${member.user_id}`, { method: "DELETE" });
      const data = (await response.json()) as { detail?: string };
      if (response.ok) {
        setFeedback({ status: "saved", message: `${member.name ?? member.email ?? "Member"} disabled.` });
        await refresh();
      } else {
        setFeedback({ status: "error", message: data.detail ?? `Disable failed (HTTP ${response.status}).` });
      }
    } catch (error) {
      setFeedback({ status: "error", message: error instanceof Error ? error.message : "Disable failed." });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-3">
      {feedback ? (
        <p
          className={cn(
            "flex items-center gap-1.5 text-xs",
            feedback.status === "error" ? "text-danger" : "text-[var(--accent-text)]",
          )}
        >
          {feedback.status === "error" ? (
            <AlertTriangle aria-hidden="true" size={13} />
          ) : (
            <CheckCircle2 aria-hidden="true" size={13} />
          )}
          {feedback.message}
        </p>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left font-mono text-[10px] uppercase text-muted-foreground">
              <th className="px-3 py-2 font-semibold">Member</th>
              <th className="px-3 py-2 font-semibold">Role</th>
              <th className="px-3 py-2 font-semibold">Status</th>
              <th className="px-3 py-2 text-right font-semibold">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {members.length === 0 ? (
              <tr>
                <td className="px-3 py-4 text-muted-foreground" colSpan={4}>
                  No members visible. Owner/admin role is required to manage members.
                </td>
              </tr>
            ) : (
              members.map((member) => {
                const isSelf = member.user_id === currentUserId;
                const statusTone = toneFromProductStatus(member.status);
                return (
                  <tr key={member.user_id}>
                    <td className="px-3 py-2.5">
                      <div className="font-medium text-foreground">
                        {member.name ?? "Unnamed"}
                        {isSelf ? (
                          <span className="ml-2 text-[10px] uppercase text-muted-foreground">(you)</span>
                        ) : null}
                      </div>
                      <div className="text-xs text-muted-foreground">{member.email ?? "—"}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      <Select
                        disabled={busyId === member.user_id}
                        onValueChange={(value) => updateRole(member, value as MemberView["role"])}
                        value={member.role}
                      >
                        <SelectTrigger className="h-8 w-36 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.map((role) => (
                            <SelectItem key={role} value={role}>
                              {role}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusPill tone={statusTone}>{member.status}</StatusPill>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <Button
                        disabled={busyId === member.user_id || member.status === "disabled"}
                        onClick={() => disableMember(member)}
                        size="sm"
                        type="button"
                        variant="ghost"
                      >
                        {busyId === member.user_id ? (
                          <Loader2 aria-hidden="true" size={14} className="animate-spin" />
                        ) : (
                          <Power aria-hidden="true" size={14} />
                        )}
                        Disable
                      </Button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
