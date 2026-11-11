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
