"""Catalog API backed by a temporary persistent database."""

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import Base, make_engine
from app.db_models import UtilityEntryRecord
from app.main import app
from app.repositories.utility_repository import UtilityRepository
from app.routers.utilities import get_service
from app.services.utility_service import UtilityService


@pytest.fixture
def catalog(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'utilities.db'}")
    Base.metadata.create_all(engine)
    repository = UtilityRepository(engine)
    app.dependency_overrides[get_service] = lambda: UtilityService(repository)
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_service, None)
        engine.dispose()


def create_utility(client, name="Luz", provider="Proveedor local"):
    response = client.post("/utilities", json={"name": name, "provider": provider})
    assert response.status_code == 201
    return response.json()


def test_catalog_create_detail_edit_filter_archive_and_reactivate(catalog):
    client, _ = catalog
    assert client.get("/utilities").json() == []
    utility = create_utility(client, "  Luz  ", "  Proveedor local  ")
    path = f"/utilities/{utility['utility_id']}"
    assert utility["name"] == "Luz"
    assert utility["provider"] == "Proveedor local"
    assert utility["is_active"] is True
    assert client.get(path).json() == utility
    assert client.get(path + "/entries").json() == []

    edited = client.patch(path, json={"name": "Electricidad", "provider": None})
    assert edited.status_code == 200
    assert edited.json()["name"] == "Electricidad"
    assert edited.json()["provider"] is None
    assert edited.json()["is_active"] is True

    assert client.patch(path, json={"is_active": False}).json()["is_active"] is False
    assert client.get("/utilities?is_active=true").json() == []
    assert len(client.get("/utilities?is_active=false").json()) == 1
    assert len(client.get("/utilities").json()) == 1
    assert client.patch(path, json={"is_active": True}).json()["is_active"] is True
    assert client.get("/utilities?is_active=false").json() == []
    assert client.get(path).json()["name"] == "Electricidad"


def test_history_survives_archive_and_repository_recreation(catalog):
    client, engine = catalog
    utility = create_utility(client)
    utility_id = utility["utility_id"]
    other_id = create_utility(client, "Agua")["utility_id"]
    with Session(engine) as session, session.begin():
        for uid, year, month, paid_date, amount in [
            (utility_id, 2025, 12, date(2026, 1, 2), 4510),
            (utility_id, 2026, 1, None, 5000),
            (other_id, 2026, 1, None, 3000),
        ]:
            session.add(UtilityEntryRecord(
                entry_id=str(uuid4()), utility_id=uid, year=year, month=month,
                amount_cents=amount, paid_date=paid_date,
            ))
    path = f"/utilities/{utility_id}"
    assert client.patch(path, json={"is_active": False}).status_code == 200
    history = client.get(path + "/entries")
    assert history.status_code == 200
    assert [(e["year"], e["month"]) for e in history.json()] == [(2026, 1), (2025, 12)]
    assert [e["status"] for e in history.json()] == ["pending", "paid"]
    assert [e["amount"] for e in history.json()] == ["50.00", "45.10"]
    assert history.json()[1]["paid_date"] == "2026-01-02"
    recreated = UtilityRepository(engine)
    assert recreated.get(utility_id).is_active is False
    assert len(recreated.list_entries(utility_id)) == 2
    assert client.patch(path, json={"is_active": True}).status_code == 200
    assert client.get(path + "/entries").json() == history.json()
    assert client.delete(path).status_code == 405
    assert client.get(path + "/entries").json() == history.json()


@pytest.mark.parametrize("payload", [
    {}, {"name": " "}, {"name": None}, {"name": "Luz", "is_active": False},
    {"name": "Luz", "unexpected": True},
])
def test_invalid_create_is_rejected(catalog, payload):
    client, _ = catalog
    assert client.post("/utilities", json=payload).status_code == 422
    assert client.get("/utilities").json() == []


@pytest.mark.parametrize("payload", [
    {}, {"name": " "}, {"name": None}, {"is_active": None},
    {"is_active": "false"}, {"is_active": 0}, {"unknown": "value"},
])
def test_invalid_update_leaves_service_unchanged(catalog, payload):
    client, _ = catalog
    utility = create_utility(client)
    path = f"/utilities/{utility['utility_id']}"
    assert client.patch(path, json=payload).status_code == 422
    assert client.get(path).json() == utility


def test_clearing_provider_does_not_modify_other_fields(catalog):
    client, _ = catalog
    utility = create_utility(client)
    path = f"/utilities/{utility['utility_id']}"
    response = client.patch(path, json={"provider": "  "})
    assert response.status_code == 200
    assert response.json() == {**utility, "provider": None}


def test_missing_service_invalid_ids_and_query(catalog):
    client, _ = catalog
    missing_path = f"/utilities/{uuid4()}"
    for response in (
        client.get(missing_path), client.patch(missing_path, json={"is_active": False}),
        client.get(missing_path + "/entries"),
    ):
        assert response.status_code == 404
        assert response.json() == {"detail": "Servicio no encontrado."}
    assert client.get("/utilities/not-a-uuid").status_code == 422
    assert client.get("/utilities?is_active=invalid").status_code == 422


@pytest.mark.parametrize("method,suffix,payload", [
    ("GET", "", None), ("POST", "", {"name": "Luz"}),
    ("GET", "/id", None), ("PATCH", "/id", {"is_active": False}),
    ("GET", "/id/entries", None),
])
def test_every_catalog_route_requires_authentication(catalog, monkeypatch, method, suffix, payload):
    client, _ = catalog
    monkeypatch.delitem(app.dependency_overrides, get_current_user)
    monkeypatch.setenv("SUBSCRIPTIONS_ENV", "local")
    path = "/utilities" + suffix.replace("/id", f"/{uuid4()}")
    response = client.request(method, path, json=payload)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_database_failures_return_public_error_without_sql_details(catalog, tmp_path):
    client, _ = catalog
    missing_schema = make_engine(f"sqlite:///{tmp_path / 'unmigrated.db'}")
    app.dependency_overrides[get_service] = lambda: UtilityService(UtilityRepository(missing_schema))
    try:
        for response in (
            client.get("/utilities"), client.post("/utilities", json={"name": "Luz"}),
            client.get(f"/utilities/{uuid4()}"),
            client.patch(f"/utilities/{uuid4()}", json={"is_active": False}),
        ):
            assert response.status_code == 500
            assert response.json() == {"detail": "No se pudo acceder al catálogo de servicios."}
    finally:
        missing_schema.dispose()
