from datetime import date

from app.models.subscription import BillingCycle, RenewalAlert, Subscription

ALERT_WINDOW: dict[BillingCycle, int] = {
    BillingCycle.monthly: 7,
    BillingCycle.yearly: 30,
}


class AlertEngine:
    @staticmethod
    def days_until_renewal(renewal_date: date, today: date) -> int:
        """Return the floor of calendar days between today and renewal_date."""
        return (renewal_date - today).days

    @staticmethod
    def evaluate(subscriptions: list[Subscription], today: date) -> list[RenewalAlert]:
        """
        Evaluate active subscriptions and return those within their alert window,
        sorted ascending by days_until_renewal (oldest overdue first, then
        soonest upcoming).

        Includes a subscription if:
          - is_active is True
          - days_until_renewal < 0 (overdue, remains pending indefinitely), or
          - 0 <= days_until_renewal <= ALERT_WINDOW[billing_cycle]
        """
        alerts = []
        for sub in subscriptions:
            if not sub.is_active:
                continue
            days = AlertEngine.days_until_renewal(sub.renewal_date, today)
            window = ALERT_WINDOW[sub.billing_cycle]
            if days <= window:
                alerts.append(
                    RenewalAlert(
                        subscription_id=sub.subscription_id,
                        name=sub.name,
                        renewal_date=sub.renewal_date,
                        billing_cycle=sub.billing_cycle,
                        days_until_renewal=days,
                    )
                )
        return sorted(alerts, key=lambda a: a.days_until_renewal)
