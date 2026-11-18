import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api, ApiError } from "../api";
import { App } from "../App";
import type { ExpenseMonthlySummary } from "../types";
import { ExpenseAnalysis } from "./ExpenseAnalysis";

const summary: ExpenseMonthlySummary = {
  year: 2025, month: 11, count: 3, total_amount: "17.00",
  categories: [{ category_id: "food", category_name: "Alimentación", subcategory_id: null, subcategory_name: null, count: 2, total_amount: "14.00" }, { category_id: "transport", category_name: "Transporte", subcategory_id: null, subcategory_name: null, count: 1, total_amount: "3.00" }],
  subcategories: [{ category_id: "food", category_name: "Alimentación", subcategory_id: null, subcategory_name: null, count: 1, total_amount: "8.00" }, { category_id: "food", category_name: "Alimentación", subcategory_id: "drinks", subcategory_name: "Bebidas", count: 1, total_amount: "6.00" }, { category_id: "transport", category_name: "Transporte", subcategory_id: null, subcategory_name: null, count: 1, total_amount: "3.00" }],
  days: [{ expense_date: "2025-11-01", count: 2, total_amount: "14.00", cumulative_amount: "14.00" }, { expense_date: "2025-11-02", count: 0, total_amount: "0.00", cumulative_amount: "14.00" }, { expense_date: "2025-11-03", count: 1, total_amount: "3.00", cumulative_amount: "17.00" }],
};
beforeEach(() => { vi.spyOn(api, "getExpenseMonthlySummary").mockResolvedValue(structuredClone(summary)); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });

it("renders backend totals and accessible tables including unclassified subcategories and zero days", async () => {
  render(<ExpenseAnalysis filters={{ year: 2025, month: 11 }} />);
  const analysis = await screen.findByRole("region", { name: "Análisis mensual de gastos" });
  expect(analysis).toHaveTextContent("17.00");
  expect(analysis).toHaveTextContent("3 gastos");
  expect(analysis).toHaveTextContent("Los anulados están excluidos");
  await userEvent.click(screen.getByText("Ver tabla: por subcategoría"));
  const table = screen.getByRole("table", { name: "Por subcategoría: importes de gastos vigentes" });
  expect(within(table).getByRole("rowheader", { name: "Alimentación · Sin subcategoría" })).toBeInTheDocument();
  expect(within(table).getByRole("rowheader", { name: "Transporte · Sin subcategoría" })).toBeInTheDocument();
  await userEvent.click(screen.getByText("Ver tabla de evolución diaria y acumulada"));
  const daily = screen.getByRole("table", { name: "Evolución del gasto: días transcurridos del período" });
  expect(within(daily).getByRole("row", { name: /2 de noviembre de 2025/ })).toHaveTextContent("0.00");
  await userEvent.click(screen.getByRole("button", { name: "Acumulado" }));
  expect(screen.getByRole("button", { name: "Acumulado" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("img", { name: /Evolución acumulada/ })).toBeInTheDocument();
  expect(screen.getByText(/Los días sin gastos mantienen el acumulado/)).toBeInTheDocument();
  expect(api.getExpenseMonthlySummary).toHaveBeenCalledTimes(1);
});

it("shares URL filters across views without sending state or pagination to analytics", async () => {
  vi.spyOn(api, "listExpenseCategories").mockResolvedValue([{ category_id: "food", name: "Alimentación", is_active: false, subcategories: [{ category_id: "food", subcategory_id: "drinks", name: "Bebidas", is_active: false }] }]);
  vi.spyOn(api, "listExpenses").mockResolvedValue({ items: [], total_count: 0, limit: 50, offset: 0 });
  window.history.replaceState({}, "", "/gastos?period=2025-11&category_id=food&subcategory_id=drinks&search=bebidas&state=voided&page=2");
  render(<App />);
  await screen.findByRole("heading", { name: "Movimientos" });
  await userEvent.click(screen.getByRole("button", { name: "Análisis" }));
  await screen.findByRole("region", { name: "Análisis mensual de gastos" });
  expect(api.getExpenseMonthlySummary).toHaveBeenLastCalledWith({ year: 2025, month: 11, category_id: "food", subcategory_id: "drinks", search: "bebidas" });
  expect(screen.queryByLabelText("Estado de gastos")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Filtrar categoría")).toHaveValue("food");
  await userEvent.click(screen.getByRole("button", { name: "Limpiar filtros" }));
  await waitFor(() => expect(api.getExpenseMonthlySummary).toHaveBeenLastCalledWith({ year: 2025, month: 11, category_id: undefined, subcategory_id: undefined, search: "" }));
  expect(window.location.search).toContain("view=analysis");
  await userEvent.click(screen.getByRole("button", { name: "Movimientos" }));
  expect(await screen.findByLabelText("Estado de gastos")).toHaveValue("active");
});

it("never presents stale or invented zero totals during loading or errors and can retry", async () => {
  let finish: (value: ExpenseMonthlySummary) => void = () => {};
  vi.mocked(api.getExpenseMonthlySummary).mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
  const { rerender } = render(<ExpenseAnalysis filters={{ year: 2025, month: 11 }} />);
  expect(screen.getByRole("status")).toHaveTextContent("Cargando análisis");
  expect(screen.queryByText("Total del período")).not.toBeInTheDocument();
  finish(summary);
  await screen.findByText("Total del período");
  vi.mocked(api.getExpenseMonthlySummary).mockRejectedValueOnce(new ApiError(500, "Resumen no disponible."));
  rerender(<ExpenseAnalysis filters={{ year: 2025, month: 10 }} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Resumen no disponible.");
  expect(screen.queryByText("Total del período")).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  await screen.findByText("Total del período");
});

it("handles empty and future months without drawing fabricated series", async () => {
  vi.mocked(api.getExpenseMonthlySummary).mockResolvedValue({ ...summary, count: 0, total_amount: "0.00", categories: [], subcategories: [], days: [] });
  render(<ExpenseAnalysis filters={{ year: 2099, month: 11 }} />);
  expect(await screen.findByText("No hay gastos vigentes con estos filtros")).toBeInTheDocument();
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});

it("ignores an obsolete summary response when the period changes", async () => {
  let old: (value: ExpenseMonthlySummary) => void = () => {};
  vi.mocked(api.getExpenseMonthlySummary).mockReturnValueOnce(new Promise((resolve) => { old = resolve; }));
  const { rerender } = render(<ExpenseAnalysis filters={{ year: 2025, month: 10 }} />);
  rerender(<ExpenseAnalysis filters={{ year: 2025, month: 11 }} />);
  await screen.findByText("Total del período");
  old({ ...summary, total_amount: "999.00" });
  await waitFor(() => expect(screen.queryByText(/999.00/)).not.toBeInTheDocument());
});
