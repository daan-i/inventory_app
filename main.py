"""
main.py

Application entry point.

Responsibilities:
  - Configure logging
  - Run database migrations
  - Launch the GUI (placeholder for now)

This is the only place in the codebase where a broad Exception catch
is acceptable, per SPECIFICATION.md §10.
"""

import logging
import os
import sys

from config.settings import APP_NAME, APP_VERSION, LOG_FOLDER
from database.db import run_migrations


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def configure_logging() -> None:
    os.makedirs(LOG_FOLDER, exist_ok=True)

    log_path = os.path.join(LOG_FOLDER, "inventory_app.log")

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Console shows WARNING and above only; file gets everything.
    logging.getLogger().handlers[1].setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    configure_logging()

    logger = logging.getLogger(__name__)
    logger.info("Starting %s v%s", APP_NAME, APP_VERSION)

    try:
        run_migrations()
    except Exception:
        logger.critical("Failed to initialise the database.", exc_info=True)
        sys.exit(1)

    logger.info("Database ready.")

    # GUI launch goes here in Phase 7.
    logger.info("%s started successfully.", APP_NAME)


if __name__ == "__main__":
    main()