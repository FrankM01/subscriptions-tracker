import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import * as auth from "./auth";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("API client", () => {
  it("keeps the archived-service filter and uses the authenticated utility API", async () => {
    vi.spyOn(auth, "getAccessToken").mockResolvedValue("utility-token");
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.listUtilities(false);
    expect(fetchMock).toHaveBeenCalledWith("/utilities?is_active=false", expect.objectContaining({
      headers: { Authorization: "Bearer utility-token" },
    }));
  });

  it("preserves decimal strings and explicit nulls when correcting a monthly entry", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.updateUtilityEntry("utility-id", "entry-id", { amount: "45.10", due_date: null, notes: null });
    expect(fetchMock).toHaveBeenCalledWith("/utilities/utility-id/entries/entry-id", expect.objectContaining({
      method: "PATCH", body: JSON.stringify({ amount: "45.10", due_date: null, notes: null }),
    }));
  });

  it("sends an empty confirmation command to use the pending amount and today's date", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.confirmUtilityPayment("utility-id", "entry-id");
    expect(fetchMock).toHaveBeenCalledWith("/utilities/utility-id/entries/entry-id/confirm", expect.objectContaining({
      method: "POST", body: "{}",
    }));
  });

  it("requests the selected service period and preserves payment conflict details", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.getUtilityMonthlySummary(2025, 11);
    expect(fetchMock).toHaveBeenCalledWith("/utilities/summary?year=2025&month=11", expect.anything());
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ detail: "El pago ya está confirmado." }), { status: 409 }));
    await expect(api.confirmUtilityPayment("utility-id", "entry-id")).rejects.toMatchObject({
      status: 409, message: "El pago ya está confirmado.",
    });
  });

  it("uses the renewal API and sends the expected period identifier", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ renewal_id: 7 }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.confirmRenewal("abc-123", {
      scheduled_date: "2030-01-15",
      paid_date: "2026-10-10",
      paid_amount: "19.90",
    });

    expect(fetchMock).toHaveBeenCalledWith("/subscriptions/abc-123/renewals", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ scheduled_date: "2030-01-15", paid_date: "2026-10-10", paid_amount: "19.90" }),
    }));
  });

  it("attaches the refreshed Keycloak access token as a bearer token", async () => {
    vi.spyOn(auth, "getAccessToken").mockResolvedValue("signed-access-token");
    const fetchMock = vi.fn().mockResolvedValue(new Response("[]", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.listSubscriptions();

    expect(fetchMock).toHaveBeenCalledWith("/subscriptions", expect.objectContaining({
      headers: { Authorization: "Bearer signed-access-token" },
    }));
  });

  it("keeps API conflict details available to the interface", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "The pending renewal date has changed" }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    )));

    await expect(api.listRenewals("abc-123")).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      message: "The pending renewal date has changed",
    });
  });

  it("converts connection failures to a local-server message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(api.getSummary()).rejects.toBeInstanceOf(ApiError);
    await expect(api.getSummary()).rejects.toThrow("Verifica que el servidor esté activo");
  });
});
