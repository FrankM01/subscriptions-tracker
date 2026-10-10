# Feature: subscriptions-tracker, Property 7: PUT actualiza únicamente los campos provistos y preserva el resto
# Validates: Requirements 3.1

from decimal import Decimal
from datetime import date, timedelta

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.models.subscription import BillingCycle, SubscriptionCreate, SubscriptionUpdate
from app.services.subscription_service import SubscriptionService
from tests.helpers import temporary_repository, valid_name_strategy


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

valid_cost = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999.99"),
    places=2,
).filter(lambda x: not x.is_nan() and not x.is_infinite())

billing_cycle_strategy = st.sampled_from(["monthly", "yearly"])

future_date = st.dates(
    min_value=date.today() + timedelta(days=1),
    max_value=date(2030, 12, 31),
)

valid_subscription_strategy = st.fixed_dictionaries({
    "name": valid_name_strategy(),
    "cost": valid_cost,
    "billing_cycle": billing_cycle_strategy,
    "renewal_date": future_date.map(lambda d: d.isoformat()),
    "is_active": st.booleans(),
})

# All updatable field names
UPDATABLE_FIELDS = ["name", "cost", "billing_cycle", "renewal_date", "is_active"]

# Per-field update value strategies (valid values only)
_field_value_strategies = {
    "name": valid_name_strategy(),
    "cost": valid_cost,
    "billing_cycle": billing_cycle_strategy,
    "renewal_date": future_date.map(lambda d: d.isoformat()),
    "is_active": st.booleans(),
}


# ---------------------------------------------------------------------------
# Property 7: composite strategy and test
# ---------------------------------------------------------------------------

# Use st.composite to draw original + update values together in one strategy
@st.composite
def original_and_update(draw):
    """Draw an original subscription payload AND a non-empty update dict."""
    original = draw(valid_subscription_strategy)

    # Choose which fields to update (at least 1)
    fields = draw(
        st.lists(
            st.sampled_from(UPDATABLE_FIELDS),
            min_size=1,
            max_size=len(UPDATABLE_FIELDS),
            unique=True,
        )
    )

    # Draw new values for the chosen fields
    update = draw(st.fixed_dictionaries({f: _field_value_strategies[f] for f in fields}))
    if original["is_active"] is False and update.get("is_active") is True:
        update["renewal_date"] = draw(_field_value_strategies["renewal_date"])

    return original, update


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(data=original_and_update())
def test_put_updates_only_provided_fields(data):
    """
    **Validates: Requirements 3.1**

    Property 7: For any existing subscription and any non-empty subset of valid
    fields to update (name, cost, billing_cycle, renewal_date, is_active) with
    valid values, the resulting subscription SHALL have exactly those fields
    updated with the new values and all other fields SHALL retain their original values.
    """
    original_payload, update_dict = data

    # Fresh isolated store + service per hypothesis example
    with temporary_repository() as repository:
        service = SubscriptionService(repository=repository)

        # Step 1: Create the subscription and capture original field values
        subscription = service.create(SubscriptionCreate(**original_payload))
        original = subscription.model_dump()
        subscription_id = str(subscription.subscription_id)

        # Step 2: Build SubscriptionUpdate with only the chosen fields
        update = SubscriptionUpdate(**update_dict)

        # Step 3: Perform the update via the service
        updated = service.update(subscription_id, update)
        result = updated.model_dump()

    # Normalise update_dict values for comparison (cost stays Decimal, billing_cycle as str)
    normalised_update: dict = {}
    for field, value in update_dict.items():
        if field == "cost":
            normalised_update[field] = Decimal(str(value))
        elif field == "renewal_date":
            from datetime import date as date_type
            normalised_update[field] = date_type.fromisoformat(value)
        elif field == "billing_cycle":
            normalised_update[field] = BillingCycle(value)
        else:
            normalised_update[field] = value

    # Step 4: Assert that updated fields have the new values
    for field, new_value in normalised_update.items():
        assert result[field] == new_value, (
            f"Field '{field}' expected new value {new_value!r} but got {result[field]!r}"
        )

    # Step 5: Assert that non-updated fields still have original values
    updated_field_names = set(update_dict.keys())
    for field, original_value in original.items():
        if field == "subscription_id":
            # ID must never change
            assert result["subscription_id"] == original_value, (
                f"subscription_id changed from {original_value!r} to {result['subscription_id']!r}"
            )
        elif field not in updated_field_names:
            assert result[field] == original_value, (
                f"Non-updated field '{field}' changed from {original_value!r} to {result[field]!r}"
            )
