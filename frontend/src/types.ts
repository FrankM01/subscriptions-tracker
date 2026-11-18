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
  initial_payment?: {
    paid_date?: string;
    paid_amount?: string;
  };
}

export type SubscriptionUpdateInput = Partial<Omit<SubscriptionInput, "initial_payment">>;

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

export interface DebtInput {
  name: string;
  creditor: string;
  installment_amount: string;
  total_installments: number;
  previously_paid_installments: number;
  first_due_date: string | null;
  notes: string | null;
}

export interface DebtInstallment {
  installment_id: string;
  debt_id: string;
  number: number;
  amount: string;
  due_date: string;
  paid_date: string | null;
  status: "pending" | "paid";
}

export interface Debt extends DebtInput {
  debt_id: string;
  is_active: boolean;
  paid_installments: number;
  pending_installments: number;
  remaining_balance: string;
  next_due_date: string | null;
  overdue_installments: number;
  status: "pending" | "settled";
  schedule_editable: boolean;
  installments: DebtInstallment[];
}

export interface DebtUpdateInput extends Partial<DebtInput> {
  is_active?: boolean;
}

export interface DebtMonthlySummary {
  year: number;
  month: number;
  pending_count: number;
  paid_count: number;
  total_pending: string;
  total_paid: string;
  overdue_before_month_count: number;
  total_overdue_before_month: string;
}

export interface ExpenseSubcategory {
  subcategory_id: string;
  category_id: string;
  name: string;
  is_active: boolean;
}

export interface ExpenseCategory {
  category_id: string;
  name: string;
  is_active: boolean;
  subcategories: ExpenseSubcategory[];
}

export interface ExpenseInput {
  description: string;
  quantity: string;
  total_amount: string;
  expense_date: string;
  category_id: string;
  subcategory_id: string | null;
  notes: string | null;
}

export interface Expense extends ExpenseInput {
  expense_id: string;
  is_voided: boolean;
}

export interface ExpenseFilters {
  year: number;
  month: number;
  category_id?: string;
  subcategory_id?: string;
  search?: string;
  state?: "active" | "voided" | "all";
  limit?: number;
  offset?: number;
}

export interface ExpensePage {
  items: Expense[];
  total_count: number;
  limit: number;
  offset: number;
}

export interface ExpenseCategoryUpdateInput {
  name?: string;
  is_active?: boolean;
}

export type ExpenseSummaryFilters = Pick<ExpenseFilters, "year" | "month" | "category_id" | "subcategory_id" | "search">;

export interface ExpenseGroupTotal {
  category_id: string;
  category_name: string;
  subcategory_id: string | null;
  subcategory_name: string | null;
  count: number;
  total_amount: string;
}

export interface ExpenseDayTotal {
  expense_date: string;
  count: number;
  total_amount: string;
  cumulative_amount: string;
}

export interface ExpenseMonthlySummary {
  year: number;
  month: number;
  count: number;
  total_amount: string;
  categories: ExpenseGroupTotal[];
  subcategories: ExpenseGroupTotal[];
  days: ExpenseDayTotal[];
}
