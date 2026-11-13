-- Restock database blueprint.
-- IF NOT EXISTS lets the app run this on every start without errors or data loss.

-- Garden centers on the route.
CREATE TABLE IF NOT EXISTS stores (
    id                   INTEGER PRIMARY KEY,
    name                 TEXT NOT NULL,
    city                 TEXT NOT NULL,
    -- The reorder formula plans stock to last until the next visit.
    visit_frequency_days INTEGER NOT NULL CHECK (visit_frequency_days > 0)
);

-- Plants. The same plant in two pot sizes sells and restocks separately,
-- so each name + size pair is its own product.
CREATE TABLE IF NOT EXISTS products (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    size     TEXT NOT NULL,  -- pot size, e.g. '1 gal', '4 in'
    category TEXT NOT NULL,  -- e.g. 'Perennials', 'Shrubs'
    UNIQUE (name, size)
);

-- One row per store visit. No unique (store, date) rule because
-- two visits on the same day can really happen.
CREATE TABLE IF NOT EXISTS visits (
    id         INTEGER PRIMARY KEY,
    store_id   INTEGER NOT NULL REFERENCES stores(id),
    visit_date TEXT NOT NULL,  -- 'YYYY-MM-DD' so dates sort correctly as text
    notes      TEXT            -- free text, may be empty
);

-- What was counted on a visit, one row per product.
CREATE TABLE IF NOT EXISTS counts (
    id         INTEGER PRIMARY KEY,
    visit_id   INTEGER NOT NULL REFERENCES visits(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    on_hand    INTEGER NOT NULL CHECK (on_hand >= 0),  -- shelf + backroom total
    -- Delivered since the previous visit; needed to work out units sold.
    received   INTEGER NOT NULL DEFAULT 0 CHECK (received >= 0),
    UNIQUE (visit_id, product_id)
);
