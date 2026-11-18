import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import { api, ApiError } from "../api";
import type { Debt } from "../types";

let debt: Debt;
beforeEach(() => {
  debt = {
    debt_id: "loan", name: "Préstamo estudios", creditor: "Ana", installment_amount: "100.00",
    total_installments: 6, previously_paid_installments: 1, first_due_date: "2025-01-13",
    notes: null, is_active: true, paid_installments: 1, pending_installments: 5,
    remaining_balance: "500.00", next_due_date: "2025-01-13", overdue_installments: 5,
    status: "pending", schedule_editable: true, installments: [{
      installment_id: "quota2", debt_id: "loan", number: 2, amount: "100.00",
      due_date: "2025-01-13", paid_date: null, status: "pending",
    }],
  };
  vi.spyOn(api, "listDebts").mockImplementation(async () => [structuredClone(debt)]);
  vi.spyOn(api, "getDebt").mockImplementation(async () => structuredClone(debt));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/"); });

async function open(path = "/deudas/loan") {
  window.history.replaceState({}, "", path);
  render(<App />);
  await screen.findByRole("heading", { name: path === "/deudas" ? "Mis préstamos" : "Préstamo estudios" });
}

it("opens debts from a direct route, marks navigation active and filters by creditor, month and state", async () => {
  await open("/deudas");
  screen.getAllByRole("link", { name: "Deudas" }).forEach((link) => expect(link).toHaveAttribute("aria-current", "page"));
  const search = screen.getByLabelText("Buscar deuda o persona");
  await userEvent.type(search, "Bea");
  expect(screen.getByText("No hay deudas con estos filtros")).toBeInTheDocument();
  await userEvent.clear(search); await userEvent.type(search, "ANA");
  expect(screen.getByRole("link", { name: "Ver deuda Préstamo estudios" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Mes de vencimiento (opcional)"), { target: { value: "2025-01" } });
  expect(screen.getByRole("link", { name: "Ver deuda Préstamo estudios" })).toHaveAttribute("href", "/deudas/loan?period=2025-01");
  await userEvent.selectOptions(screen.getByLabelText("Mostrar deudas"), "settled");
  expect(screen.getByText("No hay deudas con estos filtros")).toBeInTheDocument();
});

it("creates a loan from declared progress and opens its detail", async () => {
  const create = vi.spyOn(api, "createDebt").mockResolvedValue(debt);
  await open("/deudas");
  await userEvent.click(screen.getByRole("button", { name: "Nueva deuda" }));
  const form = screen.getByRole("region", { name: "Nueva deuda" });
  await userEvent.type(within(form).getByLabelText("Nombre de la deuda"), "Préstamo estudios");
  await userEvent.type(within(form).getByLabelText("Persona a quien debo"), "Ana");
  await userEvent.type(within(form).getByLabelText(/^Importe de cada cuota/), "100,00");
  fireEvent.change(within(form).getByLabelText("Cuotas pagadas antes de usar la app"), { target: { value: "1" } });
  fireEvent.change(within(form).getByLabelText(/^Primer vencimiento pendiente/), { target: { value: "2025-01-13" } });
  expect(within(form).getByText(/Se crearán 5 cuotas pendientes, de la 2 a la 6/)).toBeInTheDocument();
  await userEvent.click(within(form).getByRole("button", { name: "Crear deuda" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith({ name: "Préstamo estudios", creditor: "Ana", installment_amount: "100.00", total_installments: 6, previously_paid_installments: 1, first_due_date: "2025-01-13", notes: null }));
  expect(await screen.findByRole("heading", { name: "Calendario de cuotas" })).toBeInTheDocument();
  expect(screen.getByText(/cuota previa declarada/)).toBeInTheDocument();
});

it("retains the form and input on conflicts without submitting twice", async () => {
  let fail: (reason: Error) => void = () => {};
  const confirm = vi.spyOn(api, "confirmDebtPayment").mockReturnValue(new Promise((_, reject) => { fail = reject; }));
  await open();
  await userEvent.click(screen.getByRole("button", { name: "Pagar cuota 2" }));
  const form = screen.getByRole("region", { name: "Pagar cuota 2" });
  fireEvent.change(within(form).getByLabelText("Fecha real del pago"), { target: { value: "2025-01-01" } });
  await userEvent.click(within(form).getByRole("button", { name: "Confirmar pago completo" }));
  expect(within(form).getByRole("button", { name: "Guardando…" })).toBeDisabled();
  expect(within(form).getByRole("button", { name: "Cancelar" })).toBeDisabled();
  expect(confirm).toHaveBeenCalledExactlyOnceWith("loan", "quota2", "2025-01-01");
  fail(new ApiError(409, "El pago ya está confirmado."));
  expect(await screen.findByRole("alert")).toHaveTextContent("El pago ya está confirmado.");
  expect(within(form).getByLabelText("Fecha real del pago")).toHaveValue("2025-01-01");
});

it("keeps a paid agreement locked while allowing metadata edits", async () => {
  debt.schedule_editable = false;
  const update = vi.spyOn(api, "updateDebt").mockImplementation(async (_id, input) => { debt = { ...debt, ...input }; return debt; });
  await open();
  await userEvent.click(screen.getByRole("button", { name: "Editar deuda" }));
  const form = screen.getByRole("region", { name: "Editar deuda" });
  expect(within(form).queryByLabelText(/^Importe de cada cuota/)).not.toBeInTheDocument();
  expect(within(form).getByText(/calendario y el importe están bloqueados/)).toBeInTheDocument();
  await userEvent.type(within(form).getByLabelText("Notas (opcional)"), "Acordado");
  await userEvent.click(within(form).getByRole("button", { name: "Guardar deuda" }));
  await waitFor(() => expect(update).toHaveBeenCalledWith("loan", { name: "Préstamo estudios", creditor: "Ana", notes: "Acordado" }));
});

it("corrects a paid date and requires explicit confirmation before undo", async () => {
  debt.installments[0] = { ...debt.installments[0], status: "paid", paid_date: "2025-01-01" };
  const correct = vi.spyOn(api, "correctDebtPayment").mockImplementation(async (_id, _iid, date) => {
    debt.installments[0].paid_date = date; return { ...debt.installments[0] };
  });
  const undo = vi.spyOn(api, "undoDebtPayment").mockImplementation(async () => {
    debt.installments[0] = { ...debt.installments[0], status: "pending", paid_date: null };
    return debt.installments[0];
  });
  await open();
  await userEvent.click(screen.getByRole("button", { name: "Corregir fecha de cuota 2" }));
  fireEvent.change(screen.getByLabelText("Fecha real del pago"), { target: { value: "2025-01-02" } });
  await userEvent.click(screen.getByRole("button", { name: "Guardar fecha" }));
  await waitFor(() => expect(correct).toHaveBeenCalledWith("loan", "quota2", "2025-01-02"));
  await userEvent.click(await screen.findByRole("button", { name: "Deshacer pago de cuota 2" }));
  expect(undo).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Volver a pendiente" }));
  expect(await screen.findByRole("button", { name: "Pagar cuota 2" })).toBeInTheDocument();
});

it("preserves archived obligations and reactivates without changing installments", async () => {
  debt.is_active = false;
  const update = vi.spyOn(api, "updateDebt").mockImplementation(async (_id, input) => { debt = { ...debt, ...input }; return debt; });
  await open();
  expect(screen.getByText(/Deuda archivada/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Pagar cuota 2" })).toBeEnabled();
  await userEvent.click(screen.getByRole("button", { name: "Reactivar deuda" }));
  await waitFor(() => expect(update).toHaveBeenCalledWith("loan", { is_active: true }));
  expect(await screen.findByRole("button", { name: "Archivar deuda" })).toBeInTheDocument();
});

it("offers retry and a return link for missing or unavailable debts", async () => {
  vi.mocked(api.getDebt).mockRejectedValueOnce(new ApiError(404, "Deuda no encontrada."));
  window.history.replaceState({}, "", "/deudas/missing"); render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("No encontramos esta deuda.");
  expect(screen.getByRole("link", { name: "Volver a deudas" })).toHaveAttribute("href", "/deudas");
  await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(await screen.findByRole("heading", { name: "Préstamo estudios" })).toBeInTheDocument();
});

it("registers an already settled agreement without inventing a first pending date", async () => {
  const create = vi.spyOn(api, "createDebt").mockResolvedValue(debt);
  await open("/deudas");
  await userEvent.click(screen.getByRole("button", { name: "Nueva deuda" }));
  const form = screen.getByRole("region", { name: "Nueva deuda" });
  await userEvent.type(within(form).getByLabelText("Nombre de la deuda"), "Liquidada");
  await userEvent.type(within(form).getByLabelText("Persona a quien debo"), "Ana");
  await userEvent.type(within(form).getByLabelText(/^Importe de cada cuota/), "20.10");
  fireEvent.change(within(form).getByLabelText("Cuotas pagadas antes de usar la app"), { target: { value: "6" } });
  expect(within(form).queryByLabelText(/^Primer vencimiento pendiente/)).not.toBeInTheDocument();
  await userEvent.click(within(form).getByRole("button", { name: "Crear deuda" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ previously_paid_installments: 6, first_due_date: null })));
});
