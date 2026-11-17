import type { UtilityEntry } from "./types";

export function parseUtilityPeriod(value: string | null): { year: number; month: number } | null {
  if (!value || !/^[0-9]{4}-(0[1-9]|1[0-2])$/.test(value)) return null;
  const [year, month] = value.split("-").map(Number);
  return year >= 1900 ? { year, month } : null;
}

export function entryPeriod(entry: Pick<UtilityEntry, "year" | "month">): string {
  return `${entry.year}-${String(entry.month).padStart(2, "0")}`;
}

export function formatUtilityPeriod(period: string): string {
  const parsed = parseUtilityPeriod(period);
  if (!parsed) return period;
  return new Intl.DateTimeFormat("es-PE", { month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(Date.UTC(parsed.year, parsed.month - 1, 1)));
}

export function latestUtilityPayment(entries: UtilityEntry[]): UtilityEntry | undefined {
  return entries.filter((entry) => entry.paid_date !== null)
    .sort((a, b) => b.paid_date!.localeCompare(a.paid_date!) || entryPeriod(b).localeCompare(entryPeriod(a)))[0];
}

export function personalAmount(value: string): string | null {
  const normalized = value.trim().replace(",", ".");
  return /^[0-9]{1,7}(\.[0-9]{1,2})?$/.test(normalized) && Number(normalized) > 0 ? normalized : null;
}
