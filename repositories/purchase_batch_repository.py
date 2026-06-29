"""
repositories/purchase_batch_repository.py

Data access for the purchase_batches table.

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
from models.domain import PurchaseBatch
from models.enums import Platform, PaymentMethod
from models.errors import RepositoryError

logger = logging.getLogger(__name__)


class PurchaseBatchRepository:

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_batch(row: sqlite3.Row) -> PurchaseBatch:
        return PurchaseBatch(
            id=row["id"],
            date=row["date"],
            seller=row["seller"],
            platform=Platform(row["platform"]),
            payment_method=PaymentMethod(row["payment_method"]),
            shipping_cost=row["shipping_cost"],
            fees=row["fees"],
            notes=row["notes"],
            currency=row["currency"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Standard CRUD
    # ------------------------------------------------------------------

    def create(self, batch: PurchaseBatch) -> PurchaseBatch:
        """Insert a new purchase batch. Returns the batch with its assigned id."""
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            row_id = execute_write(
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
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to create purchase batch: {e}") from e

        batch.id = row_id
        batch.created_at = now
        batch.updated_at = now
        logger.debug("PurchaseBatch created: id=%d", row_id)
        return batch

    def get_by_id(self, batch_id: int) -> PurchaseBatch | None:
        """Return a single batch by primary key, or None if not found."""
        try:
            rows = execute_query(
                "SELECT * FROM purchase_batches WHERE id = ?", (batch_id,)
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch purchase batch {batch_id}: {e}") from e

        return self._row_to_batch(rows[0]) if rows else None

    def get_all(self) -> list[PurchaseBatch]:
        """Return all purchase batches ordered by date descending."""
        try:
            rows = execute_query(
                "SELECT * FROM purchase_batches ORDER BY date DESC"
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch purchase batches: {e}") from e

        return [self._row_to_batch(r) for r in rows]

    def update(self, batch: PurchaseBatch) -> PurchaseBatch:
        """Persist changes to an existing batch. Refreshes updated_at."""
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            execute_write(
                """
                UPDATE purchase_batches
                SET date           = ?,
                    seller         = ?,
                    platform       = ?,
                    payment_method = ?,
                    shipping_cost  = ?,
                    fees           = ?,
                    notes          = ?,
                    currency       = ?,
                    updated_at     = ?
                WHERE id = ?
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
                    batch.id,
                ),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to update purchase batch {batch.id}: {e}") from e

        batch.updated_at = now
        logger.debug("PurchaseBatch updated: id=%d", batch.id)
        return batch

    def delete(self, batch_id: int) -> bool:
        """
        Delete a batch by primary key.

        Returns True if a row was deleted, False if the id did not exist.
        Note: the service layer is responsible for validating that no
        items in the batch are SOLD before calling this method.
        """
        try:
            execute_write(
                "DELETE FROM purchase_batches WHERE id = ?", (batch_id,)
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to delete purchase batch {batch_id}: {e}") from e

        logger.debug("PurchaseBatch deleted: id=%d", batch_id)
        return True

    # ------------------------------------------------------------------
    # Entity-specific queries
    # ------------------------------------------------------------------

    def get_by_platform(self, platform: Platform) -> list[PurchaseBatch]:
        """Return all batches purchased on a given platform."""
        try:
            rows = execute_query(
                "SELECT * FROM purchase_batches WHERE platform = ? ORDER BY date DESC",
                (platform.value,),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch batches by platform: {e}") from e

        return [self._row_to_batch(r) for r in rows]

    def get_by_date_range(self, start: str, end: str) -> list[PurchaseBatch]:
        """
        Return all batches with a date between start and end (inclusive).

        Args:
            start: ISO 8601 date string, e.g. '2024-01-01'
            end:   ISO 8601 date string, e.g. '2024-12-31'
        """
        try:
            rows = execute_query(
                """
                SELECT * FROM purchase_batches
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
                """,
                (start, end),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch batches by date range: {e}") from e

        return [self._row_to_batch(r) for r in rows]
