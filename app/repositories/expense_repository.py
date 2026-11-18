"""Atomic daily-expense writes and filtered, exact monthly reporting."""

from calendar import monthrange
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db_models import ExpenseCategoryRecord as CategoryRecord
from app.db_models import ExpenseSubcategoryRecord as SubcategoryRecord
from app.db_models import ExpenseRecord
from app.models.expense import (
    Expense, ExpenseCategory, ExpenseCategoryCreate, ExpenseCategoryDetail, ExpenseCategoryUpdate,
    ExpenseCreate, ExpenseDayTotal, ExpenseFilters, ExpenseGroupTotal, ExpenseMonthlySummary,
    ExpensePage, ExpenseSubcategory, ExpenseUpdate,
)
from app.utils.dates import today_in_lima


class ExpenseNotFoundError(LookupError):
    pass


class ExpenseConflictError(RuntimeError):
    pass


class ExpenseClassificationError(ValueError):
    pass


def money(value: int) -> Decimal:
    return (Decimal(value) / 100).quantize(Decimal("0.01"))


K = TypeVar("K")


def add_group_total(
    groups: dict[K, ExpenseGroupTotal], key: K, row: ExpenseRecord,
    category_name: str, subcategory_id: str | None = None, subcategory_name: str | None = None,
) -> None:
    if key not in groups:
        groups[key] = ExpenseGroupTotal(
            category_id=UUID(row.category_id), category_name=category_name,
            subcategory_id=UUID(subcategory_id) if subcategory_id else None,
            subcategory_name=subcategory_name, count=0, total_amount=Decimal("0.00"),
        )
    groups[key].count += 1
    groups[key].total_amount += money(row.total_amount_cents)


class ExpenseRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        with Session(self._engine) as session:
            try:
                if self._engine.dialect.name == "sqlite":
                    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    @staticmethod
    def _category(row: CategoryRecord) -> ExpenseCategory:
        return ExpenseCategory(category_id=UUID(row.category_id), name=row.name, is_active=row.is_active)

    @staticmethod
    def _subcategory(row: SubcategoryRecord) -> ExpenseSubcategory:
        return ExpenseSubcategory(subcategory_id=UUID(row.subcategory_id), category_id=UUID(row.category_id),
                                  name=row.name, is_active=row.is_active)

    @staticmethod
    def _expense(row: ExpenseRecord) -> Expense:
        return Expense(
            expense_id=UUID(row.expense_id), description=row.description,
            quantity=(Decimal(row.quantity_millis) / 1000).quantize(Decimal("0.001")),
            total_amount=money(row.total_amount_cents), expense_date=row.expense_date,
            category_id=UUID(row.category_id),
            subcategory_id=UUID(row.subcategory_id) if row.subcategory_id else None,
            notes=row.notes, is_voided=row.is_voided,
        )

    @staticmethod
    def _require_category(session: Session, category_id: str) -> CategoryRecord:
        row = session.scalar(select(CategoryRecord).where(CategoryRecord.category_id == category_id).with_for_update())
        if row is None:
            raise ExpenseNotFoundError("Categoría no encontrada.")
        return row

    @staticmethod
    def _require_subcategory(session: Session, category_id: str, subcategory_id: str) -> SubcategoryRecord:
        row = session.scalar(select(SubcategoryRecord).where(
            SubcategoryRecord.subcategory_id == subcategory_id,
            SubcategoryRecord.category_id == category_id,
        ))
        if row is None:
            raise ExpenseNotFoundError("Subcategoría no encontrada en esta categoría.")
        return row

    @staticmethod
    def _require_expense(session: Session, expense_id: str) -> ExpenseRecord:
        row = session.scalar(select(ExpenseRecord).where(ExpenseRecord.expense_id == expense_id).with_for_update())
        if row is None:
            raise ExpenseNotFoundError("Gasto no encontrado.")
        return row

    def list_categories(self) -> list[ExpenseCategoryDetail]:
        # Outer join includes empty and archived categories in the same snapshot.
        statement = select(CategoryRecord, SubcategoryRecord).outerjoin(
            SubcategoryRecord, CategoryRecord.category_id == SubcategoryRecord.category_id,
        ).order_by(CategoryRecord.name_key, SubcategoryRecord.name_key)
        with Session(self._engine) as session:
            categories: dict[str, ExpenseCategoryDetail] = {}
            for parent, child in session.execute(statement):
                if parent.category_id not in categories:
                    categories[parent.category_id] = ExpenseCategoryDetail(
                        **self._category(parent).model_dump(), subcategories=[],
                    )
                if child is not None:
                    categories[parent.category_id].subcategories.append(self._subcategory(child))
            return list(categories.values())

    def create_category(self, data: ExpenseCategoryCreate) -> ExpenseCategory:
        with self._transaction() as session:
            row = CategoryRecord(category_id=str(uuid4()), name=data.name, name_key=data.name.casefold())
            session.add(row)
            session.flush()
            result = self._category(row)
        return result

    def update_category(self, category_id: str, data: ExpenseCategoryUpdate) -> ExpenseCategory:
        with self._transaction() as session:
            row = self._require_category(session, category_id)
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(row, key, value)
            if data.name is not None:
                row.name_key = data.name.casefold()
            session.flush()
            result = self._category(row)
        return result

    def create_subcategory(self, category_id: str, data: ExpenseCategoryCreate) -> ExpenseSubcategory:
        with self._transaction() as session:
            parent = self._require_category(session, category_id)
            if not parent.is_active:
                raise ExpenseConflictError("Reactiva la categoría antes de agregar subcategorías.")
            row = SubcategoryRecord(subcategory_id=str(uuid4()), category_id=category_id,
                                    name=data.name, name_key=data.name.casefold())
            session.add(row)
            session.flush()
            result = self._subcategory(row)
        return result

    def update_subcategory(self, category_id: str, subcategory_id: str, data: ExpenseCategoryUpdate) -> ExpenseSubcategory:
        with self._transaction() as session:
            parent = self._require_category(session, category_id)
            row = self._require_subcategory(session, category_id, subcategory_id)
            if data.is_active is True and not parent.is_active:
                raise ExpenseConflictError("Reactiva primero la categoría principal.")
            for key, value in data.model_dump(exclude_unset=True).items():
                setattr(row, key, value)
            if data.name is not None:
                row.name_key = data.name.casefold()
            session.flush()
            result = self._subcategory(row)
        return result

    def _validate_classification(self, session: Session, category_id: str, subcategory_id: str | None) -> None:
        parent = self._require_category(session, category_id)
        if not parent.is_active:
            raise ExpenseConflictError("La categoría está archivada. Reactívala o selecciona otra.")
        if subcategory_id is not None:
            child = session.get(SubcategoryRecord, subcategory_id)
            if child is None:
                raise ExpenseNotFoundError("Subcategoría no encontrada.")
            if child.category_id != category_id:
                raise ExpenseClassificationError("La subcategoría no pertenece a la categoría seleccionada.")
            if not child.is_active:
                raise ExpenseConflictError("La subcategoría está archivada. Reactívala o selecciona otra.")

    def create(self, data: ExpenseCreate) -> Expense:
        with self._transaction() as session:
            category_id = str(data.category_id)
            subcategory_id = str(data.subcategory_id) if data.subcategory_id else None
            self._validate_classification(session, category_id, subcategory_id)
            row = ExpenseRecord(
                expense_id=str(uuid4()), description=data.description, expense_date=data.expense_date,
                quantity_millis=int(data.quantity * 1000), total_amount_cents=int(data.total_amount * 100),
                category_id=category_id, subcategory_id=subcategory_id, notes=data.notes,
            )
            session.add(row)
            session.flush()
            result = self._expense(row)
        return result

    def get(self, expense_id: str) -> Expense:
        with Session(self._engine) as session:
            row = session.get(ExpenseRecord, expense_id)
            if row is None:
                raise ExpenseNotFoundError("Gasto no encontrado.")
            return self._expense(row)

    def update(self, expense_id: str, data: ExpenseUpdate) -> Expense:
        with self._transaction() as session:
            row = self._require_expense(session, expense_id)
            if row.is_voided:
                raise ExpenseConflictError("Restaura el gasto antes de editarlo.")
            original = self._expense(row)
            fields = data.model_dump(exclude_unset=True)
            if data.category_id is not None and data.category_id != original.category_id and "subcategory_id" not in fields:
                fields["subcategory_id"] = None
            merged = ExpenseCreate.model_validate({**original.model_dump(exclude={"expense_id", "is_voided"}), **fields})
            if (merged.category_id, merged.subcategory_id) != (original.category_id, original.subcategory_id):
                self._validate_classification(session, str(merged.category_id), str(merged.subcategory_id) if merged.subcategory_id else None)
            row.description, row.expense_date, row.notes = merged.description, merged.expense_date, merged.notes
            row.category_id = str(merged.category_id)
            row.subcategory_id = str(merged.subcategory_id) if merged.subcategory_id else None
            row.quantity_millis = int(merged.quantity * 1000)
            row.total_amount_cents = int(merged.total_amount * 100)
            session.flush()
            result = self._expense(row)
        return result

    def set_voided(self, expense_id: str, is_voided: bool) -> Expense:
        with self._transaction() as session:
            row = self._require_expense(session, expense_id)
            if row.is_voided == is_voided:
                raise ExpenseConflictError("El gasto ya está anulado." if is_voided else "El gasto ya está vigente.")
            row.is_voided = is_voided
            session.flush()
            result = self._expense(row)
        return result

    @staticmethod
    def _conditions(filters: ExpenseFilters):
        first = date(filters.year, filters.month, 1)
        last = date(filters.year, filters.month, monthrange(filters.year, filters.month)[1])
        conditions = [ExpenseRecord.expense_date >= first, ExpenseRecord.expense_date <= last]
        if filters.category_id is not None:
            conditions.append(ExpenseRecord.category_id == str(filters.category_id))
        if filters.subcategory_id is not None:
            conditions.append(ExpenseRecord.subcategory_id == str(filters.subcategory_id))
        if filters.search.strip():
            conditions.append(ExpenseRecord.description.icontains(filters.search.strip(), autoescape=True))
        return conditions

    def list_all(self, filters: ExpenseFilters, state: str, limit: int, offset: int) -> ExpensePage:
        statement = select(ExpenseRecord).where(*self._conditions(filters)).order_by(
            ExpenseRecord.expense_date.desc(), ExpenseRecord.expense_id,
        )
        if state != "all":
            statement = statement.where(ExpenseRecord.is_voided == (state == "voided"))
        # Count and page are derived from one statement/snapshot, even while editing.
        with Session(self._engine) as session:
            rows = list(session.scalars(statement))
            return ExpensePage(items=[self._expense(row) for row in rows[offset:offset + limit]],
                               total_count=len(rows), limit=limit, offset=offset)

    def get_summary(self, filters: ExpenseFilters) -> ExpenseMonthlySummary:
        statement = select(ExpenseRecord, CategoryRecord.name, SubcategoryRecord.name).join(
            CategoryRecord, ExpenseRecord.category_id == CategoryRecord.category_id,
        ).outerjoin(SubcategoryRecord, ExpenseRecord.subcategory_id == SubcategoryRecord.subcategory_id).where(
            *self._conditions(filters), ExpenseRecord.is_voided.is_(False),
        )
        categories: dict[str, ExpenseGroupTotal] = {}
        subcategories: dict[tuple[str, str | None], ExpenseGroupTotal] = {}
        per_day: dict[date, tuple[int, int]] = {}
        total_cents = 0
        count = 0
        with Session(self._engine) as session:
            for row, category_name, subcategory_name in session.execute(statement):
                total_cents += row.total_amount_cents
                count += 1
                add_group_total(categories, row.category_id, row, category_name)
                add_group_total(subcategories, (row.category_id, row.subcategory_id), row,
                                category_name, row.subcategory_id, subcategory_name)
                daily_count, daily_cents = per_day.get(row.expense_date, (0, 0))
                per_day[row.expense_date] = daily_count + 1, daily_cents + row.total_amount_cents
        days = []
        current = date(filters.year, filters.month, 1)
        last = min(today_in_lima(), date(filters.year, filters.month, monthrange(filters.year, filters.month)[1]))
        cumulative = 0
        while current <= last:
            daily_count, daily_cents = per_day.get(current, (0, 0))
            cumulative += daily_cents
            days.append(ExpenseDayTotal(expense_date=current, count=daily_count,
                                       total_amount=money(daily_cents), cumulative_amount=money(cumulative)))
            if current == last:
                break
            current += timedelta(days=1)
        return ExpenseMonthlySummary(
            year=filters.year, month=filters.month, count=count, total_amount=money(total_cents), days=days,
            categories=sorted(categories.values(), key=lambda group: (-group.total_amount, group.category_name)),
            subcategories=sorted(subcategories.values(), key=lambda group: (-group.total_amount, group.category_name, group.subcategory_name or "")),
        )
