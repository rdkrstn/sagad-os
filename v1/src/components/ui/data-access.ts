export type LooseRecord = Record<string, unknown>;

export function asRecord(value: unknown): LooseRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as LooseRecord)
    : {};
}

export function asArray<T = LooseRecord>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}
// TODO: The utility functions in this file are designed to safely extract typed data from loosely-typed records, which is common when dealing with API responses that may have varying structures. As we integrate with the real Agent Studio APIs, we should consider replacing these with more specific types and validation logic based on the actual data shapes returned by the APIs, to improve type safety and reduce reliance on runtime checks.
export function textOf(
  record: LooseRecord,
  keys: string[],
  fallback = "Unassigned",
): string {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value;
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return value.toString();
    }
  }

  return fallback;
}

export function numberOf(
  record: LooseRecord,
  keys: string[],
  fallback = 0,
): number {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string") {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }

  return fallback;
}

export function nestedArray<T = LooseRecord>(
  record: LooseRecord,
  keys: string[],
): T[] {
  for (const key of keys) {
    const value = record[key];
    if (Array.isArray(value)) {
      return value as T[];
    }
  }

  return [];
}
