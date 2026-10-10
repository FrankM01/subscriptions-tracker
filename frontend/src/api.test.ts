import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
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
