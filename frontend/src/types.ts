export type BillingCycle = "monthly" | "yearly";

export interface Subscription {
  subscription_id: string;
  name: string;
  cost: string;
  billing_cycle: BillingCycle;
  renewal_date: string;
  is_active: boolean;
}

export interface RenewalEntry {
  renewal_id: number;
  subscription_id: string;
  scheduled_date: string;
  paid_date: string;
  paid_amount: string;
}

export interface RenewalAlert {
  subscription_id: string;
  name: string;
  renewal_date: string;
  billing_cycle: BillingCycle;
  days_until_renewal: number;
}

export interface Summary {
  total_monthly_cost: string;
}

export interface SubscriptionInput {
  name: string;
  cost: string;
  billing_cycle: BillingCycle;
  renewal_date: string;
  is_active?: boolean;
}

export type SubscriptionUpdateInput = Partial<SubscriptionInput>;

export interface RenewalConfirmationInput {
  scheduled_date: string;
  paid_date?: string;
  paid_amount?: string;
}

export interface Utility {
  utility_id: string;
  name: string;
  provider: string | null;
  is_active: boolean;
}

export interface UtilityInput {
  name: string;
  provider?: string | null;
}

export interface UtilityUpdateInput extends Partial<UtilityInput> {
  is_active?: boolean;
}

export interface UtilityEntryInput {
  year: number;
  month: number;
  amount: string;
  due_date?: string | null;
  paid_date?: string | null;
  notes?: string | null;
}

export interface UtilityEntry {
  entry_id: string;
  utility_id: string;
  year: number;
  month: number;
  amount: string;
  due_date: string | null;
  paid_date: string | null;
  notes: string | null;
  status: "pending" | "paid";
}

// Only notes/due_date may be cleared; use undo to clear a payment date.
export interface UtilityEntryUpdateInput {
  year?: number;
  month?: number;
  amount?: string;
  due_date?: string | null;
  paid_date?: string;
  notes?: string | null;
}

export interface UtilityPaymentConfirmationInput {
  amount?: string | null;
  paid_date?: string | null;
}

export interface UtilityMonthlySummary {
  year: number;
  month: number;
  pending_count: number;
  paid_count: number;
  total_pending: string;
  total_paid: string;
}
