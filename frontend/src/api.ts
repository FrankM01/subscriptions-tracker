import type {
  RenewalAlert,
  RenewalConfirmationInput,
  RenewalEntry,
  Subscription,
  SubscriptionInput,
  SubscriptionUpdateInput,
  Summary,
  Utility, UtilityInput, UtilityUpdateInput, UtilityEntry, UtilityEntryInput,
  UtilityEntryUpdateInput, UtilityPaymentConfirmationInput, UtilityMonthlySummary,
  Debt, DebtInput, DebtUpdateInput, DebtInstallment,
} from "./types";
import { getAccessToken } from "./auth";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let accessToken: string | undefined;
  try {
    accessToken = await getAccessToken();
  } catch {
    throw new ApiError(401, "La sesión expiró. Inicia sesión nuevamente.");
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
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
  listDebts: () => request<Debt[]>("/debts"),
  getDebt: (id: string) => request<Debt>(`/debts/${id}`),
  createDebt: (input: DebtInput) =>
    request<Debt>("/debts", { method: "POST", body: JSON.stringify(input) }),
  updateDebt: (id: string, input: DebtUpdateInput) =>
    request<Debt>(`/debts/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  confirmDebtPayment: (id: string, installmentId: string, paidDate: string) =>
    request<DebtInstallment>(`/debts/${id}/installments/${installmentId}/confirm`, { method: "POST", body: JSON.stringify({ paid_date: paidDate }) }),
  correctDebtPayment: (id: string, installmentId: string, paidDate: string) =>
    request<DebtInstallment>(`/debts/${id}/installments/${installmentId}`, { method: "PATCH", body: JSON.stringify({ paid_date: paidDate }) }),
  undoDebtPayment: (id: string, installmentId: string) =>
    request<DebtInstallment>(`/debts/${id}/installments/${installmentId}/undo`, { method: "POST" }),
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
  listUtilities: (isActive?: boolean) =>
    request<Utility[]>(`/utilities${isActive === undefined ? "" : `?is_active=${isActive}`}`),
  getUtility: (id: string) => request<Utility>(`/utilities/${id}`),
  createUtility: (input: UtilityInput) =>
    request<Utility>("/utilities", { method: "POST", body: JSON.stringify(input) }),
  updateUtility: (id: string, input: UtilityUpdateInput) =>
    request<Utility>(`/utilities/${id}`, { method: "PATCH", body: JSON.stringify(input) }),
  listUtilityEntries: (id: string) => request<UtilityEntry[]>(`/utilities/${id}/entries`),
  createUtilityEntry: (id: string, input: UtilityEntryInput) =>
    request<UtilityEntry>(`/utilities/${id}/entries`, { method: "POST", body: JSON.stringify(input) }),
  updateUtilityEntry: (id: string, entryId: string, input: UtilityEntryUpdateInput) =>
    request<UtilityEntry>(`/utilities/${id}/entries/${entryId}`, { method: "PATCH", body: JSON.stringify(input) }),
  confirmUtilityPayment: (id: string, entryId: string, input: UtilityPaymentConfirmationInput = {}) =>
    request<UtilityEntry>(`/utilities/${id}/entries/${entryId}/confirm`, { method: "POST", body: JSON.stringify(input) }),
  undoUtilityPayment: (id: string, entryId: string) =>
    request<UtilityEntry>(`/utilities/${id}/entries/${entryId}/undo`, { method: "POST" }),
  getUtilityMonthlySummary: (year: number, month: number) =>
    request<UtilityMonthlySummary>(`/utilities/summary?${new URLSearchParams({ year: String(year), month: String(month) })}`),
};
