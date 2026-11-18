import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import { api, ApiError } from "../api";
import type { ExpenseCategory } from "../types";

let categories: ExpenseCategory[];
beforeEach(() => {
  categories = [{ category_id: "food", name: "Alimentación", is_active: true, subcategories: [{ subcategory_id: "drinks", category_id: "food", name: "Bebidas", is_active: true }] }];
  vi.spyOn(api, "listExpenseCategories").mockImplementation(async () => structuredClone(categories));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });
async function open() {
  window.history.replaceState({}, "", "/gastos/categorias"); render(<App />);
  await screen.findByRole("button", { name: "Renombrar categoría Alimentación" });
}

it("creates a category then a subcategory without duplicating the parent in the body", async () => {
  const create = vi.spyOn(api, "createExpenseCategory").mockImplementation(async (name) => {
    const row = { category_id: "health", name, is_active: true }; categories.push({ ...row, subcategories: [] }); return row;
  });
  const child = vi.spyOn(api, "createExpenseSubcategory").mockImplementation(async (id, name) => {
    const row = { subcategory_id: "meds", category_id: id, name, is_active: true }; categories[1].subcategories.push(row); return row;
  });
  await open();
  await userEvent.click(screen.getByRole("button", { name: "Nueva categoría" }));
  await userEvent.type(screen.getByLabelText("Nombre"), "Salud");
  await userEvent.click(screen.getByRole("button", { name: "Guardar nombre" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith("Salud"));
  await userEvent.click(await screen.findByRole("button", { name: "Agregar subcategoría a Salud" }));
  await userEvent.type(screen.getByLabelText("Nombre"), "Medicinas");
  await userEvent.click(screen.getByRole("button", { name: "Guardar nombre" }));
  await waitFor(() => expect(child).toHaveBeenCalledWith("health", "Medicinas"));
  expect(await screen.findByText("Medicinas")).toBeInTheDocument();
});

it("retains a duplicate category name and allows correction", async () => {
  vi.spyOn(api, "updateExpenseCategory").mockRejectedValue(new ApiError(409, "Ya existe ese nombre en el mismo nivel."));
  await open(); await userEvent.click(screen.getByRole("button", { name: "Renombrar categoría Alimentación" }));
  const form = screen.getByRole("region", { name: "Renombrar categoría" });
  await userEvent.clear(within(form).getByLabelText("Nombre"));
  await userEvent.type(within(form).getByLabelText("Nombre"), "Salud");
  await userEvent.click(within(form).getByRole("button", { name: "Guardar nombre" }));
  expect(await within(form).findByRole("alert")).toHaveTextContent("Ya existe ese nombre");
  expect(within(form).getByLabelText("Nombre")).toHaveValue("Salud");
});

it("archives the parent without losing children and reactivates it", async () => {
  const update = vi.spyOn(api, "updateExpenseCategory").mockImplementation(async (_id, input) => {
    categories[0] = { ...categories[0], ...input }; return categories[0];
  });
  await open(); await userEvent.click(screen.getByRole("button", { name: "Archivar categoría Alimentación" }));
  expect(await screen.findByText("No disponible: categoría principal archivada")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Agregar subcategoría a Alimentación" })).toBeDisabled();
  expect(screen.getByText("Bebidas")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Reactivar categoría Alimentación" }));
  await waitFor(() => expect(update).toHaveBeenLastCalledWith("food", { is_active: true }));
});
