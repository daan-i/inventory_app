"""
services/inventory_service.py

Business logic for inventory queries and item status management.

Rules:
  - No direct database access. Calls repositories only.
  - Status transition validation lives here, not in the repository.
  - Business rule violations raise BusinessRuleError.
"""

import logging

from models.domain import Item
from models.enums import ItemStatus
from models.errors import BusinessRuleError
from repositories.item_repository import ItemRepository

logger = logging.getLogger(__name__)

# Valid manual status transitions (sale-driven transitions handled by SaleService)
_ALLOWED_TRANSITIONS: dict[ItemStatus, set[ItemStatus]] = {
    ItemStatus.PURCHASED:  {ItemStatus.IN_TRANSIT, ItemStatus.AVAILABLE},
    ItemStatus.IN_TRANSIT: {ItemStatus.AVAILABLE},
    ItemStatus.AVAILABLE:  {ItemStatus.RESERVED, ItemStatus.DISCARDED},
    ItemStatus.RESERVED:   {ItemStatus.AVAILABLE},
    ItemStatus.SOLD:       {ItemStatus.RETURNED},
    ItemStatus.RETURNED:   {ItemStatus.AVAILABLE, ItemStatus.DISCARDED},
    ItemStatus.DISCARDED:  set(),
}


class InventoryService:

    def __init__(self, item_repo: ItemRepository) -> None:
        self._item_repo = item_repo

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_item(self, item_id: int) -> Item:
        """
        Return a single item by id.

        Raises:
            BusinessRuleError: If the item does not exist.
        """
        item = self._item_repo.get_by_id(item_id)
        if item is None:
            raise BusinessRuleError(f"Item {item_id} not found.")
        return item

    def get_available_items(self) -> list[Item]:
        """Return all items with status AVAILABLE."""
        return self._item_repo.get_by_status(ItemStatus.AVAILABLE)

    def get_items_by_status(self, status: ItemStatus) -> list[Item]:
        """Return all items with the given status."""
        return self._item_repo.get_by_status(status)

    def search_inventory(self, query: str) -> list[Item]:
        """
        Search items across name, description, and category fields.

        The search is case-insensitive and matches partial strings.

        Args:
            query: The search string.

        Returns:
            All items where name, description, or category contains the query.
        """
        if not query or not query.strip():
            return self._item_repo.get_all()

        all_items = self._item_repo.get_all()
        q = query.strip().lower()

        return [
            item for item in all_items
            if q in item.name.lower()
            or q in item.category.value.lower()
            or (item.description and q in item.description.lower())
        ]

    # ------------------------------------------------------------------
    # Status management
    # ------------------------------------------------------------------

    def update_item_status(self, item_id: int, new_status: ItemStatus) -> Item:
        """
        Update the status of an item, validating the transition is permitted.

        Args:
            item_id:    The id of the item to update.
            new_status: The target status.

        Returns:
            The updated Item.

        Raises:
            BusinessRuleError: If the item does not exist, or if the
                               transition is not permitted.
            RepositoryError:   If a database operation fails.
        """
        item = self._item_repo.get_by_id(item_id)
        if item is None:
            raise BusinessRuleError(f"Item {item_id} not found.")

        allowed = _ALLOWED_TRANSITIONS.get(item.status, set())
        if new_status not in allowed:
            raise BusinessRuleError(
                f"Cannot change item status from '{item.status.value}' "
                f"to '{new_status.value}'."
            )

        self._item_repo.update_status(item_id, new_status)
        item.status = new_status

        logger.info(
            "Item status updated: id=%d %s → %s",
            item_id,
            item.status.value,
            new_status.value,
        )
        return item
