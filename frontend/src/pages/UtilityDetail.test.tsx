import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import { api, ApiError } from "../api";
import type { Utility, UtilityEntry } from "../types";

let utility: Utility;
let history: UtilityEntry[];
const previous: UtilityEntry = {
  entry_id: "older", utility_id: "light", year: 2025, month: 10, amount: "40.00",
  due_date: null, paid_date: "2025-11-01", notes: "Mi aporte anterior", status: "paid",
};

beforeEach(() => {
  utility = { utility_id: "light", name: "Luz", provider: "Proveedor", is_active: true };
  history = [{ ...previous }];
  vi.spyOn(api, "getUtility").mockImplementation(async () => ({ ...utility }));
  vi.spyOn(api, "listUtilityEntries").mockImplementation(async () => history.map((entry) => ({ ...entry })));
});

afterEach(() => {
  cleanup(); vi.restoreAllMocks(); window.history.replaceState({}, "", "/");
});

async function openDetail(period = "2025-11") {
  window.history.replaceState({}, "", `/servicios/light?period=${period}`);
  render(<App />);
  await screen.findByRole("heading", { name: "Luz", level: 1 });
}

it("records only my contribution and can enter a historical payment in a different month", async () => {
  const create = vi.spyOn(api, "createUtilityEntry").mockImplementation(async (_id, input) => {
    const entry: UtilityEntry = { ...input, entry_id: "new", utility_id: "light", due_date: input.due_date ?? null,
      paid_date: input.paid_date ?? null, notes: input.notes ?? null, status: input.paid_date ? "paid" : "pending" };
    history = [entry, ...history]; return entry;
  });
  await openDetail();
  expect(screen.getByText(/Último pago:/)).toHaveTextContent("40.00");
  await userEvent.click(screen.getByRole("button", { name: "Registrar mi monto" }));
  const form = screen.getByRole("region", { name: "Registrar mi monto" });
  expect(within(form).getByLabelText("Mi monto (S/)")).toHaveValue("");
  await userEvent.type(within(form).getByLabelText("Mi monto (S/)"), "45,10");
  await userEvent.click(within(form).getByLabelText("Ya pagué este período"));
  fireEvent.change(within(form).getByLabelText("Fecha real del pago"), { target: { value: "2025-12-02" } });
  await userEvent.click(within(form).getByRole("button", { name: "Registrar monto" }));
  await waitFor(() => expect(create).toHaveBeenCalledWith("light", {
    year: 2025, month: 11, amount: "45.10", due_date: null, notes: null, paid_date: "2025-12-02",
  }));
  expect(await screen.findByText("2 registros")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Período seleccionado" })).getByText(/Pagado el/)).toHaveTextContent("diciembre");
});

it("retains input on a duplicate period error instead of closing the form", async () => {
  vi.spyOn(api, "createUtilityEntry").mockRejectedValue(new ApiError(409, "Ya existe un registro para ese servicio y período."));
  await openDetail();
  await userEvent.click(screen.getByRole("button", { name: "Registrar mi monto" }));
  const form = screen.getByRole("region", { name: "Registrar mi monto" });
  await userEvent.type(within(form).getByLabelText("Mi monto (S/)"), "45.10");
  await userEvent.click(within(form).getByRole("button", { name: "Registrar monto" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Ya existe un registro");
  expect(within(form).getByLabelText("Mi monto (S/)")).toHaveValue("45.10");
});

it("prevents double submission and preserves the confirmation conflict message", async () => {
  history = [{ ...previous, entry_id: "pending", month: 11, paid_date: null, status: "pending" }];
  let reject: (reason: Error) => void = () => {};
  const confirm = vi.spyOn(api, "confirmUtilityPayment").mockReturnValue(new Promise((_, fail) => { reject = fail; }));
  await openDetail();
  await userEvent.click(screen.getByRole("button", { name: "Confirmar pago" }));
  const form = screen.getByRole("region", { name: "Confirmar pago" });
  expect(within(form).getByLabelText("Monto que pagué (S/)")).toHaveValue("40.00");
  await userEvent.click(within(form).getByRole("button", { name: "Guardar pago" }));
  expect(within(form).getByRole("button", { name: "Guardando…" })).toBeDisabled();
  expect(within(form).getByRole("button", { name: "Cancelar" })).toBeDisabled();
  expect(confirm).toHaveBeenCalledTimes(1);
  reject(new ApiError(409, "El pago ya está confirmado."));
  expect(await screen.findByRole("alert")).toHaveTextContent("El pago ya está confirmado.");
});

it("corrects paid data without clearing its status, then explicitly returns it to pending", async () => {
  history = [{ ...previous, month: 11 }];
  const update = vi.spyOn(api, "updateUtilityEntry").mockImplementation(async (_uid, _eid, input) => {
    history = [{ ...history[0], ...input }]; return history[0];
  });
  const undo = vi.spyOn(api, "undoUtilityPayment").mockImplementation(async () => {
    history = [{ ...history[0], paid_date: null, status: "pending" }]; return history[0];
  });
  await openDetail();
  await userEvent.click(screen.getByRole("button", { name: "Corregir registro" }));
  const form = screen.getByRole("region", { name: "Corregir registro mensual" });
  const amount = within(form).getByLabelText("Mi monto (S/)");
  await userEvent.clear(amount); await userEvent.type(amount, "42.30");
  await userEvent.clear(within(form).getByLabelText("Notas (opcional)"));
  await userEvent.click(within(form).getByRole("button", { name: "Guardar registro" }));
  await waitFor(() => expect(update).toHaveBeenCalledWith("light", "older", expect.objectContaining({ amount: "42.30", notes: null, paid_date: "2025-11-01" })));
  await userEvent.click(await screen.findByRole("button", { name: "Deshacer pago" }));
  expect(undo).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Volver a pendiente" }));
  expect(await screen.findByRole("button", { name: "Confirmar pago" })).toBeInTheDocument();
  expect(history[0].amount).toBe("42.30");
});

it("reactivates an archived service before allowing another period", async () => {
  utility.is_active = false;
  const update = vi.spyOn(api, "updateUtility").mockImplementation(async (_id, input) => {
    utility = { ...utility, ...input }; return utility;
  });
  await openDetail();
  expect(screen.getByRole("button", { name: "Registrar mi monto" })).toBeDisabled();
  expect(screen.getByText(/Servicio archivado/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Reactivar servicio" }));
  await waitFor(() => expect(update).toHaveBeenCalledWith("light", { is_active: true }));
  expect(await screen.findByRole("button", { name: "Registrar mi monto" })).toBeEnabled();
  expect(screen.getByText("Mi aporte anterior")).toBeInTheDocument();
});

it("reports a missing service and offers a return route", async () => {
  vi.mocked(api.getUtility).mockRejectedValue(new ApiError(404, "Servicio no encontrado."));
  window.history.replaceState({}, "", "/servicios/missing");
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("No encontramos este servicio.");
  expect(screen.getByRole("link", { name: "Volver a servicios" })).toBeInTheDocument();
});
