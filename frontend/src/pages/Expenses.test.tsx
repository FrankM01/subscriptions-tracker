import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import { api, ApiError } from "../api";
import { todayInLima } from "../format";
import type { Expense, ExpenseCategory } from "../types";

let categories: ExpenseCategory[];
let expenses: Expense[];
beforeEach(() => {
  categories = [
    { category_id: "food", name: "Alimentación", is_active: true, subcategories: [{ subcategory_id: "drinks", category_id: "food", name: "Bebidas", is_active: true }] },
    { category_id: "transport", name: "Transporte", is_active: true, subcategories: [] },
  ];
  expenses = [{ expense_id: "one", description: "Almuerzo", quantity: "1.000", total_amount: "8.00", expense_date: "2025-11-01", category_id: "food", subcategory_id: "drinks", notes: null, is_voided: false }];
  vi.spyOn(api, "listExpenseCategories").mockImplementation(async () => structuredClone(categories));
  vi.spyOn(api, "listExpenses").mockImplementation(async (filters) => {
    const rows = expenses.filter((row) => (filters.state === "all" || row.is_voided === (filters.state === "voided"))
      && (!filters.category_id || row.category_id === filters.category_id));
    return { items: structuredClone(rows), total_count: rows.length, limit: 50, offset: filters.offset ?? 0 };
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });

async function open(path = "/gastos?period=2025-11") {
  window.history.replaceState({}, "", path); render(<App />);
  await screen.findByRole("heading", { name: "Movimientos" });
}

async function fillNewExpense() {
  await userEvent.click(screen.getByRole("button", { name: "Nuevo gasto" }));
  const form = screen.getByRole("region", { name: "Nuevo gasto" });
  await userEvent.type(within(form).getByLabelText("Producto o descripción"), "Bebidas");
  await userEvent.clear(within(form).getByLabelText("Cantidad"));
  await userEvent.type(within(form).getByLabelText("Cantidad"), "2");
  await userEvent.type(within(form).getByLabelText("Importe total (S/)"), "6,00");
  fireEvent.change(within(form).getByLabelText("Fecha del gasto"), { target: { value: "2025-11-02" } });
  await userEvent.selectOptions(within(form).getByLabelText("Categoría del gasto"), "food");
  await userEvent.selectOptions(within(form).getByLabelText("Subcategoría del gasto (opcional)"), "drinks");
  return form;
}

it("opens the direct route and preserves monthly filters and pagination", async () => {
  await open();
  expect(screen.getAllByRole("link", { name: "Gastos diarios" })).toHaveLength(2);
  screen.getAllByRole("link", { name: "Gastos diarios" }).forEach((link) => expect(link).toHaveAttribute("aria-current", "page"));
  await userEvent.selectOptions(screen.getByLabelText("Filtrar categoría"), "food");
  await waitFor(() => expect(api.listExpenses).toHaveBeenLastCalledWith(expect.objectContaining({ year: 2025, month: 11, category_id: "food", offset: 0 })));
  await userEvent.type(screen.getByLabelText("Buscar descripción"), "Almuerzo");
  await userEvent.click(screen.getByRole("button", { name: "Buscar" }));
  await waitFor(() => expect(api.listExpenses).toHaveBeenLastCalledWith(expect.objectContaining({ search: "Almuerzo" })));
  await userEvent.click(screen.getByRole("button", { name: "Limpiar filtros" }));
  expect(screen.getByLabelText("Mes de gastos")).toHaveValue("2025-11");
});

it("registers the total independently and keeps only the date when adding another expense", async () => {
  const create = vi.spyOn(api, "createExpense").mockImplementation(async (input) => {
    const saved: Expense = { ...input, expense_id: "new", is_voided: false }; expenses.push(saved); return saved;
  });
  await open();
  const form = await fillNewExpense();
  await userEvent.click(within(form).getByRole("button", { name: "Guardar y agregar otro" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith({ description: "Bebidas", quantity: "2", total_amount: "6.00", expense_date: "2025-11-02", category_id: "food", subcategory_id: "drinks", notes: null }));
  expect(within(form).getByLabelText("Fecha del gasto")).toHaveValue("2025-11-02");
  expect(within(form).getByLabelText("Cantidad")).toHaveValue("1");
  expect(within(form).getByLabelText("Producto o descripción")).toHaveValue("");
  expect(within(form).getByLabelText("Importe total (S/)")).toHaveValue("");
  expect(within(form).getByLabelText("Categoría del gasto")).toHaveValue("");
  expect(within(form).getByLabelText("Subcategoría del gasto (opcional)")).toHaveValue("");
});

it("blocks duplicate submissions and keeps the input on an API conflict", async () => {
  let fail: (error: Error) => void = () => {};
  const create = vi.spyOn(api, "createExpense").mockReturnValue(new Promise((_, reject) => { fail = reject; }));
  await open(); const form = await fillNewExpense();
  await userEvent.click(within(form).getByRole("button", { name: "Guardar gasto" }));
  expect(within(form).getByRole("button", { name: "Guardando…" })).toBeDisabled();
  expect(within(form).getByRole("button", { name: "Cancelar" })).toBeDisabled();
  expect(create).toHaveBeenCalledTimes(1);
  fail(new ApiError(409, "La categoría está archivada."));
  expect(await within(form).findByRole("alert")).toHaveTextContent("La categoría está archivada.");
  expect(within(form).getByLabelText("Producto o descripción")).toHaveValue("Bebidas");
});

it("keeps archived classification for corrections and clears child on a new category", async () => {
  categories[0].is_active = false;
  const update = vi.spyOn(api, "updateExpense").mockImplementation(async (_id, input) => {
    expenses[0] = { ...expenses[0], ...input }; return expenses[0];
  });
  await open();
  await userEvent.click(screen.getByRole("button", { name: "Editar gasto Almuerzo" }));
  const form = screen.getByRole("region", { name: "Editar gasto" });
  expect(within(form).getByLabelText("Categoría del gasto")).toHaveValue("food");
  await userEvent.clear(within(form).getByLabelText("Importe total (S/)"));
  await userEvent.type(within(form).getByLabelText("Importe total (S/)"), "9.00");
  await userEvent.click(within(form).getByRole("button", { name: "Guardar gasto" }));
  await waitFor(() => expect(update).toHaveBeenCalledWith("one", expect.objectContaining({ category_id: "food", subcategory_id: "drinks", total_amount: "9.00" })));
  await userEvent.click(await screen.findByRole("button", { name: "Editar gasto Almuerzo" }));
  await userEvent.selectOptions(screen.getByLabelText("Categoría del gasto"), "transport");
  expect(screen.getByLabelText("Subcategoría del gasto (opcional)")).toHaveValue("");
  await userEvent.click(screen.getByRole("button", { name: "Guardar gasto" }));
  await waitFor(() => expect(update).toHaveBeenLastCalledWith("one", expect.objectContaining({ category_id: "transport", subcategory_id: null })));
});

it("requires confirmation before voiding and restores from the voided filter", async () => {
  const annul = vi.spyOn(api, "voidExpense").mockImplementation(async () => { expenses[0].is_voided = true; return expenses[0]; });
  const restore = vi.spyOn(api, "restoreExpense").mockImplementation(async () => { expenses[0].is_voided = false; return expenses[0]; });
  await open();
  await userEvent.click(screen.getByRole("button", { name: "Anular gasto Almuerzo" }));
  expect(annul).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Confirmar anulación" }));
  expect(await screen.findByText("No hay gastos con estos filtros")).toBeInTheDocument();
  await userEvent.selectOptions(screen.getByLabelText("Estado de gastos"), "voided");
  await userEvent.click(await screen.findByRole("button", { name: "Restaurar gasto Almuerzo" }));
  await userEvent.click(within(screen.getByRole("region", { name: "Restaurar gasto" })).getByRole("button", { name: "Restaurar gasto" }));
  await waitFor(() => expect(restore).toHaveBeenCalledWith("one"));
});

it("handles paginated days and recovers when the last page becomes empty", async () => {
  vi.mocked(api.listExpenses).mockImplementation(async (filters) => ({ items: (filters.offset ?? 0) < 50 ? expenses : [], total_count: 50, limit: 50, offset: filters.offset ?? 0 }));
  await open("/gastos?period=2025-11&page=2");
  await waitFor(() => expect(screen.getByText("Página 1 de 1")).toBeInTheDocument());
  expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
});

it("retries history errors without depending on a new category request", async () => {
  vi.mocked(api.listExpenses).mockRejectedValueOnce(new ApiError(500, "No se pudo consultar gastos."));
  window.history.replaceState({}, "", "/gastos"); render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo consultar gastos.");
  await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(await screen.findByRole("heading", { name: "Movimientos" })).toBeInTheDocument();
  expect(api.listExpenseCategories).toHaveBeenCalledTimes(1);
});

it("validates fractional quantity while keeping today's default for a new expense", async () => {
  const create = vi.spyOn(api, "createExpense");
  await open(); const form = await fillNewExpense();
  fireEvent.change(within(form).getByLabelText("Cantidad"), { target: { value: "0.0001" } });
  await userEvent.click(within(form).getByRole("button", { name: "Guardar gasto" }));
  expect(await within(form).findByRole("alert")).toHaveTextContent("hasta tres decimales");
  expect(create).not.toHaveBeenCalled();
  fireEvent.change(within(form).getByLabelText("Cantidad"), { target: { value: "0.125" } });
  fireEvent.change(within(form).getByLabelText("Fecha del gasto"), { target: { value: todayInLima() } });
  expect(within(form).getByLabelText("Cantidad")).toHaveValue("0.125");
});
