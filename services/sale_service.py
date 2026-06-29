"""
services/sale_service.py

Business logic for sale operations.

Rules:
  - No direct database access. Calls repositories only.
  - create_sale and cancel_sale are fully atomic via execute_transaction.
  - Sales are never hard-deleted. Use cancel_sale instead.
  - Business rule violations raise BusinessRuleError.
"""

import logging

from database.db import execute_transaction
from models.domain import Item, Sale, SaleItem
from models.enums import ItemStatus, SaleStatus
from models.errors import BusinessRuleError
from repositories.item_repository import ItemRepository
from repositories.sale_repository import SaleRepository

logger = logging.getLogger(__name__)

_SELLABLE_STATUSES = {ItemStatus.AVAILABLE, ItemStatus.RESERVED}


class SaleService:

    def __init__(
        self,
        sale_repo: SaleRepository,
        item_repo: ItemRepository,
    ) -> None:
        self._sale_repo = sale_repo
        self._item_repo = item_repo

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_sale(
        self,
        sale: Sale,
        selected_items: list[Item],
        allocated_prices: dict[int, int],
    ) -> Sale:
        """
        Create a sale, its SaleItems, and mark all items as SOLD — atomically.

        Args:
            sale:             Sale with id=None (assigned by DB).
            selected_items:   The Item objects being sold.
            allocated_prices: Dict mapping item.id → allocated_sale_price (cents).
                              All items must be present. Prices should sum to
                              sale.final_price, but this is not enforced here —
                              the GUI is responsible for allocation UI.

        Returns:
            The created Sale with its assigned id.

        Raises:
            BusinessRuleError: If no items provided, or any item is not
                               AVAILABLE or RESERVED.
            RepositoryError:   If a database operation fails.
        """
        if not selected_items:
            raise BusinessRuleError("A sale must contain at least one item.")

        # Re-fetch items from the DB to get their current status.
        # Never trust in-memory objects for business rule validation —
        # the caller may hold stale references.
        item_ids = [i.id for i in selected_items]
        fresh_items = [self._item_repo.get_by_id(iid) for iid in item_ids]
        fresh_items = [i for i in fresh_items if i is not None]

        unsellable = [
            i for i in fresh_items if i.status not in _SELLABLE_STATUSES
        ]
        if unsellable:
            names = ", ".join(i.name for i in unsellable)
            raise BusinessRuleError(
                f"The following item(s) cannot be sold because their status "
                f"is not Available or Reserved: {names}."
            )

        created_sale: Sale | None = None

        def operations(conn):
            nonlocal created_sale
            from datetime import datetime
            from config.settings import DATETIME_FORMAT

            now = datetime.now().strftime(DATETIME_FORMAT)

            # Insert sale
            cursor = conn.execute(
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
                    SaleStatus.COMPLETED.value,
                    sale.currency,
                    now,
                    now,
                ),
            )
            sale_id = cursor.lastrowid
            sale.id = sale_id
            sale.status = SaleStatus.COMPLETED
            sale.created_at = now
            sale.updated_at = now

            # Insert SaleItems and mark items SOLD
            for item in selected_items:
                allocated_price = allocated_prices.get(item.id, 0)
                conn.execute(
                    """
                    INSERT INTO sale_items
                        (sale_id, item_id, allocated_sale_price, currency,
                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (sale_id, item.id, allocated_price, sale.currency, now, now),
                )
                conn.execute(
                    "UPDATE items SET status = ?, updated_at = ? WHERE id = ?",
                    (ItemStatus.SOLD.value, now, item.id),
                )

            created_sale = sale

        execute_transaction(operations)
        logger.info(
            "Sale created: id=%d items=%d total=%d cents",
            created_sale.id,
            len(selected_items),
            created_sale.final_price,
        )
        return created_sale

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_sale(self, sale_id: int) -> Sale:
        """
        Return a sale by id.

        Raises:
            BusinessRuleError: If the sale does not exist.
        """
        sale = self._sale_repo.get_by_id(sale_id)
        if sale is None:
            raise BusinessRuleError(f"Sale {sale_id} not found.")
        return sale

    def get_all_sales(self) -> list[Sale]:
        """Return all sales, most recent first."""
        return self._sale_repo.get_all()

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_sale(self, sale: Sale) -> Sale:
        """
        Persist changes to a sale's metadata (date, platform, notes, etc.).

        Does not change sale status or item statuses. Use cancel_sale for that.

        Raises:
            BusinessRuleError: If the sale does not exist.
            RepositoryError:   If a database operation fails.
        """
        existing = self._sale_repo.get_by_id(sale.id)
        if existing is None:
            raise BusinessRuleError(f"Sale {sale.id} not found.")
        return self._sale_repo.update(sale)

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def cancel_sale(self, sale_id: int) -> Sale:
        """
        Cancel a completed sale and restore all item statuses to AVAILABLE.

        Sales are never hard-deleted. Cancelling preserves the historical
        record while reversing the inventory effect.

        Args:
            sale_id: The id of the sale to cancel.

        Returns:
            The updated Sale with status CANCELLED.

        Raises:
            BusinessRuleError: If the sale does not exist, or is already
                               CANCELLED.
            RepositoryError:   If a database operation fails.
        """
        sale = self._sale_repo.get_by_id(sale_id)
        if sale is None:
            raise BusinessRuleError(f"Sale {sale_id} not found.")

        if sale.status == SaleStatus.CANCELLED:
            raise BusinessRuleError(f"Sale {sale_id} is already cancelled.")

        sale_items = self._sale_repo.get_items_for_sale(sale_id)
        item_ids = [si.item_id for si in sale_items]

        def operations(conn):
            from datetime import datetime
            from config.settings import DATETIME_FORMAT

            now = datetime.now().strftime(DATETIME_FORMAT)

            conn.execute(
                "UPDATE sales SET status = ?, updated_at = ? WHERE id = ?",
                (SaleStatus.CANCELLED.value, now, sale_id),
            )
            for item_id in item_ids:
                conn.execute(
                    "UPDATE items SET status = ?, updated_at = ? WHERE id = ?",
                    (ItemStatus.AVAILABLE.value, now, item_id),
                )

        execute_transaction(operations)

        sale.status = SaleStatus.CANCELLED
        logger.info(
            "Sale cancelled: id=%d items_restored=%d", sale_id, len(item_ids)
        )
        return sale
