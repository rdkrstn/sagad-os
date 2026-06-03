"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";

type RealtimeState = "connecting" | "connected" | "disabled" | "reconnecting";

interface RealtimeTokenEnabledResponse {
  enabled: true;
  token: string;
  wsUrl: string;
  expiresAt: number;
}

interface RealtimeTokenDisabledResponse {
  enabled: false;
  reason: string;
}

type RealtimeTokenResponse =
  | RealtimeTokenEnabledResponse
  | RealtimeTokenDisabledResponse;

interface RealtimeEvent {
  type?: string;
}

const refreshEvents = new Set([
  "conversation.upserted",
  "conversation.message_appended",
  "approval.updated",
]);

function parseRealtimeEvent(value: string): RealtimeEvent {
  try {
    const parsed = JSON.parse(value) as unknown;
    if (parsed && typeof parsed === "object" && "type" in parsed) {
      const event = parsed as { type?: unknown };
      return typeof event.type === "string" ? { type: event.type } : {};
    }
  } catch {
    return {};
  }
  return {};
}

function statusLabel(state: RealtimeState): string {
  if (state === "connected") return "Live sync";
  if (state === "reconnecting") return "Sync reconnecting";
  if (state === "connecting") return "Sync connecting";
  return "Sync disabled";
}

function statusColor(state: RealtimeState): string {
  if (state === "connected") return "bg-emerald-500";
  if (state === "reconnecting" || state === "connecting") return "bg-amber-500";
  return "bg-muted-foreground";
}

export function ConsoleRealtimeStatus() {
  const router = useRouter();
  const [state, setState] = useState<RealtimeState>("connecting");
  const reconnectTimer = useRef<number | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function connect(): Promise<void> {
      setState((current) => (current === "connected" ? current : "connecting"));
      const response = await fetch("/api/realtime-token", { cache: "no-store" });
      if (!response.ok) {
        setState("disabled");
        return;
      }

      const payload = (await response.json()) as RealtimeTokenResponse;
      if (!payload.enabled) {
        setState("disabled");
        return;
      }

      const url = new URL(payload.wsUrl);
      url.searchParams.set("token", payload.token);
      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
        if (!cancelled) {
          setState("connected");
        }
      };
      socket.onmessage = (event) => {
        if (typeof event.data !== "string") {
          return;
        }
        const realtimeEvent = parseRealtimeEvent(event.data);
        if (realtimeEvent.type && refreshEvents.has(realtimeEvent.type)) {
          router.refresh();
        }
      };
      socket.onclose = () => {
        if (cancelled) {
          return;
        }
        setState("reconnecting");
        reconnectTimer.current = window.setTimeout(() => {
          void connect();
        }, 3000);
      };
      socket.onerror = () => {
        socket.close();
      };
    }

    void connect();

    return () => {
      cancelled = true;
      if (reconnectTimer.current) {
        window.clearTimeout(reconnectTimer.current);
      }
      socketRef.current?.close();
    };
  }, [router]);

  return (
    <Badge className="h-7 gap-1.5" variant="outline">
      <span className={`size-1.5 rounded-full ${statusColor(state)}`} />
      {statusLabel(state)}
    </Badge>
  );
}
