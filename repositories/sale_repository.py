"""
repositories/sale_repository.py

Data access for the sales and sale_items tables.

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
from models.domain import Sale, SaleItem
from models.enums import Platform, PaymentMethod, SaleStatus
from models.errors import RepositoryError

logger = logging.getLogger(__name__)


class SaleRepository:

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_sale(row: sqlite3.Row) -> Sale:
        return Sale(
            id=row["id"],
            date=row["date"],
            platform=Platform(row["platform"]),
            buyer=row["buyer"],
            payment_method=PaymentMethod(row["payment_method"]),
            listing_price=row["listing_price"],
            final_price=row["final_price"],
            shipping_cost=row["shipping_cost"],
            fees=row["fees"],
            notes=row["notes"],
            status=SaleStatus(row["status"]),
            currency=row["currency"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_sale_item(row: sqlite3.Row) -> SaleItem:
        return SaleItem(
            sale_id=row["sale_id"],
            item_id=row["item_id"],
            allocated_sale_price=row["allocated_sale_price"],
            currency=row["currency"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Standard CRUD — Sale
    # ------------------------------------------------------------------

    def create(self, sale: Sale) -> Sale:
        """Insert a new sale. Returns the sale with its assigned id."""
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            row_id = execute_write(
                """
                INSERT INTO sales
                    (date, platform, buyer, payment_method,
                     listing_price, final_price, shipping_cost, fees,
                     notes, status, currency, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sale.date,
                    sale.platform.value,
                    sale.buyer,
                    sale.payment_method.value,
                    sale.listing_price,
                    sale.final_price,
                    sale.shipping_cost,
                    sale.fees,
                    sale.notes,
                    sale.status.value,
                    sale.currency,
                    now,
                    now,
                ),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to create sale: {e}") from e

        sale.id = row_id
        sale.created_at = now
        sale.updated_at = now
        logger.debug("Sale created: id=%d", row_id)
        return sale

    def get_by_id(self, sale_id: int) -> Sale | None:
        """Return a single sale by primary key, or None if not found."""
        try:
            rows = execute_query("SELECT * FROM sales WHERE id = ?", (sale_id,))
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch sale {sale_id}: {e}") from e

        return self._row_to_sale(rows[0]) if rows else None

    def get_all(self) -> list[Sale]:
        """Return all sales ordered by date descending."""
        try:
            rows = execute_query("SELECT * FROM sales ORDER BY date DESC")
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch sales: {e}") from e

        return [self._row_to_sale(r) for r in rows]

    def update(self, sale: Sale) -> Sale:
        """Persist changes to an existing sale. Refreshes updated_at."""
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            execute_write(
                """
                UPDATE sales
                SET date           = ?,
                    platform       = ?,
                    buyer          = ?,
                    payment_method = ?,
                    listing_price  = ?,
                    final_price    = ?,
                    shipping_cost  = ?,
                    fees           = ?,
                    notes          = ?,
                    status         = ?,
                    currency       = ?,
                    updated_at     = ?
                WHERE id = ?
                """,
                (
                    sale.date,
                    sale.platform.value,
                    sale.buyer,
                    sale.payment_method.value,
                    sale.listing_price,
                    sale.final_price,
                    sale.shipping_cost,
                    sale.fees,
                    sale.notes,
                    sale.status.value,
                    sale.currency,
                    now,
                    sale.id,
                ),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to update sale {sale.id}: {e}") from e

        sale.updated_at = now
        logger.debug("Sale updated: id=%d", sale.id)
        return sale

    # ------------------------------------------------------------------
    # SaleItem operations
    # ------------------------------------------------------------------

    def create_sale_item(self, sale_item: SaleItem) -> SaleItem:
        """Insert a sale_item record linking a sale to an item."""
        now = datetime.now().strftime(DATETIME_FORMAT)
        try:
            execute_write(
                """
                INSERT INTO sale_items
                    (sale_id, item_id, allocated_sale_price, currency,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    sale_item.sale_id,
                    sale_item.item_id,
                    sale_item.allocated_sale_price,
                    sale_item.currency,
                    now,
                    now,
                ),
            )
        except sqlite3.Error as e:
            raise RepositoryError(
                f"Failed to create sale_item (sale={sale_item.sale_id}, "
                f"item={sale_item.item_id}): {e}"
            ) from e

        sale_item.created_at = now
        sale_item.updated_at = now
        logger.debug(
            "SaleItem created: sale_id=%d item_id=%d",
            sale_item.sale_id,
            sale_item.item_id,
        )
        return sale_item

    def get_items_for_sale(self, sale_id: int) -> list[SaleItem]:
        """Return all SaleItem records for a given sale."""
        try:
            rows = execute_query(
                "SELECT * FROM sale_items WHERE sale_id = ?", (sale_id,)
            )
        except sqlite3.Error as e:
            raise RepositoryError(
                f"Failed to fetch sale items for sale {sale_id}: {e}"
            ) from e

        return [self._row_to_sale_item(r) for r in rows]

    # ------------------------------------------------------------------
    # Entity-specific queries
    # ------------------------------------------------------------------

    def get_by_status(self, status: SaleStatus) -> list[Sale]:
        """Return all sales with the given status."""
        try:
            rows = execute_query(
                "SELECT * FROM sales WHERE status = ? ORDER BY date DESC",
                (status.value,),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch sales by status: {e}") from e

        return [self._row_to_sale(r) for r in rows]

    def get_by_date_range(self, start: str, end: str) -> list[Sale]:
        """
        Return all sales with a date between start and end (inclusive).

        Args:
            start: ISO 8601 date string, e.g. '2024-01-01'
            end:   ISO 8601 date string, e.g. '2024-12-31'
        """
        try:
            rows = execute_query(
                """
                SELECT * FROM sales
                WHERE date BETWEEN ? AND ?
                ORDER BY date DESC
                """,
                (start, end),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch sales by date range: {e}") from e

        return [self._row_to_sale(r) for r in rows]

    def get_by_platform(self, platform: Platform) -> list[Sale]:
        """Return all sales on a given platform."""
        try:
            rows = execute_query(
                "SELECT * FROM sales WHERE platform = ? ORDER BY date DESC",
                (platform.value,),
            )
        except sqlite3.Error as e:
            raise RepositoryError(f"Failed to fetch sales by platform: {e}") from e

        return [self._row_to_sale(r) for r in rows]
