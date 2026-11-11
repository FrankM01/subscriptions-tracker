import { describe, expect, it } from "vitest";
import { addCalendarDays, formatDate, formatMoney, renewalStatus } from "./format";

describe("format helpers", () => {
  it("formats amounts as Peruvian soles with two decimal places", () => {
    expect(formatMoney("125.5")).toContain("125.50");
    expect(formatMoney("125.5")).toContain("S/");
  });

  it("formats a calendar date without shifting its day", () => {
    expect(formatDate("2030-01-15")).toContain("15");
    expect(formatDate("2030-01-15")).toContain("enero");
  });

  it("adds calendar days across month and year boundaries", () => {
    expect(addCalendarDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addCalendarDays("2028-02-28", 1)).toBe("2028-02-29");
  });

  it("labels overdue, due today, and upcoming renewals", () => {
    expect(renewalStatus({ days_until_renewal: -3 })).toBe("Vencida hace 3 días");
    expect(renewalStatus({ days_until_renewal: 0 })).toBe("Vence hoy");
    expect(renewalStatus({ days_until_renewal: 5 })).toBe("En 5 días");
  });
});
