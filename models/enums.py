"""
models/enums.py

All application enumerations.

Rules:
  - New enum values are added here and nowhere else.
  - Enums inherit from (str, Enum) so their values can be stored
    directly in SQLite as TEXT and compared with plain strings.
  - Values match exactly what is stored in the database.
"""

from enum import Enum


class Category(str, Enum):
    ELECTRONICS  = "Electronics"
    TOOLS        = "Tools"
    LEGO         = "LEGO"
    HOUSEHOLD    = "Household"
    COLLECTIBLES = "Collectibles"
    OTHER        = "Other"


class Condition(str, Enum):
    NEW      = "New"
    LIKE_NEW = "Like New"
    GOOD     = "Good"
    FAIR     = "Fair"
    POOR     = "Poor"


class ItemStatus(str, Enum):
    PURCHASED  = "Purchased"
    IN_TRANSIT = "In Transit"
    AVAILABLE  = "Available"
    RESERVED   = "Reserved"
    SOLD       = "Sold"
    RETURNED   = "Returned"
    DISCARDED  = "Discarded"


class Platform(str, Enum):
    WALLAPOP    = "Wallapop"
    EBAY        = "eBay"
    MILANUNCIOS = "Milanuncios"
    FACEBOOK    = "Facebook Marketplace"
    IN_PERSON   = "In Person"
    OTHER       = "Other"


class PaymentMethod(str, Enum):
    CASH          = "Cash"
    BANK_TRANSFER = "Bank Transfer"
    PAYPAL        = "PayPal"
    BIZUM         = "Bizum"
    OTHER         = "Other"


class ExpenseCategory(str, Enum):
    PACKAGING  = "Packaging"
    FUEL       = "Fuel"
    SOFTWARE   = "Software"
    OFFICE     = "Office Supplies"
    STORAGE    = "Storage"
    EQUIPMENT  = "Equipment"
    MARKETING  = "Marketing"
    OTHER      = "Other"


class SaleStatus(str, Enum):
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"
