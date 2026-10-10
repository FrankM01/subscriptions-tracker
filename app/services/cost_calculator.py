from decimal import Decimal

from app.models.subscription import BillingCycle, Subscription


class CostCalculator:
    @staticmethod
    def monthly_cost(subscription: Subscription) -> Decimal:
        """
        Returns the monthly cost equivalent for a subscription.
        - monthly: returns cost directly
        - yearly: divides cost by 12, rounded to 2 decimals
        """
        if subscription.billing_cycle == BillingCycle.monthly:
            return subscription.cost
        return round(subscription.cost / Decimal("12"), 2)

    @staticmethod
    def total_monthly_cost(subscriptions: list[Subscription]) -> Decimal:
        """
        Returns the total monthly cost for all active subscriptions,
        rounded to 2 decimals. Returns Decimal("0.00") if no active
        subscriptions exist.
        """
        active = [s for s in subscriptions if s.is_active]
        if not active:
            return Decimal("0.00")
        total = sum(CostCalculator.monthly_cost(s) for s in active)
        return round(total, 2)
