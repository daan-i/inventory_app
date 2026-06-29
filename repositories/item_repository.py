"""
repositories/item_repository.py

Data access for the items table.

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
from models.domain import Item
from models.enums import Category, Condition, ItemStatus, Platform, PaymentMethod
from models.errors import RepositoryError

logger = logging.getLogger(__name__)


class ItemRepository:

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> Item:
        return Item(
            id=row["id"],
            batch_id=row["batch_id"],
            category=Category(row["category"]),
            name=row["name"],
            description=row["description"],
            condition=Condition(row["condition"]),
            purchase_cost=row["purchase_cost"],
            status=ItemStatus(row["status"]),
            currency=row["currency"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Standard CRUD
    # ------------------------------------------------------------------

    def create(self, item: Item) -> Item:
        """Insert a new item. Returns the item with its assigned id."""
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            row_id = execute_write(
                """
                INSERT INTO items
                    (batch_id, category, name, description,
                     condition, purchase_cost, status, currency,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.batch_id,
                    item.category.value,
                    item.name,
                    item.description,
                    item.condition.value,
                    item.purchase_cost,
                    item.status.value,
                    item.currency,
                    now,
                    now,
                ),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to create item '{item.name}': {e}") from e

        item.id = row_id
        item.created_at = now
        item.updated_at = now
        logger.debug("Item created: id=%d name=%s", row_id, item.name)
        return item

    def get_by_id(self, item_id: int) -> Item | None:
        """Return a single item by primary key, or None if not found."""
        try:
            rows = execute_query("SELECT * FROM items WHERE id = ?", (item_id,))
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch item {item_id}: {e}") from e

        return self._row_to_item(rows[0]) if rows else None

    def get_all(self) -> list[Item]:
        """Return all items ordered by creation date descending."""
        try:
            rows = execute_query("SELECT * FROM items ORDER BY created_at DESC")
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch items: {e}") from e

        return [self._row_to_item(r) for r in rows]

    def update(self, item: Item) -> Item:
        """Persist changes to an existing item. Refreshes updated_at."""
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            execute_write(
                """
                UPDATE items
                SET batch_id      = ?,
                    category      = ?,
                    name          = ?,
                    description   = ?,
                    condition     = ?,
                    purchase_cost = ?,
                    status        = ?,
                    currency      = ?,
                    updated_at    = ?
                WHERE id = ?
                """,
                (
                    item.batch_id,
                    item.category.value,
                    item.name,
                    item.description,
                    item.condition.value,
                    item.purchase_cost,
                    item.status.value,
                    item.currency,
                    now,
                    item.id,
                ),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to update item {item.id}: {e}") from e

        item.updated_at = now
        logger.debug("Item updated: id=%d", item.id)
        return item

    def delete(self, item_id: int) -> bool:
        """Delete an item by primary key. Returns True if deleted."""
        try:
            execute_write("DELETE FROM items WHERE id = ?", (item_id,))
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to delete item {item_id}: {e}") from e

        logger.debug("Item deleted: id=%d", item_id)
        return True

    # ------------------------------------------------------------------
    # Entity-specific queries
    # ------------------------------------------------------------------

    def get_by_batch(self, batch_id: int) -> list[Item]:
        """Return all items belonging to a given purchase batch."""
        try:
            rows = execute_query(
                "SELECT * FROM items WHERE batch_id = ? ORDER BY created_at ASC",
                (batch_id,),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch items for batch {batch_id}: {e}") from e

        return [self._row_to_item(r) for r in rows]

    def get_by_status(self, status: ItemStatus) -> list[Item]:
        """Return all items with the given status."""
        try:
            rows = execute_query(
                "SELECT * FROM items WHERE status = ? ORDER BY updated_at DESC",
                (status.value,),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch items by status: {e}") from e

        return [self._row_to_item(r) for r in rows]

    def get_by_category(self, category: Category) -> list[Item]:
        """Return all items in a given category."""
        try:
            rows = execute_query(
                "SELECT * FROM items WHERE category = ? ORDER BY created_at DESC",
                (category.value,),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch items by category: {e}") from e

        return [self._row_to_item(r) for r in rows]

    def update_status(self, item_id: int, status: ItemStatus) -> bool:
        """
        Update only the status field of an item. Refreshes updated_at.

        Returns True if the row was updated.
        """
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            execute_write(
                "UPDATE items SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, item_id),
            )
        except sqlite3.Error as e:
            raise RepositoryError(
                f"Failed to update status for item {item_id}: {e}"
            ) from e

        logger.debug("Item status updated: id=%d status=%s", item_id, status.value)
        return True
