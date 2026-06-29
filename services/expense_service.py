"""
services/expense_service.py

Business logic for expense operations.

Rules:
  - No direct database access. Calls repositories only.
  - Business rule violations raise BusinessRuleError.
"""

import logging

from models.domain import Expense
from models.enums import ExpenseCategory
from models.errors import BusinessRuleError
from repositories.expense_repository import ExpenseRepository

logger = logging.getLogger(__name__)


class ExpenseService:

    def __init__(self, expense_repo: ExpenseRepository) -> None:
        self._expense_repo = expense_repo

    def create_expense(self, expense: Expense) -> Expense:
        """
        Create a new expense.

        Raises:
            BusinessRuleError: If the amount is negative.
            RepositoryError:   If a database operation fails.
        """
        if expense.amount < 0:
            raise BusinessRuleError("Expense amount cannot be negative.")

        created = self._expense_repo.create(expense)
        logger.info("Expense created: id=%d amount=%d", created.id, created.amount)
        return created

    def update_expense(self, expense: Expense) -> Expense:
        """
        Persist changes to an expense.

        Raises:
            BusinessRuleError: If the expense does not exist or amount is negative.
            RepositoryError:   If a database operation fails.
        """
        if expense.amount < 0:
            raise BusinessRuleError("Expense amount cannot be negative.")

        existing = self._expense_repo.get_by_id(expense.id)
        if existing is None:
            raise BusinessRuleError(f"Expense {expense.id} not found.")

        updated = self._expense_repo.update(expense)
        logger.info("Expense updated: id=%d", updated.id)
        return updated

    def delete_expense(self, expense_id: int) -> bool:
        """
        Delete an expense by id.

        Raises:
            BusinessRuleError: If the expense does not exist.
            RepositoryError:   If a database operation fails.
        """
        existing = self._expense_repo.get_by_id(expense_id)
        if existing is None:
            raise BusinessRuleError(f"Expense {expense_id} not found.")

        result = self._expense_repo.delete(expense_id)
        logger.info("Expense deleted: id=%d", expense_id)
        return result

    def get_all_expenses(self) -> list[Expense]:
        """Return all expenses, most recent first."""
        return self._expense_repo.get_all()

    def get_expenses_by_category(self, category: ExpenseCategory) -> list[Expense]:
        """Return all expenses in the given category."""
        return self._expense_repo.get_by_category(category)
