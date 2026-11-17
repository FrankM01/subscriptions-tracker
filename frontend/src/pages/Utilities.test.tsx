import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import { api, ApiError } from "../api";
import * as auth from "../auth";
import { todayInLima } from "../format";

beforeEach(() => {
  vi.spyOn(api, "getUtilityMonthlySummary").mockImplementation(async (year, month) => ({
    year, month, pending_count: 0, paid_count: 0, total_pending: "0.00", total_paid: "0.00",
  }));
  vi.spyOn(api, "listUtilityEntries").mockResolvedValue([]);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState({}, "", "/");
});

function renderServices() {
  vi.spyOn(auth, "getAuthenticatedUserLabel").mockReturnValue("Usuario de prueba");
  window.history.replaceState({}, "", "/servicios");
  return render(<App />);
}

it("opens Services directly and marks both navigation links active", async () => {
  vi.spyOn(api, "listUtilities").mockResolvedValue([
    { utility_id: "1", name: "Luz", provider: "Proveedor local", is_active: true },
    { utility_id: "2", name: "Internet", provider: null, is_active: false },
  ]);
  renderServices();
  expect(screen.getByRole("heading", { name: "Servicios", level: 1 })).toBeInTheDocument();
  expect(await screen.findByText("Proveedor local")).toBeInTheDocument();
  expect(screen.getByText("Activo")).toBeInTheDocument();
  expect(screen.getByText("Archivado")).toBeInTheDocument();
  const links = screen.getAllByRole("link", { name: "Servicios" });
  expect(links).toHaveLength(2);
  links.forEach((link) => expect(link).toHaveAttribute("aria-current", "page"));
  expect(screen.getAllByRole("link", { name: "Suscripciones" })).toHaveLength(2);
});

it("shows loading then an empty catalog without inventing services", async () => {
  let resolve: (value: []) => void = () => {};
  vi.spyOn(api, "listUtilities").mockReturnValue(new Promise<[]>((done) => { resolve = done; }));
  renderServices();
  expect(screen.getByRole("status")).toHaveTextContent("Cargando servicios");
  resolve([]);
  expect(await screen.findByText("Aún no tienes servicios registrados")).toBeInTheDocument();
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

it("allows retrying a failed load and clears the error after success", async () => {
  const load = vi.spyOn(api, "listUtilities")
    .mockRejectedValueOnce(new ApiError(0, "No se pudo conectar con la aplicación."))
    .mockResolvedValueOnce([]);
  renderServices();
  expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo conectar");
  await userEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(await screen.findByText("Aún no tienes servicios registrados")).toBeInTheDocument();
  await waitFor(() => expect(load).toHaveBeenCalledTimes(2));
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

it("filters pending, paid and missing months while preserving the selected period in detail links", async () => {
  const [year, month] = todayInLima().slice(0, 7).split("-").map(Number);
  vi.spyOn(api, "listUtilities").mockResolvedValue([
    { utility_id: "light", name: "Luz", provider: null, is_active: true },
    { utility_id: "water", name: "Agua", provider: null, is_active: true },
  ]);
  vi.mocked(api.listUtilityEntries).mockImplementation(async (id) => id === "light" ? [{
    entry_id: "pending", utility_id: id, year, month, amount: "45.10",
    due_date: null, paid_date: null, notes: null, status: "pending",
  }] : []);
  renderServices();
  await screen.findByRole("link", { name: "Ver Luz" });
  const filter = screen.getByLabelText("Mostrar registros");
  await userEvent.selectOptions(filter, "pending");
  expect(screen.getByRole("link", { name: "Ver Luz" })).toHaveAttribute("href", `/servicios/light?period=${todayInLima().slice(0, 7)}`);
  expect(screen.queryByRole("link", { name: "Ver Agua" })).not.toBeInTheDocument();
  await userEvent.selectOptions(filter, "missing");
  expect(screen.getByRole("link", { name: "Ver Agua" })).toBeInTheDocument();
  await userEvent.selectOptions(filter, "paid");
  expect(screen.getByText("No hay registros con este filtro")).toBeInTheDocument();
  await userEvent.selectOptions(filter, "all");
  fireEvent.change(screen.getByLabelText("Mes de servicios"), { target: { value: "2025-01" } });
  await waitFor(() => expect(api.getUtilityMonthlySummary).toHaveBeenLastCalledWith(2025, 1));
  await waitFor(() => expect(screen.getByRole("link", { name: "Ver Luz" })).toHaveAttribute("href", "/servicios/light?period=2025-01"));
  expect(within(screen.getByRole("region", { name: "Catálogo de servicios" })).getAllByText("Sin registro")).toHaveLength(4);
});
