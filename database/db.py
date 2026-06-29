"""
database/db.py

Responsibilities:
  - Open and configure SQLite connections
  - Execute queries and writes
  - Manage transactions
  - Run schema migrations
  - Create database backups

This module knows nothing about the domain. It must not import from
models, services, or repositories.
"""

import logging
import os
import shutil
import sqlite3
from collections.abc import Callable
from datetime import datetime

from config.settings import (
    BACKUP_FOLDER,
    DATABASE_NAME,
    DATETIME_FORMAT,
    LOG_FOLDER,
    MIGRATIONS_FOLDER,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

os.makedirs(LOG_FOLDER, exist_ok=True)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Open a SQLite connection with foreign key enforcement and row factory.

    Row factory is set to sqlite3.Row so callers can access columns by name
    rather than by index.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def execute_query(sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    """
    Execute a SELECT statement and return all matching rows.

    Args:
        sql:    The SQL query string. Use ? placeholders for parameters.
        params: Query parameters. Never format user input directly into sql.

    Returns:
        A list of sqlite3.Row objects (accessible by column name).
    """
    logger.debug("execute_query: %s | params: %s", sql, params)
    with get_connection() as conn:
        cursor = conn.execute(sql, params)
        return cursor.fetchall()


def execute_write(sql: str, params: tuple = ()) -> int:
    """
    Execute an INSERT, UPDATE, or DELETE statement.

    Args:
        sql:    The SQL statement. Use ? placeholders for parameters.
        params: Statement parameters.

    Returns:
        The lastrowid for INSERT statements; 0 for UPDATE/DELETE.

    Raises:
        sqlite3.Error: Propagated to the calling repository to wrap as
                       RepositoryError.
    """
    logger.debug("execute_write: %s | params: %s", sql, params)
    with get_connection() as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid


# ---------------------------------------------------------------------------
# Transaction management
# ---------------------------------------------------------------------------

def execute_transaction(operations: Callable[[sqlite3.Connection], None]) -> None:
    """
    Execute multiple write operations atomically.

    The caller provides a callable that receives an open connection and
    performs all writes against it. If any operation raises an exception,
    the transaction is rolled back and the exception is re-raised.

    Usage:
        def my_operations(conn: sqlite3.Connection) -> None:
            conn.execute("INSERT INTO ...", (...))
            conn.execute("UPDATE ...", (...))

        execute_transaction(my_operations)

    Args:
        operations: A callable that accepts a sqlite3.Connection and performs
                    one or more write operations. Must not call conn.commit()
                    itself — the transaction manager handles that.

    Raises:
        sqlite3.Error: Propagated after rollback.
        Any exception raised inside operations is propagated after rollback.
    """
    conn = get_connection()
    try:
        operations(conn)
        conn.commit()
        logger.debug("Transaction committed successfully.")
    except Exception:
        conn.rollback()
        logger.error("Transaction rolled back due to error.", exc_info=True)
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

def run_migrations() -> None:
    """
    Apply any pending SQL migration files in database/migrations/.

    Migration files must be named with a numeric prefix followed by an
    underscore and a description, e.g.:
        001_initial_schema.sql
        002_add_notes_column.sql

    The current schema version is stored in SQLite's built-in user_version
    pragma. Only files whose numeric prefix is greater than the current
    version are applied, in ascending order.

    This function is idempotent: running it multiple times on an
    already-up-to-date database is safe and has no effect.
    """
    os.makedirs(MIGRATIONS_FOLDER, exist_ok=True)

    with get_connection() as conn:
        current_version: int = conn.execute("PRAGMA user_version").fetchone()[0]
        logger.debug("Current schema version: %d", current_version)

        migration_files = sorted(
            f for f in os.listdir(MIGRATIONS_FOLDER)
            if f.endswith(".sql") and _migration_version(f) > current_version
        )

        if not migration_files:
            logger.debug("No pending migrations.")
            return

        for filename in migration_files:
            version = _migration_version(filename)
            filepath = os.path.join(MIGRATIONS_FOLDER, filename)

            logger.info("Applying migration %s ...", filename)

            with open(filepath, encoding="utf-8") as f:
                sql = f.read()

            conn.executescript(sql)
            # executescript issues an implicit COMMIT, so we update the
            # version inside a new statement rather than relying on the
            # script's transaction state.
            conn.execute(f"PRAGMA user_version = {version}")
            conn.commit()

            logger.info("Migration %s applied (schema version → %d).", filename, version)


def _migration_version(filename: str) -> int:
    """
    Extract the numeric version from a migration filename.

    Example: '001_initial_schema.sql' → 1
    """
    try:
        return int(filename.split("_")[0])
    except (ValueError, IndexError):
        raise ValueError(
            f"Migration filename '{filename}' does not start with a numeric prefix. "
            "Expected format: '001_description.sql'."
        )


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

def create_backup() -> str:
    """
    Copy the current database file to the backups folder.

    The backup filename includes a timestamp so multiple backups can
    coexist without overwriting each other.

    Returns:
        The absolute path of the created backup file.

    Raises:
        FileNotFoundError: If the database file does not yet exist.
        OSError: If the backup folder cannot be created or the file
                 cannot be copied.
    """
    if not os.path.exists(DATABASE_NAME):
        raise FileNotFoundError(
            f"Cannot back up '{DATABASE_NAME}': database file not found. "
            "Run run_migrations() first to initialise the database."
        )

    os.makedirs(BACKUP_FOLDER, exist_ok=True)

    timestamp = datetime.now().strftime(DATETIME_FORMAT).replace(":", "-")
    backup_filename = f"inventory_{timestamp}.db"
    backup_path = os.path.join(BACKUP_FOLDER, backup_filename)

    shutil.copy2(DATABASE_NAME, backup_path)

    logger.info("Backup created: %s", backup_path)
    return backup_path
