"""
repositories/expense_repository.py

Data access for the expenses table.

Rules:
  - No business logic.
  - Returns domain model objects only — never raw rows or dicts.
  - All SQL lives here. Services never execute SQL directly.
  - sqlite3 errors are caught and re-raised as RepositoryError.
"""

import logging
import sqlite3
from datetime import datetime

from config.settings import DATETIME_FORMAT
from database.db import execute_query, execute_write
from models.domain import Expense
from models.enums import ExpenseCategory, PaymentMethod
from models.errors import RepositoryError

logger = logging.getLogger(__name__)


class ExpenseRepository:

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_expense(row: sqlite3.Row) -> Expense:
        return Expense(
            id=row["id"],
            date=row["date"],
            category=ExpenseCategory(row["category"]),
            description=row["description"],
            amount=row["amount"],
            payment_method=PaymentMethod(row["payment_method"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Standard CRUD
    # ------------------------------------------------------------------

    def create(self, expense: Expense) -> Expense:
        """Insert a new expense. Returns the expense with its assigned id."""
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            row_id = execute_write(
                """
                INSERT INTO expenses
                    (date, category, description, amount,
                     payment_method, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    expense.date,
                    expense.category.value,
                    expense.description,
                    expense.amount,
                    expense.payment_method.value,
                    now,
                    now,
                ),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to create expense: {e}") from e

        expense.id = row_id
        expense.created_at = now
        expense.updated_at = now
        logger.debug("Expense created: id=%d", row_id)
        return expense

    def get_by_id(self, expense_id: int) -> Expense | None:
        """Return a single expense by primary key, or None if not found."""
        try:
            rows = execute_query(
                "SELECT * FROM expenses WHERE id = ?", (expense_id,)
            )
        except sqlite3.Error as e:
            raise RepositoryError(
                f"Failed to fetch expense {expense_id}: {e}"
            ) from e

        return self._row_to_expense(rows[0]) if rows else None

    def get_all(self) -> list[Expense]:
        """Return all expenses ordered by date descending."""
        try:
            rows = execute_query("SELECT * FROM expenses ORDER BY date DESC")
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch expenses: {e}") from e

        return [self._row_to_expense(r) for r in rows]

    def update(self, expense: Expense) -> Expense:
        """Persist changes to an existing expense. Refreshes updated_at."""
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            execute_write(
                """
                UPDATE expenses
                SET date           = ?,
                    category       = ?,
                    description    = ?,
                    amount         = ?,
                    payment_method = ?,
                    updated_at     = ?
                WHERE id = ?
                """,
                (
                    expense.date,
                    expense.category.value,
                    expense.description,
                    expense.amount,
                    expense.payment_method.value,
                    now,
                    expense.id,
                ),
            )
        except sqlite3.Error as e:
            raise RepositoryError(
                f"Failed to update expense {expense.id}: {e}"
            ) from e

        expense.updated_at = now
        logger.debug("Expense updated: id=%d", expense.id)
        return expense

    def delete(self, expense_id: int) -> bool:
        """Delete an expense by primary key. Returns True if deleted."""
        try:
            execute_write("DELETE FROM expenses WHERE id = ?", (expense_id,))
        except sqlite3.Error as e:
            raise RepositoryError(
                f"Failed to delete expense {expense_id}: {e}"
            ) from e

        logger.debug("Expense deleted: id=%d", expense_id)
        return True

    # ------------------------------------------------------------------
    # Entity-specific queries
    # ------------------------------------------------------------------

    def get_by_category(self, category: ExpenseCategory) -> list[Expense]:
        """Return all expenses in a given category."""
        try:
            rows = execute_query(
                "SELECT * FROM expenses WHERE category = ? ORDER BY date DESC",
                (category.value,),
            )
        except sqlite3.Error as e:
            raise RepositoryError(
                f"Failed to fetch expenses by category: {e}"
            ) from e

        return [self._row_to_expense(r) for r in rows]

    def get_by_date_range(self, start: str, end: str) -> list[Expense]:
        """
        Return all expenses with a date between start and end (inclusive).

        Args:
            start: ISO 8601 date string, e.g. '2024-01-01'
            end:   ISO 8601 date string, e.g. '2024-12-31'
        """
        try:
            rows = execute_query(
                """
                SELECT * FROM expenses
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
                """,
                (start, end),
            )
        except sqlite3.Error as e:
            raise RepositoryError(
                f"Failed to fetch expenses by date range: {e}"
            ) from e

        return [self._row_to_expense(r) for r in rows]
