"""
models/errors.py

Application exception hierarchy.

All custom exceptions are defined here and imported from here by the
Repository, Service, and GUI layers. No layer defines its own exceptions.

Hierarchy:
    AppError
    ├── RepositoryError   — database-level failures (raised by repositories)
    └── BusinessRuleError — business rule violations (raised by services)
"""


class AppError(Exception):
    """Base class for all application exceptions."""


class RepositoryError(AppError):
    """
    Raised by repositories when a database operation fails.

    Wraps sqlite3 errors so upper layers never need to import sqlite3.
    """


class BusinessRuleError(AppError):
    """
    Raised by services when a business rule is violated.

    Messages should be written in plain language suitable for display
    directly in a user-facing dialog.

    Examples:
        "Only Available or Reserved items can be added to a sale."
        "Cannot delete a batch that contains sold items."
    """
