import type {
  RenewalAlert,
  RenewalConfirmationInput,
  RenewalEntry,
  Subscription,
  SubscriptionInput,
  SubscriptionUpdateInput,
  Summary,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, "No se pudo conectar con la aplicación. Verifica que el servidor esté activo.");
  }

  if (!response.ok) {
    let message = `La solicitud falló (${response.status}).`;
    try {
      const payload = (await response.json()) as { detail?: string | { msg?: string }[] };
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (Array.isArray(payload.detail)) {
        message = payload.detail.map((item) => item.msg).filter(Boolean).join(" ");
      }
    } catch {
      // Keep the status based fallback for non-JSON responses.
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  listSubscriptions: () => request<Subscription[]>("/subscriptions"),
  getSummary: () => request<Summary>("/subscriptions/summary"),
  getAlerts: () => request<RenewalAlert[]>("/subscriptions/alerts"),
  createSubscription: (input: SubscriptionInput) =>
    request<Subscription>("/subscriptions", { method: "POST", body: JSON.stringify(input) }),
  updateSubscription: (id: string, input: SubscriptionUpdateInput) =>
    request<Subscription>(`/subscriptions/${id}`, { method: "PUT", body: JSON.stringify(input) }),
  deleteSubscription: (id: string) =>
    request<void>(`/subscriptions/${id}`, { method: "DELETE" }),
  listRenewals: (id: string) => request<RenewalEntry[]>(`/subscriptions/${id}/renewals`),
  confirmRenewal: (id: string, input: RenewalConfirmationInput) =>
    request<RenewalEntry>(`/subscriptions/${id}/renewals`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  undoRenewal: (id: string) =>
    request<Subscription>(`/subscriptions/${id}/renewals/undo`, { method: "POST" }),
};
