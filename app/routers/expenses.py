"""Authenticated daily expenses and two-level category catalog."""
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from app.auth import get_current_user
from app.models.expense import (
    Expense, ExpenseCategory, ExpenseCategoryCreate, ExpenseCategoryDetail, ExpenseCategoryUpdate,
    ExpenseCreate, ExpenseFilters, ExpenseMonthlySummary, ExpensePage, ExpenseSubcategory, ExpenseUpdate,
)
from app.models.subscription import ErrorResponse
from app.services.expense_service import ExpenseService

ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 500: {"model": ErrorResponse},
}
router = APIRouter(prefix="/expenses", tags=["expenses"], dependencies=[Depends(get_current_user)], responses=ERRORS)
categories_router = APIRouter(prefix="/expense-categories", tags=["expense-categories"], dependencies=[Depends(get_current_user)], responses=ERRORS)


def get_service(request: Request) -> ExpenseService:
    return request.app.state.expense_service


def get_filters(
    year: int = Query(ge=1900, le=9999), month: int = Query(ge=1, le=12),
    category_id: UUID | None = None, subcategory_id: UUID | None = None,
    search: str = Query(default="", max_length=200),
) -> ExpenseFilters:
    return ExpenseFilters(year=year, month=month, category_id=category_id,
                          subcategory_id=subcategory_id, search=search)


@categories_router.get("", response_model=list[ExpenseCategoryDetail])
def list_categories(service: ExpenseService = Depends(get_service)) -> list[ExpenseCategoryDetail]:
    return service.list_categories()


@categories_router.post("", response_model=ExpenseCategory, status_code=status.HTTP_201_CREATED)
def create_category(data: ExpenseCategoryCreate, service: ExpenseService = Depends(get_service)) -> ExpenseCategory:
    return service.create_category(data)


@categories_router.patch("/{category_id}", response_model=ExpenseCategory)
def update_category(category_id: UUID, data: ExpenseCategoryUpdate, service: ExpenseService = Depends(get_service)) -> ExpenseCategory:
    return service.update_category(str(category_id), data)


@categories_router.post("/{category_id}/subcategories", response_model=ExpenseSubcategory, status_code=status.HTTP_201_CREATED)
def create_subcategory(category_id: UUID, data: ExpenseCategoryCreate, service: ExpenseService = Depends(get_service)) -> ExpenseSubcategory:
    return service.create_subcategory(str(category_id), data)


@categories_router.patch("/{category_id}/subcategories/{subcategory_id}", response_model=ExpenseSubcategory)
def update_subcategory(category_id: UUID, subcategory_id: UUID, data: ExpenseCategoryUpdate,
                       service: ExpenseService = Depends(get_service)) -> ExpenseSubcategory:
    return service.update_subcategory(str(category_id), str(subcategory_id), data)


@router.post("", response_model=Expense, status_code=status.HTTP_201_CREATED)
def create_expense(data: ExpenseCreate, service: ExpenseService = Depends(get_service)) -> Expense:
    return service.create(data)


@router.get("", response_model=ExpensePage)
def list_expenses(
    filters: ExpenseFilters = Depends(get_filters),
    state: Literal["active", "voided", "all"] = "active",
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    service: ExpenseService = Depends(get_service),
) -> ExpensePage:
    return service.list_all(filters, state, limit, offset)


@router.get("/summary", response_model=ExpenseMonthlySummary)
def get_summary(filters: ExpenseFilters = Depends(get_filters), service: ExpenseService = Depends(get_service)) -> ExpenseMonthlySummary:
    """Active expenses only, by actual expense date, unaffected by pagination."""
    return service.get_summary(filters)


@router.get("/{expense_id}", response_model=Expense)
def get_expense(expense_id: UUID, service: ExpenseService = Depends(get_service)) -> Expense:
    return service.get(str(expense_id))


@router.patch("/{expense_id}", response_model=Expense)
def update_expense(expense_id: UUID, data: ExpenseUpdate, service: ExpenseService = Depends(get_service)) -> Expense:
    return service.update(str(expense_id), data)


@router.post("/{expense_id}/void", response_model=Expense)
def void_expense(expense_id: UUID, service: ExpenseService = Depends(get_service)) -> Expense:
    return service.void(str(expense_id))


@router.post("/{expense_id}/restore", response_model=Expense)
def restore_expense(expense_id: UUID, service: ExpenseService = Depends(get_service)) -> Expense:
    return service.restore(str(expense_id))
