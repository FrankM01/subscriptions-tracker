import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "../App";
import { api, ApiError } from "../api";
import * as auth from "../auth";

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
