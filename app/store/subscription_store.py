import threading
from typing import Optional

from app.models.subscription import Subscription, SubscriptionUpdate


class SubscriptionStore:
    def __init__(self) -> None:
        self._store: dict[str, Subscription] = {}
        self._lock = threading.Lock()

    def add(self, subscription: Subscription) -> None:
        """Add a subscription to the store under its subscription_id."""
        with self._lock:
            self._store[str(subscription.subscription_id)] = subscription

    def get(self, subscription_id: str) -> Optional[Subscription]:
        """Return the subscription with the given ID, or None if not found."""
        return self._store.get(subscription_id)

    def list_all(self) -> list[Subscription]:
        """Return all subscriptions as a list."""
        return list(self._store.values())

    def update(self, subscription_id: str, data: SubscriptionUpdate) -> Optional[Subscription]:
        """Apply a partial update (only non-None fields) and return the updated subscription.

        Returns None if the subscription does not exist.
        """
        with self._lock:
            existing = self._store.get(subscription_id)
            if existing is None:
                return None

            updated_fields = existing.model_dump()
            for field, value in data.model_dump(exclude_unset=True).items():
                if value is not None:
                    updated_fields[field] = value

            updated_subscription = Subscription(**updated_fields)
            self._store[subscription_id] = updated_subscription
            return updated_subscription

    def delete(self, subscription_id: str) -> bool:
        """Remove the subscription with the given ID.

        Returns True if deleted, False if not found.
        """
        with self._lock:
            if subscription_id not in self._store:
                return False
            del self._store[subscription_id]
            return True

    def is_available(self) -> bool:
        """Return False if the internal dict is not initialized (i.e., is None)."""
        return self._store is not None
