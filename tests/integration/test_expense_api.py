"""Authenticated expense lifecycle, monthly reporting and competing writes."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
import os
from threading import Barrier
import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app import auth
from app.auth import get_current_user
from app.database import DEFAULT_DATABASE_PATH, make_engine
from app.main import app
from app.models.expense import ExpenseCategoryCreate, ExpenseCategoryUpdate, ExpenseCreate
from app.repositories.expense_repository import ExpenseConflictError, ExpenseRepository
from app.routers.expenses import get_service
from app.services.expense_service import ExpenseService
from app.utils.dates import today_in_lima

MONTH = "year=2025&month=11"


@pytest.fixture(params=["sqlite", "postgres"])
def expenses(request, tmp_path, monkeypatch):
    admin = None
    engine = None
    schema = "test_expense_api_" + uuid4().hex
    if request.param == "postgres":
        configured = os.getenv("SUBSCRIPTIONS_TEST_POSTGRES_URL")
        if not configured:
            pytest.skip("set SUBSCRIPTIONS_TEST_POSTGRES_URL")
        admin = make_engine(configured)
        with admin.begin() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        url = make_url(configured).update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'expense-api.db'}"
    try:
        monkeypatch.setenv("SUBSCRIPTIONS_DATABASE_URL", url)
        command.upgrade(Config(str(DEFAULT_DATABASE_PATH.parent.parent / "alembic.ini")), "head")
        engine = make_engine(url)
        repository = ExpenseRepository(engine)
        app.dependency_overrides[get_service] = lambda: ExpenseService(repository)
        with TestClient(app) as client:
            yield client, repository, engine
    finally:
        app.dependency_overrides.pop(get_service, None)
        if engine is not None:
            engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            admin.dispose()


def catalog(client):
    rows = client.get("/expense-categories").json()
    return {row["name"]: row for row in rows}


def create(client, **changes):
    food = catalog(client)["Alimentación"]
    response = client.post("/expenses", json={
        "description": "Almuerzo", "quantity": "1", "total_amount": "8.00",
        "expense_date": "2025-11-01", "category_id": food["category_id"],
        "subcategory_id": next(row["subcategory_id"] for row in food["subcategories"] if row["name"] == "Almuerzo"),
        **changes,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_expense_lifecycle_keeps_total_independent_and_restores_archived_classification(expenses):
    client, _, engine = expenses
    expense = create(client, quantity="2", total_amount="6.00")
    path = "/expenses/" + expense["expense_id"]
    assert expense["quantity"] == "2.000" and expense["total_amount"] == "6.00"
    assert client.get(path).json() == expense
    category = "/expense-categories/" + expense["category_id"]
    assert client.patch(category, json={"is_active": False}).status_code == 200
    changed = client.patch(path, json={"description": "  Bebidas  ", "total_amount": "7.50", "notes": " nota "})
    assert changed.status_code == 200
    assert changed.json()["description"] == "Bebidas" and changed.json()["notes"] == "nota"
    assert client.get("/expenses/summary?" + MONTH).json()["total_amount"] == "7.50"
    assert client.post(path + "/void").json()["is_voided"] is True
    assert client.post(path + "/void").status_code == 409
    assert client.patch(path, json={"total_amount": "20"}).status_code == 409
    assert client.get("/expenses?" + MONTH).json()["total_count"] == 0
    assert client.get("/expenses?" + MONTH + "&state=voided").json()["total_count"] == 1
    assert client.get("/expenses/summary?" + MONTH).json()["total_amount"] == "0.00"
    restored = client.post(path + "/restore")
    assert restored.status_code == 200
    assert restored.json()["category_id"] == expense["category_id"]
    assert restored.json()["subcategory_id"] == expense["subcategory_id"]
    assert client.post(path + "/restore").status_code == 409
    engine.dispose()
    assert client.get(path).json()["total_amount"] == "7.50"
    assert client.delete(path).status_code == 405


def test_category_catalog_names_archive_and_subcategory_parent_are_enforced(expenses):
    client, _, _ = expenses
    assert len(catalog(client)) == 6
    parent = client.post("/expense-categories", json={"name": "  Mascotas   y cuidados  "})
    assert parent.status_code == 201
    uid = parent.json()["category_id"]
    base = "/expense-categories/" + uid
    assert parent.json()["name"] == "Mascotas y cuidados"
    assert client.post("/expense-categories", json={"name": "MASCOTAS Y CUIDADOS"}).status_code == 409
    child = client.post(base + "/subcategories", json={"name": " Veterinario "})
    assert child.status_code == 201
    path = base + "/subcategories/" + child.json()["subcategory_id"]
    assert client.post(base + "/subcategories", json={"name": "VETERINARIO"}).status_code == 409
    assert client.patch(path, json={"name": "Consulta"}).json()["name"] == "Consulta"
    other = catalog(client)["Salud"]["category_id"]
    assert client.post(f"/expense-categories/{other}/subcategories", json={"name": "Consulta"}).status_code == 201
    assert client.patch(path, json={"category_id": other}).status_code == 422
    assert client.patch(f"/expense-categories/{other}/subcategories/{child.json()['subcategory_id']}", json={"name": "Moved"}).status_code == 404
    assert client.patch(path, json={"is_active": False}).status_code == 200
    assert client.patch(base, json={"is_active": False}).status_code == 200
    assert client.patch(path, json={"is_active": True}).status_code == 409
    assert client.post(base + "/subcategories", json={"name": "New"}).status_code == 409
    assert client.patch(base, json={"name": "Cuidado animal"}).status_code == 200
    assert client.patch(base, json={"is_active": True}).status_code == 200
    assert client.patch(path, json={"is_active": True}).status_code == 200
    assert client.patch(base, json={"name": "Salud"}).status_code == 409
    assert "Cuidado animal" in catalog(client)


def test_classification_changes_clear_subcategory_and_validate_only_new_assignments(expenses):
    client, _, _ = expenses
    cats = catalog(client)
    food, transport = cats["Alimentación"], cats["Transporte"]
    expense = create(client)
    path = "/expenses/" + expense["expense_id"]
    wrong = {"category_id": transport["category_id"], "subcategory_id": expense["subcategory_id"]}
    assert client.patch(path, json=wrong).status_code == 422
    assert client.get(path).json() == expense
    changed = client.patch(path, json={"category_id": transport["category_id"]})
    assert changed.status_code == 200 and changed.json()["subcategory_id"] is None
    assert client.post("/expenses", json={"description": "Wrong", "total_amount": "3", **wrong}).status_code == 422
    child = transport["subcategories"][0]
    child_path = f"/expense-categories/{transport['category_id']}/subcategories/{child['subcategory_id']}"
    assert client.patch(child_path, json={"is_active": False}).status_code == 200
    assert client.patch(path, json={"subcategory_id": child["subcategory_id"]}).status_code == 409
    assert client.patch("/expense-categories/" + food["category_id"], json={"is_active": False}).status_code == 200
    assert client.patch(path, json={"category_id": food["category_id"]}).status_code == 409
    response = client.post("/expenses", json={"description": "Archived", "total_amount": "3", "category_id": food["category_id"]})
    assert response.status_code == 409
    assert client.patch(path, json={"category_id": str(uuid4())}).status_code == 404


def test_filters_pagination_and_summary_reconcile_with_exact_monthly_totals(expenses):
    client, _, _ = expenses
    food = catalog(client)["Alimentación"]
    transport = catalog(client)["Transporte"]
    lunch = create(client, quantity="2")
    create(client, description="Desayuno", total_amount="3", quantity="0.125", subcategory_id=None, expense_date="2025-11-02")
    create(client, description="Bebidas 100% natural", total_amount="3", subcategory_id=None)
    create(client, description="Movilidad", total_amount="3", category_id=transport["category_id"], subcategory_id=None)
    create(client, expense_date="2025-10-31", total_amount="999")
    voided = create(client, total_amount="1000")
    client.post("/expenses/" + voided["expense_id"] + "/void")
    result = client.get("/expenses?" + MONTH + "&limit=2&offset=1").json()
    assert len(result["items"]) == 2 and result["total_count"] == 4
    assert client.get("/expenses?" + MONTH + "&offset=100").json()["total_count"] == 4
    assert client.get("/expenses?" + MONTH + "&state=all").json()["total_count"] == 5
    summary = client.get("/expenses/summary?" + MONTH).json()
    assert summary["total_amount"] == "17.00" and summary["count"] == 4
    assert len(summary["days"]) == 30
    assert summary["days"][0]["total_amount"] == "14.00"
    assert summary["days"][1]["cumulative_amount"] == "17.00"
    assert summary["days"][2]["total_amount"] == "0.00"
    assert summary["days"][-1]["cumulative_amount"] == "17.00"
    assert sum(Decimal(row["total_amount"]) for row in summary["categories"]) == Decimal("17.00")
    assert sum(Decimal(row["total_amount"]) for row in summary["subcategories"]) == Decimal("17.00")
    assert any(row["subcategory_id"] is None for row in summary["subcategories"])
    for query, count, total in [
        ("category_id=" + food["category_id"], 3, "14.00"),
        ("subcategory_id=" + lunch["subcategory_id"], 1, "8.00"),
        ("search=ALMUERZO", 1, "8.00"), ("search=%25", 1, "3.00"),
    ]:
        assert client.get("/expenses?" + MONTH + "&" + query).json()["total_count"] == count
        assert client.get("/expenses/summary?" + MONTH + "&" + query).json()["total_amount"] == total
    client.patch("/expenses/" + lunch["expense_id"], json={"expense_date": "2025-10-31"})
    assert client.get("/expenses/summary?" + MONTH).json()["total_amount"] == "9.00"


def test_empty_leap_current_and_future_month_series(expenses):
    client, _, _ = expenses
    leap = client.get("/expenses/summary?year=2024&month=2").json()
    assert len(leap["days"]) == 29
    assert leap["count"] == 0 and leap["categories"] == []
    assert all(row["total_amount"] == "0.00" for row in leap["days"])
    today = today_in_lima()
    current = client.get(f"/expenses/summary?year={today.year}&month={today.month}").json()
    assert len(current["days"]) == today.day
    assert client.get("/expenses/summary?year=9999&month=12").json()["days"] == []


@pytest.mark.parametrize("changes", [
    {}, {"quantity": "0"}, {"quantity": "0.0001"}, {"total_amount": None},
    {"expense_date": (today_in_lima() + timedelta(days=1)).isoformat()},
    {"category_id": None}, {"description": " "}, {"is_voided": True},
])
def test_invalid_updates_do_not_modify_the_expense(expenses, changes):
    client, _, _ = expenses
    expense = create(client)
    path = "/expenses/" + expense["expense_id"]
    assert client.patch(path, json=changes).status_code == 422
    assert client.get(path).json() == expense


def test_missing_resources_bad_queries_and_public_storage_error(expenses, tmp_path):
    client, _, _ = expenses
    uid = str(uuid4())
    for response in (client.get('/expenses/' + uid), client.patch('/expenses/' + uid, json={"description": "New"}),
                     client.post('/expenses/' + uid + '/void'), client.post('/expenses/' + uid + '/restore'),
                     client.patch('/expense-categories/' + uid, json={"name": "New"})):
        assert response.status_code == 404
    for query in ("", "year=2025&month=13", MONTH + "&limit=201", MONTH + "&offset=-1", MONTH + "&state=wrong"):
        assert client.get('/expenses?' + query).status_code == 422
    assert client.get('/expenses/invalid').status_code == 422
    for body in ({}, {"name": None}, {"name": " "}, {"is_active": "false"}):
        parent = catalog(client)["Alimentación"]["category_id"]
        assert client.patch('/expense-categories/' + parent, json=body).status_code == 422
    missing = make_engine(f"sqlite:///{tmp_path / 'unmigrated.db'}")
    app.dependency_overrides[get_service] = lambda: ExpenseService(ExpenseRepository(missing))
    try:
        for route in ('/expenses?' + MONTH, '/expenses/summary?' + MONTH, '/expense-categories'):
            response = client.get(route)
            assert response.status_code == 500
            assert response.json() == {"detail": "No se pudo acceder a los gastos diarios."}
    finally:
        missing.dispose()


@pytest.mark.parametrize("operation", ["void", "restore", "archive_vs_create", "duplicate_category"])
def test_competing_writes_preserve_valid_states(expenses, operation):
    client, repository, _ = expenses
    expense = create(client)
    uid = expense["expense_id"]
    if operation == "restore":
        repository.set_voided(uid, True)
    barrier = Barrier(2)

    def run(index: int) -> str:
        barrier.wait(timeout=10)
        try:
            if operation == "duplicate_category":
                # Service translates the DB uniqueness race into a public conflict.
                result = client.post('/expense-categories', json={"name": "Concurrent"})
                return "ok" if result.status_code == 201 else str(result.status_code)
            if operation == "archive_vs_create":
                if index == 0:
                    repository.update_category(expense["category_id"], ExpenseCategoryUpdate(is_active=False))
                else:
                    repository.create(ExpenseCreate.model_validate({
                        "description": "Race", "total_amount": "3", "category_id": expense["category_id"],
                    }))
            else:
                repository.set_voided(uid, operation == "void")
            return "ok"
        except ExpenseConflictError:
            return "409"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(run, range(2)))
    if operation == "archive_vs_create":
        assert outcomes[0] == "ok" and outcomes[1] in ("ok", "409")
        assert next(row for row in repository.list_categories() if str(row.category_id) == expense["category_id"]).is_active is False
    else:
        assert sorted(outcomes) == ["409", "ok"]
        if operation != "duplicate_category":
            assert repository.get(uid).is_voided is (operation == "void")


def test_all_routes_require_authentication_and_signed_token_works(expenses, monkeypatch):
    client, _, _ = expenses
    categories = catalog(client)
    parent = categories["Alimentación"]
    expense = create(client)
    base = '/expenses/' + expense["expense_id"]
    cat = '/expense-categories/' + parent["category_id"]
    sub = cat + '/subcategories/' + expense["subcategory_id"]
    monkeypatch.delitem(app.dependency_overrides, get_current_user, raising=False)
    monkeypatch.setenv("SUBSCRIPTIONS_ENV", "local")
    issuer = "https://issuer.example.test/realms/subscriptions"
    for key, value in {
        "KEYCLOAK_PUBLIC_URL": "https://issuer.example.test", "KEYCLOAK_REALM": "subscriptions",
        "KEYCLOAK_WEB_CLIENT_ID": "subscriptions-web", "KEYCLOAK_ISSUER_URL": issuer,
        "KEYCLOAK_JWKS_URL": issuer + "/certs", "KEYCLOAK_API_AUDIENCE": "subscriptions-api",
    }.items():
        monkeypatch.setenv(key, value)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(auth, "_get_jwks_client", lambda _: SimpleNamespace(
        get_signing_key_from_jwt=lambda _: SimpleNamespace(key=private.public_key()),
    ))
    now = int(time.time())
    token = jwt.encode({"iss": issuer, "sub": "expense-user", "aud": "subscriptions-api", "iat": now, "exp": now + 300}, private, algorithm="RS256")
    headers = {"Authorization": "Bearer " + token}
    for method, path, body in [
        ('GET','/expense-categories',None), ('POST','/expense-categories',{"name":"New"}),
        ('PATCH',cat,{"name":"New"}), ('POST',cat+'/subcategories',{"name":"New"}),
        ('PATCH',sub,{"name":"New"}), ('GET','/expenses?'+MONTH,None),
        ('GET','/expenses/summary?'+MONTH,None), ('POST','/expenses',{"description":"New","total_amount":"2","category_id":parent["category_id"]}),
        ('GET',base,None), ('PATCH',base,{"description":"New"}),
        ('POST',base+'/void',None), ('POST',base+'/restore',None),
    ]:
        rejected = client.request(method,path,json=body)
        assert rejected.status_code == 401 and rejected.headers['www-authenticate'] == 'Bearer'
    assert client.get('/expenses?'+MONTH,headers={"Authorization":"Bearer invalid"}).status_code == 401
    assert client.get('/expense-categories',headers=headers).status_code == 200
    assert client.patch(base,headers=headers,json={"quantity":"0.125"}).json()["quantity"] == "0.125"
    assert client.post(base+'/void',headers=headers).status_code == 200
    assert client.get('/expenses/summary?'+MONTH,headers=headers).json()["count"] == 0
    assert client.post(base+'/restore',headers=headers).status_code == 200
    assert client.get('/expenses/summary?'+MONTH,headers=headers).json()["total_amount"] == "8.00"


def test_multiple_pages_reconcile_after_correction_reclassification_and_month_transfer(expenses):
    client, repository, engine = expenses
    cats = catalog(client)
    food, transport = cats["Alimentación"], cats["Transporte"]
    identifiers = set()
    for index in range(55):
        item = repository.create(ExpenseCreate.model_validate({
            "description": f"Compra {index:02}", "total_amount": "0.10",
            "quantity": "0.125", "expense_date": "2025-11-01",
            "category_id": food["category_id"],
        }))
        identifiers.add(str(item.expense_id))
    first = client.get("/expenses?" + MONTH + "&limit=50").json()
    second = client.get("/expenses?" + MONTH + "&limit=50&offset=50").json()
    rows = first["items"] + second["items"]
    assert first["total_count"] == second["total_count"] == 55
    assert len(first["items"]) == 50 and len(second["items"]) == 5
    assert {row["expense_id"] for row in rows} == identifiers and len(rows) == len(identifiers)
    assert client.get("/expenses?" + MONTH + "&limit=50").json() == first
    assert sum(Decimal(row["total_amount"]) for row in rows) == Decimal("5.50")
    assert client.get("/expenses/summary?" + MONTH).json()["total_amount"] == "5.50"
    path = "/expenses/" + rows[0]["expense_id"]
    assert client.patch(path, json={"total_amount": "0.25", "category_id": transport["category_id"]}).status_code == 200
    summary = client.get("/expenses/summary?" + MONTH).json()
    assert summary["total_amount"] == "5.65" and summary["count"] == 55
    assert {row["category_name"]: row["total_amount"] for row in summary["categories"]} == {"Alimentación": "5.40", "Transporte": "0.25"}
    assert client.patch("/expense-categories/" + transport["category_id"], json={"name": "Traslados", "is_active": False}).status_code == 200
    archived = client.get("/expenses/summary?" + MONTH + "&category_id=" + transport["category_id"]).json()
    assert archived["total_amount"] == "0.25" and archived["categories"][0]["category_name"] == "Traslados"
    assert client.patch(path, json={"expense_date": "2025-10-31"}).status_code == 200
    assert client.get("/expenses/summary?" + MONTH).json()["total_amount"] == "5.40"
    assert client.get("/expenses/summary?year=2025&month=10").json()["total_amount"] == "0.25"
    engine.dispose()
    assert client.get(path).json()["quantity"] == "0.125"
    assert client.post(path + "/void").status_code == 200
    assert client.get("/expenses/summary?year=2025&month=10").json()["total_amount"] == "0.00"
    assert client.post(path + "/restore").status_code == 200
    assert client.get("/expenses/summary?year=2025&month=10").json()["total_amount"] == "0.25"
