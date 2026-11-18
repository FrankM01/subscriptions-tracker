import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { api, ApiError } from "../api";
import * as format from "../format";
import type { UtilityMonthlySummary } from "../types";
import { Dashboard } from "./Dashboard";

const totals: UtilityMonthlySummary = {
  year: 2026, month: 11, pending_count: 2, paid_count: 1,
  total_pending: "45.10", total_paid: "20.20",
};

beforeEach(() => {
  vi.spyOn(format, "todayInLima").mockReturnValue("2026-11-30");
  vi.spyOn(api, "getSummary").mockResolvedValue({ total_monthly_cost: "100.00" });
  vi.spyOn(api, "getAlerts").mockResolvedValue([]);
  vi.spyOn(api, "listSubscriptions").mockResolvedValue([]);
  vi.spyOn(api, "getUtilityMonthlySummary").mockResolvedValue(totals);
  vi.spyOn(api, "getDebtMonthlySummary").mockResolvedValue({
    year: 2026, month: 11, pending_count: 2, paid_count: 1,
    total_pending: "200.50", total_paid: "100.25",
    overdue_before_month_count: 1, total_overdue_before_month: "75.00",
  });
});

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

function openDashboard() { render(<MemoryRouter><Dashboard /></MemoryRouter>); }

it("separates subscription estimates from service totals and links to the Lima period", async () => {
  openDashboard();
  const services = await screen.findByRole("region", { name: "Servicios de este mes" });
  await within(services).findByText("Pendiente · 2");
  expect(api.getUtilityMonthlySummary).toHaveBeenCalledWith(2026, 11);
  expect(within(services).getByText("Pagado · 1")).toBeInTheDocument();
  expect(services).toHaveTextContent("45.10");
  expect(services).toHaveTextContent("20.20");
  expect(services).toHaveTextContent("noviembre de 2026");
  expect(within(services).getByRole("link", { name: "Ver servicios" })).toHaveAttribute("href", "/servicios?period=2026-11");
  expect(screen.getByRole("region", { name: "Gasto mensual estimado" })).toHaveTextContent("100.00");
  expect(screen.getByText(/El monto mensual de suscripciones es una estimación/)).toBeInTheDocument();
  expect(services).toHaveTextContent("Un pago de este período puede haberse realizado en otro mes.");
});

it("shows an unrecorded month honestly while retaining a path to Services", async () => {
  vi.mocked(api.getUtilityMonthlySummary).mockResolvedValue({ ...totals, pending_count: 0, paid_count: 0, total_pending: "0.00", total_paid: "0.00" });
  openDashboard();
  expect(await screen.findByText(/Aún no hay montos registrados para este período/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Ver servicios" })).toBeInTheDocument();
});

it("retries Services independently when subscriptions loaded successfully", async () => {
  vi.mocked(api.getUtilityMonthlySummary).mockRejectedValueOnce(new ApiError(500, "No se pudo consultar Servicios."));
  openDashboard();
  const services = screen.getByRole("region", { name: "Servicios de este mes" });
  expect(await within(services).findByRole("alert")).toHaveTextContent("No se pudo consultar Servicios.");
  expect(screen.getByRole("region", { name: "Gasto mensual estimado" })).toHaveTextContent("100.00");
  expect(within(services).queryByLabelText("Totales de servicios del mes")).not.toBeInTheDocument();
  await userEvent.click(within(services).getByRole("button", { name: "Reintentar" }));
  await within(services).findByText("Pendiente · 2");
  expect(api.getUtilityMonthlySummary).toHaveBeenCalledTimes(2);
  expect(api.getSummary).toHaveBeenCalledTimes(1);
});

it("keeps Services available when the subscription section fails", async () => {
  vi.mocked(api.getSummary).mockRejectedValue(new ApiError(500, "No se pudo consultar Suscripciones."));
  openDashboard();
  expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo consultar Suscripciones.");
  const services = screen.getByRole("region", { name: "Servicios de este mes" });
  expect(await within(services).findByText("Pendiente · 2")).toBeInTheDocument();
  expect(within(services).getByRole("link", { name: "Ver servicios" })).toBeInTheDocument();
});

it("does not show zero totals while the service summary is still loading", async () => {
  let resolve: (value: UtilityMonthlySummary) => void = () => {};
  vi.mocked(api.getUtilityMonthlySummary).mockReturnValue(new Promise((done) => { resolve = done; }));
  openDashboard();
  const services = screen.getByRole("region", { name: "Servicios de este mes" });
  expect(within(services).getByRole("status")).toHaveTextContent("Cargando resumen de servicios");
  expect(within(services).queryByText("Pendiente · 0")).not.toBeInTheDocument();
  resolve(totals);
  await waitFor(() => expect(within(services).queryByRole("status")).not.toBeInTheDocument());
  expect(within(services).getByText("Pendiente · 2")).toBeInTheDocument();
});

it("separates monthly debt installments from earlier arrears and subscription estimates", async () => {
  openDashboard();
  const debts = screen.getByRole("region", { name: "Deudas de este mes" });
  await within(debts).findByText("Cuotas pendientes · 2");
  expect(api.getDebtMonthlySummary).toHaveBeenCalledWith(2026, 11);
  expect(debts).toHaveTextContent("200.50");
  expect(debts).toHaveTextContent("100.25");
  expect(debts).toHaveTextContent("1 cuota vencida pendiente");
  expect(debts).toHaveTextContent("75.00");
  expect(within(debts).getByRole("link", { name: "Ver cuotas del mes" })).toHaveAttribute("href", "/deudas?period=2026-11");
  expect(within(debts).getByRole("link", { name: "Ver todas las deudas" })).toHaveAttribute("href", "/deudas");
  expect(screen.getByRole("region", { name: "Gasto mensual estimado" })).toHaveTextContent("100.00");
  expect(debts).toHaveTextContent("incluidas deudas archivadas");
});

it("retains earlier arrears even when no installments fall in the current month", async () => {
  vi.mocked(api.getDebtMonthlySummary).mockResolvedValue({
    year: 2026, month: 11, pending_count: 0, paid_count: 0,
    total_pending: "0.00", total_paid: "0.00",
    overdue_before_month_count: 2, total_overdue_before_month: "150.00",
  });
  openDashboard();
  const debts = screen.getByRole("region", { name: "Deudas de este mes" });
  expect(await within(debts).findByText("No hay cuotas con vencimiento este mes.")).toBeInTheDocument();
  expect(debts).toHaveTextContent("2 cuotas vencidas pendientes");
  expect(debts).toHaveTextContent("150.00");
});

it("retries debt failures independently without showing stale or zero amounts", async () => {
  vi.mocked(api.getDebtMonthlySummary).mockRejectedValueOnce(new ApiError(500, "No se pudo consultar Deudas."));
  openDashboard();
  const debts = screen.getByRole("region", { name: "Deudas de este mes" });
  expect(await within(debts).findByRole("alert")).toHaveTextContent("No se pudo consultar Deudas.");
  expect(within(debts).queryByLabelText("Totales de deudas del mes")).not.toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Gasto mensual estimado" })).toHaveTextContent("100.00");
  await userEvent.click(within(debts).getByRole("button", { name: "Reintentar" }));
  await within(debts).findByText("Cuotas pendientes · 2");
  expect(api.getDebtMonthlySummary).toHaveBeenCalledTimes(2);
  expect(api.getSummary).toHaveBeenCalledTimes(1);
  expect(api.getUtilityMonthlySummary).toHaveBeenCalledTimes(1);
});

it("does not invent zero debt totals while loading and explains a fully empty result", async () => {
  let finish: (value: Awaited<ReturnType<typeof api.getDebtMonthlySummary>>) => void = () => {};
  vi.mocked(api.getDebtMonthlySummary).mockReturnValue(new Promise((resolve) => { finish = resolve; }));
  openDashboard();
  const debts = screen.getByRole("region", { name: "Deudas de este mes" });
  expect(within(debts).getByRole("status")).toHaveTextContent("Cargando resumen de deudas");
  expect(within(debts).queryByLabelText("Totales de deudas del mes")).not.toBeInTheDocument();
  finish({ year: 2026, month: 11, pending_count: 0, paid_count: 0, total_pending: "0.00",
    total_paid: "0.00", overdue_before_month_count: 0, total_overdue_before_month: "0.00" });
  expect(await within(debts).findByText("No hay cuotas con vencimiento este mes.")).toBeInTheDocument();
  expect(within(debts).getByText("No tienes cuotas pendientes vencidas de meses anteriores.")).toBeInTheDocument();
});
