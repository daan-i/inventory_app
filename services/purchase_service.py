"""
services/purchase_service.py

Business logic for purchase batch operations.

Rules:
  - No direct database access. Calls repositories only.
  - All multi-step writes use execute_transaction for atomicity.
  - Business rule violations raise BusinessRuleError.
"""

import logging

from database.db import execute_transaction
from models.domain import Item, PurchaseBatch
from models.enums import ItemStatus, SaleStatus
from models.errors import BusinessRuleError, RepositoryError
from repositories.item_repository import ItemRepository
from repositories.purchase_batch_repository import PurchaseBatchRepository

logger = logging.getLogger(__name__)


class PurchaseService:

    def __init__(
        self,
        batch_repo: PurchaseBatchRepository,
        item_repo: ItemRepository,
    ) -> None:
        self._batch_repo = batch_repo
        self._item_repo = item_repo

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_batch(
        self,
        batch: PurchaseBatch,
        items: list[Item],
    ) -> PurchaseBatch:
        """
        Create a purchase batch and all its items in one atomic transaction.

        Items are created with status AVAILABLE unless a different status
        is explicitly set on the Item object passed in.

        Args:
            batch: PurchaseBatch with id=None (assigned by DB).
            items: List of Item objects with id=None and batch_id unset.

        Returns:
            The created PurchaseBatch with its assigned id.

        Raises:
            BusinessRuleError: If no items are provided.
            RepositoryError:   If a database operation fails.
        """
        if not items:
            raise BusinessRuleError("A purchase batch must contain at least one item.")

        created_batch: PurchaseBatch | None = None

        def operations(conn):
            nonlocal created_batch
            from datetime import datetime
            from config.settings import DATETIME_FORMAT

            now = datetime.now().strftime(DATETIME_FORMAT)

            # Insert batch
            cursor = conn.execute(
                """
                INSERT INTO purchase_batches
                    (date, seller, platform, payment_method,
                     shipping_cost, fees, notes, currency,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch.date,
                    batch.seller,
                    batch.platform.value,
                    batch.payment_method.value,
                    batch.shipping_cost,
                    batch.fees,
                    batch.notes,
                    batch.currency,
                    now,
                    now,
                ),
            )
            batch_id = cursor.lastrowid
            batch.id = batch_id
            batch.created_at = now
            batch.updated_at = now

            # Insert items
            for item in items:
                item.batch_id = batch_id
                if item.status is None:
                    item.status = ItemStatus.AVAILABLE
                conn.execute(
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

            created_batch = batch

        execute_transaction(operations)
        logger.info(
            "PurchaseBatch created: id=%d items=%d", created_batch.id, len(items)
        )
        return created_batch

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_batch(self, batch_id: int) -> PurchaseBatch:
        """
        Return a purchase batch by id.

        Raises:
            BusinessRuleError: If the batch does not exist.
        """
        batch = self._batch_repo.get_by_id(batch_id)
        if batch is None:
            raise BusinessRuleError(f"Purchase batch {batch_id} not found.")
        return batch

    def get_all_batches(self) -> list[PurchaseBatch]:
        """Return all purchase batches, most recent first."""
        return self._batch_repo.get_all()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_batch(self, batch: PurchaseBatch) -> PurchaseBatch:
        """
        Persist changes to a purchase batch.

        Raises:
            BusinessRuleError: If the batch does not exist.
            RepositoryError:   If a database operation fails.
        """
        existing = self._batch_repo.get_by_id(batch.id)
        if existing is None:
            raise BusinessRuleError(f"Purchase batch {batch.id} not found.")
        return self._batch_repo.update(batch)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_batch(self, batch_id: int) -> bool:
        """
        Delete a purchase batch and all its items.

        Only permitted if none of the batch's items have status SOLD.
        Deletion is atomic: items are deleted before the batch.

        Args:
            batch_id: The id of the batch to delete.

        Returns:
            True if deleted successfully.

        Raises:
            BusinessRuleError: If the batch does not exist, or if any
                               item in the batch is SOLD.
            RepositoryError:   If a database operation fails.
        """
        batch = self._batch_repo.get_by_id(batch_id)
        if batch is None:
            raise BusinessRuleError(f"Purchase batch {batch_id} not found.")

        items = self._item_repo.get_by_batch(batch_id)
        sold = [i for i in items if i.status == ItemStatus.SOLD]
        if sold:
            raise BusinessRuleError(
                f"Cannot delete batch {batch_id}: "
                f"{len(sold)} item(s) have already been sold."
            )

        def operations(conn):
            conn.execute("DELETE FROM items WHERE batch_id = ?", (batch_id,))
            conn.execute("DELETE FROM purchase_batches WHERE id = ?", (batch_id,))

        execute_transaction(operations)
        logger.info("PurchaseBatch deleted: id=%d", batch_id)
        return True
