# config/settings.py
# Application-wide constants. No hardcoded values anywhere else in the codebase.

APP_NAME          = "Inventory Manager"
APP_VERSION       = "1.0.0"

DATABASE_NAME     = "inventory.db"
MIGRATIONS_FOLDER = "database/migrations/"
BACKUP_FOLDER     = "backups/"
LOG_FOLDER        = "logs/"

DEFAULT_CURRENCY  = "EUR"
DATE_FORMAT       = "%Y-%m-%d"
DATETIME_FORMAT   = "%Y-%m-%dT%H:%M:%S"
