"""
models/domain.py

Domain model dataclasses.

Rules:
  - Pure data containers only. No methods, no business logic.
  - Shared between the Repository and Service layers.
  - The GUI consumes these objects for display.
  - All monetary fields are integers (cents).
  - All date fields are strings in ISO 8601 format (YYYY-MM-DD).
  - All timestamp fields are strings in ISO 8601 format (YYYY-MM-DDTHH:MM:SS).
  - Enums and exceptions live in enums.py and errors.py respectively —
    not here.
"""

from dataclasses import dataclass, field
from typing import Optional

from models.enums import (
    Category,
    Condition,
    ExpenseCategory,
    ItemStatus,
    PaymentMethod,
    Platform,
    SaleStatus,
)


@dataclass
class PurchaseBatch:
    id:             Optional[int]  # None until persisted
    date:           str            # YYYY-MM-DD
    platform:       Platform
    payment_method: PaymentMethod
    shipping_cost:  int            # cents
    fees:           int            # cents
    currency:       str
    created_at:     str            # YYYY-MM-DDTHH:MM:SS
    updated_at:     str            # YYYY-MM-DDTHH:MM:SS
    seller:         Optional[str]  = None
    notes:          Optional[str]  = None


@dataclass
class Item:
    id:            Optional[int]   # None until persisted
    batch_id:      int
    category:      Category
    name:          str
    condition:     Condition
    purchase_cost: int             # cents
    status:        ItemStatus
    currency:      str
    created_at:    str             # YYYY-MM-DDTHH:MM:SS
    updated_at:    str             # YYYY-MM-DDTHH:MM:SS
    description:   Optional[str]  = None


@dataclass
class Sale:
    id:             Optional[int]  # None until persisted
    date:           str            # YYYY-MM-DD
    platform:       Platform
    payment_method: PaymentMethod
    listing_price:  int            # cents
    final_price:    int            # cents
    shipping_cost:  int            # cents
    fees:           int            # cents
    status:         SaleStatus
    currency:       str
    created_at:     str            # YYYY-MM-DDTHH:MM:SS
    updated_at:     str            # YYYY-MM-DDTHH:MM:SS
    buyer:          Optional[str]  = None
    notes:          Optional[str]  = None


@dataclass
class SaleItem:
    sale_id:             int
    item_id:             int
    allocated_sale_price: int      # cents
    currency:            str
    created_at:          str       # YYYY-MM-DDTHH:MM:SS
    updated_at:          str       # YYYY-MM-DDTHH:MM:SS


@dataclass
class Expense:
    id:             Optional[int]  # None until persisted
    date:           str            # YYYY-MM-DD
    category:       ExpenseCategory
    amount:         int            # cents
    payment_method: PaymentMethod
    created_at:     str            # YYYY-MM-DDTHH:MM:SS
    updated_at:     str            # YYYY-MM-DDTHH:MM:SS
    description:    Optional[str]  = None
