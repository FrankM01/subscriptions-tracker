# Root conftest.py — shared fixtures will be added here as the project grows.
import pytest

from app.auth import get_current_user
from app.main import app


@pytest.fixture(autouse=True)
def override_authentication_for_existing_tests():
    """Keep domain/API tests isolated from the external identity provider."""
    app.dependency_overrides[get_current_user] = lambda: {"sub": "unit-test-user"}
    yield
    app.dependency_overrides.pop(get_current_user, None)
