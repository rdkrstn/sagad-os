/**
 * Turn-based ("chess clock") timing helpers for conversation threads.
 *
 * Pure and deterministic: no `Date.now()` inside the label functions so they can be
 * driven by a single ticking `nowMs` value from the UI. The live clock component owns
 * the ticking and passes the current time in.
 */

/** Parse an ISO timestamp to epoch ms, or null when unparseable. */
export function parseIsoMs(value: unknown): number | null {
  if (typeof value !== "string" || value.trim() === "") return null;
  const ms = Date.parse(value);
  return Number.isFinite(ms) ? ms : null;
}

/** Whole seconds between two ISO timestamps, clamped to >= 0. Null if either is bad. */
export function secondsBetween(fromIso: unknown, toIso: unknown): number | null {
  const from = parseIsoMs(fromIso);
  const to = parseIsoMs(toIso);
  if (from === null || to === null) return null;
  return Math.max(0, Math.round((to - from) / 1000));
}

/** Whole seconds between an ISO timestamp and a given epoch-ms "now", clamped to >= 0. */
export function elapsedSecondsSince(iso: unknown, nowMs: number): number | null {
  const from = parseIsoMs(iso);
  if (from === null) return null;
  return Math.max(0, Math.round((nowMs - from) / 1000));
}

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

/**
 * Compact duration label with seconds precision: "12s", "3m 12s", "1h 04m".
 * Mirrors the style of minutesLabel() in lib/api but adds seconds resolution for turns.
 */
export function durationLabel(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return "";
  const s = Math.floor(seconds);
  if (s < 60) return `${s}s`;
  const minutes = Math.floor(s / 60);
  const remainder = s % 60;
  if (minutes < 60) return remainder > 0 ? `${minutes}m ${pad2(remainder)}s` : `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const minuteRemainder = minutes % 60;
  return minuteRemainder > 0 ? `${hours}h ${pad2(minuteRemainder)}m` : `${hours}h`;
}

/** Live clock label: "0:07", "12:34", "1:02:03". */
export function compactClock(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return "0:00";
  const s = Math.floor(seconds);
  if (s < 3600) return `${Math.floor(s / 60)}:${pad2(s % 60)}`;
  const hours = Math.floor(s / 3600);
  const minutes = Math.floor((s % 3600) / 60);
  return `${hours}:${pad2(minutes)}:${pad2(s % 60)}`;
}

export type TurnOwner = "Our turn" | "Customer's turn";

/**
 * Whose turn it is to reply, given the sender role of the LAST message.
 * Customer just spoke -> it's our (agent/supervisor) turn. We just spoke -> customer's turn.
 */
export function turnOwnerOf(lastSenderRole: unknown): TurnOwner {
  const role = typeof lastSenderRole === "string" ? lastSenderRole.toLowerCase() : "";
  const isCustomer = role.includes("customer");
  if (isCustomer) return "Our turn";
  // ai_agent / human_agent / supervisor / system -> we (or our system) spoke last.
  return "Customer's turn";
}