import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api";
import { addCalendarDays, todayInLima } from "../format";
import type { Subscription } from "../types";
import { SubscriptionFormModal } from "./SubscriptionForm";

vi.mock("../api", () => ({
  api: {
    createSubscription: vi.fn(),
    updateSubscription: vi.fn(),
  },
  ApiError: class ApiError extends Error {},
}));

const inactive: Subscription = {
  subscription_id: "a4ef7850-574a-48ab-aac1-274ce28e6b68",
  name: "Servicio antiguo",
  cost: "9.90",
  billing_cycle: "monthly",
  renewal_date: "2020-01-10",
  is_active: false,
};

beforeEach(() => vi.clearAllMocks());

describe("SubscriptionFormModal", () => {
  it("creates an active subscription with the entered fields", async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    render(<SubscriptionFormModal onClose={vi.fn()} onSaved={onSaved} />);

    await user.type(screen.getByLabelText("Nombre"), "Música");
    await user.type(screen.getByRole("spinbutton"), "12.50");
    fireEvent.change(document.querySelector('input[type="date"]')!, { target: { value: addCalendarDays(todayInLima(), 10) } });
    await user.click(screen.getByRole("button", { name: "Crear suscripción" }));

    await waitFor(() => expect(api.createSubscription).toHaveBeenCalledWith(expect.objectContaining({
      name: "Música",
      cost: "12.5",
      billing_cycle: "monthly",
      is_active: true,
    })));
    expect(onSaved).toHaveBeenCalledOnce();
  });

  it("requires a manually reviewed future date before reactivation", async () => {
    const user = userEvent.setup();
    render(<SubscriptionFormModal subscription={inactive} onClose={vi.fn()} onSaved={vi.fn()} />);

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("revisa y selecciona la próxima fecha");
    expect(api.updateSubscription).not.toHaveBeenCalled();
  });

  it("sends only changed fields so an overdue subscription can be edited", async () => {
    const user = userEvent.setup();
    render(<SubscriptionFormModal subscription={inactive} onClose={vi.fn()} onSaved={vi.fn()} />);

    const nameInput = screen.getByLabelText("Nombre");
    await user.clear(nameInput);
    await user.type(nameInput, "Servicio actualizado");
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(api.updateSubscription).toHaveBeenCalledWith(
      inactive.subscription_id,
      { name: "Servicio actualizado" },
    ));
  });
});
