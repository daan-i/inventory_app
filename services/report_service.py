"""
services/report_service.py

Aggregated reporting across all entities.

Rules:
  - No direct database access. Calls repositories and CalculationService only.
  - Cancelled sales are excluded from all profit calculations.
  - Excel export uses openpyxl.
"""

import logging
from collections import defaultdict

from models.domain import Expense, Item, PurchaseBatch, Sale, SaleItem
from models.enums import ItemStatus, SaleStatus
from repositories.expense_repository import ExpenseRepository
from repositories.item_repository import ItemRepository
from repositories.purchase_batch_repository import PurchaseBatchRepository
from repositories.sale_repository import SaleRepository
from services.calculation_service import CalculationService

logger = logging.getLogger(__name__)


class ReportService:

    def __init__(
        self,
        batch_repo: PurchaseBatchRepository,
        item_repo: ItemRepository,
        sale_repo: SaleRepository,
        expense_repo: ExpenseRepository,
    ) -> None:
        self._batch_repo = batch_repo
        self._item_repo = item_repo
        self._sale_repo = sale_repo
        self._expense_repo = expense_repo

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    def get_inventory_report(self) -> list[Item]:
        """Return all items currently in inventory (AVAILABLE or RESERVED)."""
        all_items = self._item_repo.get_all()
        return [
            i for i in all_items
            if i.status in (ItemStatus.AVAILABLE, ItemStatus.RESERVED)
        ]

    def get_inventory_value(self) -> int:
        """Return total inventory value in cents."""
        items = self._item_repo.get_all()
        return CalculationService.calculate_inventory_value(items)

    # ------------------------------------------------------------------
    # Purchase history
    # ------------------------------------------------------------------

    def get_purchase_history(
        self,
        start: str | None = None,
        end: str | None = None,
    ) -> list[PurchaseBatch]:
        """
        Return purchase batches, optionally filtered by date range.

        Args:
            start: ISO 8601 date string or None for no lower bound.
            end:   ISO 8601 date string or None for no upper bound.
        """
        if start and end:
            return self._batch_repo.get_by_date_range(start, end)
        return self._batch_repo.get_all()

    # ------------------------------------------------------------------
    # Sales history
    # ------------------------------------------------------------------

    def get_sales_history(
        self,
        start: str | None = None,
        end: str | None = None,
        include_cancelled: bool = False,
    ) -> list[Sale]:
        """
        Return sales, optionally filtered by date range.

        Args:
            start:              ISO 8601 date string or None.
            end:                ISO 8601 date string or None.
            include_cancelled:  If False (default), only COMPLETED sales returned.
        """
        if start and end:
            sales = self._sale_repo.get_by_date_range(start, end)
        else:
            sales = self._sale_repo.get_all()

        if not include_cancelled:
            sales = [s for s in sales if s.status == SaleStatus.COMPLETED]

        return sales

    # ------------------------------------------------------------------
    # Monthly profit
    # ------------------------------------------------------------------

    def get_monthly_profit(self, year: int, month: int) -> dict:
        """
        Return profit summary for a given month.

        Only COMPLETED sales are included.

        Returns:
            {
                "year":         int,
                "month":        int,
                "gross_profit": int,  # cents
                "net_profit":   int,  # cents
                "sale_count":   int,
            }
        """
        start = f"{year:04d}-{month:02d}-01"
        # Last day: use next month minus one day
        if month == 12:
            end = f"{year + 1:04d}-01-01"
        else:
            end = f"{year:04d}-{month + 1:02d}-01"

        sales = self._sale_repo.get_by_date_range(start, end[:-3] + "31")
        completed = [s for s in sales if s.status == SaleStatus.COMPLETED]

        gross_total = 0
        net_total = 0

        for sale in completed:
            sale_items = self._sale_repo.get_items_for_sale(sale.id)
            item_ids = [si.item_id for si in sale_items]
            items = [self._item_repo.get_by_id(iid) for iid in item_ids]
            items = [i for i in items if i is not None]

            profit = CalculationService.calculate_sale_profit(sale, sale_items, items)
            gross_total += profit["gross_profit"]
            net_total += profit["net_profit"]

        return {
            "year":         year,
            "month":        month,
            "gross_profit": gross_total,
            "net_profit":   net_total,
            "sale_count":   len(completed),
        }

    # ------------------------------------------------------------------
    # Profit by platform
    # ------------------------------------------------------------------

    def get_profit_by_platform(self) -> dict[str, dict]:
        """
        Return net profit grouped by sale platform.

        Only COMPLETED sales are included.

        Returns:
            {
                "Wallapop": {"net_profit": int, "sale_count": int},
                "eBay":     {"net_profit": int, "sale_count": int},
                ...
            }
        """
        sales = self._sale_repo.get_all()
        completed = [s for s in sales if s.status == SaleStatus.COMPLETED]

        result: dict[str, dict] = defaultdict(lambda: {"net_profit": 0, "sale_count": 0})

        for sale in completed:
            sale_items = self._sale_repo.get_items_for_sale(sale.id)
            items = [self._item_repo.get_by_id(si.item_id) for si in sale_items]
            items = [i for i in items if i is not None]

            profit = CalculationService.calculate_sale_profit(sale, sale_items, items)
            platform = sale.platform.value
            result[platform]["net_profit"] += profit["net_profit"]
            result[platform]["sale_count"] += 1

        return dict(result)

    # ------------------------------------------------------------------
    # Profit by category
    # ------------------------------------------------------------------

    def get_profit_by_category(self) -> dict[str, dict]:
        """
        Return net profit grouped by item category.

        Only items from COMPLETED sales are included. Each item's profit
        is allocated individually using CalculationService.

        Returns:
            {
                "Electronics": {"net_profit": int, "item_count": int},
                ...
            }
        """
        sales = self._sale_repo.get_all()
        sale_map = {s.id: s for s in sales if s.status == SaleStatus.COMPLETED}

        result: dict[str, dict] = defaultdict(lambda: {"net_profit": 0, "item_count": 0})

        for sale_id, sale in sale_map.items():
            sale_items = self._sale_repo.get_items_for_sale(sale_id)
            for si in sale_items:
                item = self._item_repo.get_by_id(si.item_id)
                if item is None:
                    continue
                profit = CalculationService.calculate_item_profit(
                    item, si, sale, sale_items
                )
                category = item.category.value
                result[category]["net_profit"] += profit["net_profit"]
                result[category]["item_count"] += 1

        return dict(result)

    # ------------------------------------------------------------------
    # Expense report
    # ------------------------------------------------------------------

    def get_expense_report(
        self,
        start: str | None = None,
        end: str | None = None,
    ) -> list[Expense]:
        """
        Return expenses, optionally filtered by date range.

        Args:
            start: ISO 8601 date string or None.
            end:   ISO 8601 date string or None.
        """
        if start and end:
            return self._expense_repo.get_by_date_range(start, end)
        return self._expense_repo.get_all()

    # ------------------------------------------------------------------
    # Excel export
    # ------------------------------------------------------------------

    def export_to_excel(self, report_data: list[dict], path: str) -> None:
        """
        Export a list of report row dicts to an Excel file.

        Args:
            report_data: List of dicts where keys become column headers.
            path:        Destination file path (e.g. 'reports/sales.xlsx').

        Raises:
            ImportError:  If openpyxl is not installed.
            OSError:      If the file cannot be written.
        """
        try:
            import openpyxl
        except ImportError:
            raise ImportError(
                "openpyxl is required for Excel export. "
                "Install it with: pip install openpyxl"
            )

        if not report_data:
            logger.warning("export_to_excel called with empty data.")
            return

        wb = openpyxl.Workbook()
        ws = wb.active

        headers = list(report_data[0].keys())
        ws.append(headers)

        for row in report_data:
            ws.append([row.get(h) for h in headers])

        wb.save(path)
        logger.info("Excel report exported: %s (%d rows)", path, len(report_data))
