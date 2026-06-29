-- 001_initial_schema.sql
-- Initial schema: all five core tables.
-- Money values stored as INTEGER (cents). Dates as TEXT (ISO 8601).
-- Foreign keys are enforced at the connection level (PRAGMA foreign_keys = ON).

CREATE TABLE purchase_batches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    seller          TEXT,
    platform        TEXT    NOT NULL,
    payment_method  TEXT    NOT NULL,
    shipping_cost   INTEGER NOT NULL DEFAULT 0,
    fees            INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    currency        TEXT    NOT NULL DEFAULT 'EUR',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id        INTEGER NOT NULL REFERENCES purchase_batches(id),
    category        TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    description     TEXT,
    condition       TEXT    NOT NULL,
    purchase_cost   INTEGER NOT NULL DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'Available',
    currency        TEXT    NOT NULL DEFAULT 'EUR',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE sales (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    platform        TEXT    NOT NULL,
    buyer           TEXT,
    payment_method  TEXT    NOT NULL,
    listing_price   INTEGER NOT NULL DEFAULT 0,
    final_price     INTEGER NOT NULL DEFAULT 0,
    shipping_cost   INTEGER NOT NULL DEFAULT 0,
    fees            INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    status          TEXT    NOT NULL DEFAULT 'Completed',
    currency        TEXT    NOT NULL DEFAULT 'EUR',
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE TABLE sale_items (
    sale_id              INTEGER NOT NULL REFERENCES sales(id),
    item_id              INTEGER NOT NULL REFERENCES items(id),
    allocated_sale_price INTEGER NOT NULL DEFAULT 0,
    currency             TEXT    NOT NULL DEFAULT 'EUR',
    created_at           TEXT    NOT NULL,
    updated_at           TEXT    NOT NULL,
    PRIMARY KEY (sale_id, item_id)
);

CREATE TABLE expenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    category        TEXT    NOT NULL,
    description     TEXT,
    amount          INTEGER NOT NULL DEFAULT 0,
    payment_method  TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);