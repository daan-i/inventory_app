"""
services/calculation_service.py

All financial calculations for the application.

Rules:
  - Every method is a pure function: inputs in, value out.
  - No database access. No side effects.
  - All monetary inputs and outputs are integers (cents).
  - This is the single source of truth for every financial formula.
    No other layer may perform financial calculations.

Allocation rounding policy (SPECIFICATION.md §6):
  Each allocated value is rounded to the nearest cent. Any remainder
  caused by rounding is assigned entirely to the last item, ensuring
  allocated values always sum exactly to the original amount.
"""

from datetime import date, datetime

from models.domain import Expense, Item, PurchaseBatch, Sale, SaleItem
from models.enums import ItemStatus, SaleStatus


class CalculationService:

    # ------------------------------------------------------------------
    # Allocation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def allocate_batch_costs(
        batch: PurchaseBatch,
        items: list[Item],
    ) -> dict[int, dict[str, int]]:
        """
        Allocate PurchaseBatch shipping_cost and fees across items
        proportionally by each item's purchase_cost.

        Args:
            batch: The purchase batch.
            items: All items belonging to the batch.

        Returns:
            A dict keyed by item.id:
            {
                item_id: {
                    "allocated_shipping": int,  # cents
                    "allocated_fees":     int,  # cents
                }
            }

        If all items have zero purchase_cost the cost is split equally.
        If items list is empty, returns an empty dict.
        """
        if not items:
            return {}

        total_cost = sum(i.purchase_cost for i in items)

        def _allocate(total_amount: int, weights: list[int]) -> list[int]:
            """Proportional allocation with remainder assigned to last item."""
            if total_amount == 0:
                return [0] * len(weights)

            total_weight = sum(weights)
            if total_weight == 0:
                # Equal split when all weights are zero
                base, extra = divmod(total_amount, len(weights))
                result = [base] * len(weights)
                result[-1] += extra
                return result

            allocated = [
                round(total_amount * w / total_weight) for w in weights
            ]
            # Assign remainder to last item
            allocated[-1] += total_amount - sum(allocated)
            return allocated

        weights = [i.purchase_cost for i in items]
        shipping_alloc = _allocate(batch.shipping_cost, weights)
        fees_alloc = _allocate(batch.fees, weights)

        return {
            item.id: {
                "allocated_shipping": shipping_alloc[idx],
                "allocated_fees":     fees_alloc[idx],
            }
            for idx, item in enumerate(items)
        }

    @staticmethod
    def allocate_sale_costs(
        sale: Sale,
        sale_items: list[SaleItem],
    ) -> dict[int, dict[str, int]]:
        """
        Allocate Sale shipping_cost and fees across SaleItems
        proportionally by each SaleItem's allocated_sale_price.

        Args:
            sale:       The sale.
            sale_items: All SaleItem records for the sale.

        Returns:
            A dict keyed by item_id:
            {
                item_id: {
                    "allocated_shipping": int,  # cents
                    "allocated_fees":     int,  # cents
                }
            }
        """
        if not sale_items:
            return {}

        total_price = sum(si.allocated_sale_price for si in sale_items)

        def _allocate(total_amount: int, weights: list[int]) -> list[int]:
            if total_amount == 0:
                return [0] * len(weights)

            total_weight = sum(weights)
            if total_weight == 0:
                base, extra = divmod(total_amount, len(weights))
                result = [base] * len(weights)
                result[-1] += extra
                return result

            allocated = [
                round(total_amount * w / total_weight) for w in weights
            ]
            allocated[-1] += total_amount - sum(allocated)
            return allocated

        weights = [si.allocated_sale_price for si in sale_items]
        shipping_alloc = _allocate(sale.shipping_cost, weights)
        fees_alloc = _allocate(sale.fees, weights)

        return {
            sale_items[idx].item_id: {
                "allocated_shipping": shipping_alloc[idx],
                "allocated_fees":     fees_alloc[idx],
            }
            for idx in range(len(sale_items))
        }

    # ------------------------------------------------------------------
    # Item-level profit
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_item_profit(
        item: Item,
        sale_item: SaleItem,
        sale: Sale,
        sale_items: list[SaleItem],
    ) -> dict[str, int]:
        """
        Calculate gross and net profit for a single sold item.

        Args:
            item:       The Item domain object.
            sale_item:  The SaleItem linking item to its sale.
            sale:       The Sale the item belongs to.
            sale_items: All SaleItems in the same sale (needed for allocation).

        Returns:
            {
                "gross_profit": int,  # cents
                "net_profit":   int,  # cents
            }
        """
        sale_cost_alloc = CalculationService.allocate_sale_costs(sale, sale_items)
        item_alloc = sale_cost_alloc.get(item.id, {"allocated_shipping": 0, "allocated_fees": 0})

        gross_profit = sale_item.allocated_sale_price - item.purchase_cost
        net_profit = (
            sale_item.allocated_sale_price
            - item.purchase_cost
            - item_alloc["allocated_fees"]
            - item_alloc["allocated_shipping"]
        )

        return {"gross_profit": gross_profit, "net_profit": net_profit}

    # ------------------------------------------------------------------
    # Sale-level profit
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_sale_profit(
        sale: Sale,
        sale_items: list[SaleItem],
        items: list[Item],
    ) -> dict[str, int]:
        """
        Calculate gross and net profit for an entire sale.

        Cancelled sales should not be passed to this method.

        Args:
            sale:       The Sale domain object.
            sale_items: All SaleItem records for this sale.
            items:      The Item objects corresponding to those SaleItems.

        Returns:
            {
                "gross_profit": int,  # cents
                "net_profit":   int,  # cents
            }
        """
        total_purchase_cost = sum(i.purchase_cost for i in items)

        gross_profit = sale.final_price - total_purchase_cost
        net_profit = sale.final_price - total_purchase_cost - sale.fees - sale.shipping_cost

        return {"gross_profit": gross_profit, "net_profit": net_profit}

    # ------------------------------------------------------------------
    # Batch-level profit
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_batch_profit(
        batch: PurchaseBatch,
        items: list[Item],
        sale_items: list[SaleItem],
        sales: list[Sale],
    ) -> dict[str, int | float]:
        """
        Calculate profit and total invested for a purchase batch.

        Only SOLD items from COMPLETED sales are included in profit.

        Args:
            batch:      The PurchaseBatch.
            items:      All items belonging to this batch.
            sale_items: All SaleItem records for items in this batch.
            sales:      All Sale objects referenced by those SaleItems.

        Returns:
            {
                "gross_profit":   int,  # cents — sum of item gross profits
                "net_profit":     int,  # cents — sum of item net profits
                "total_invested": int,  # cents — purchase costs + batch overheads
            }
        """
        # Build lookup maps
        sale_map: dict[int, Sale] = {s.id: s for s in sales}
        sale_items_by_sale: dict[int, list[SaleItem]] = {}
        for si in sale_items:
            sale_items_by_sale.setdefault(si.sale_id, []).append(si)

        sale_item_by_item: dict[int, SaleItem] = {si.item_id: si for si in sale_items}

        gross_profit = 0
        net_profit = 0

        for item in items:
            if item.status != ItemStatus.SOLD:
                continue
            si = sale_item_by_item.get(item.id)
            if si is None:
                continue
            sale = sale_map.get(si.sale_id)
            if sale is None or sale.status != SaleStatus.COMPLETED:
                continue

            all_sale_items = sale_items_by_sale.get(si.sale_id, [])
            profits = CalculationService.calculate_item_profit(item, si, sale, all_sale_items)
            gross_profit += profits["gross_profit"]
            net_profit += profits["net_profit"]

        total_invested = sum(i.purchase_cost for i in items) + batch.shipping_cost + batch.fees

        return {
            "gross_profit":   gross_profit,
            "net_profit":     net_profit,
            "total_invested": total_invested,
        }

    # ------------------------------------------------------------------
    # ROI
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_simple_roi(net_profit: int, purchase_cost: int) -> float:
        """
        Simple ROI based on purchase cost only.

        Returns 0.0 if purchase_cost is zero to avoid division by zero.
        """
        if purchase_cost == 0:
            return 0.0
        return (net_profit / purchase_cost) * 100

    @staticmethod
    def calculate_real_roi(net_profit: int, total_invested: int) -> float:
        """
        Real ROI based on total invested (purchase cost + allocated batch costs).

        Returns 0.0 if total_invested is zero to avoid division by zero.
        """
        if total_invested == 0:
            return 0.0
        return (net_profit / total_invested) * 100

    # ------------------------------------------------------------------
    # Inventory value
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_inventory_value(items: list[Item]) -> int:
        """
        Sum of purchase_cost for all AVAILABLE and RESERVED items.

        Returns total in cents.
        """
        return sum(
            i.purchase_cost
            for i in items
            if i.status in (ItemStatus.AVAILABLE, ItemStatus.RESERVED)
        )

    # ------------------------------------------------------------------
    # Holding time
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_average_holding_time(
        items: list[Item],
        sale_items: list[SaleItem],
        sales: list[Sale],
        batches: list[PurchaseBatch],
    ) -> float:
        """
        Average holding time in calendar days for all sold items
        from completed sales.

        Holding time = sale date − batch purchase date.

        Returns 0.0 if no sold items exist.

        Args:
            items:      All items to consider.
            sale_items: SaleItem records linking items to sales.
            sales:      Sale objects (only COMPLETED are counted).
            batches:    PurchaseBatch objects (used for purchase date).
        """
        sale_map: dict[int, Sale] = {s.id: s for s in sales}
        batch_map: dict[int, PurchaseBatch] = {b.id: b for b in batches}
        sale_item_by_item: dict[int, SaleItem] = {si.item_id: si for si in sale_items}

        holding_days: list[int] = []

        for item in items:
            if item.status != ItemStatus.SOLD:
                continue
            si = sale_item_by_item.get(item.id)
            if si is None:
                continue
            sale = sale_map.get(si.sale_id)
            if sale is None or sale.status != SaleStatus.COMPLETED:
                continue
            batch = batch_map.get(item.batch_id)
            if batch is None:
                continue

            purchase_date = date.fromisoformat(batch.date)
            sale_date = date.fromisoformat(sale.date)
            days = (sale_date - purchase_date).days
            if days >= 0:
                holding_days.append(days)

        if not holding_days:
            return 0.0

        return sum(holding_days) / len(holding_days)
