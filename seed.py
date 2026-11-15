"""Reset the database and fill it with invented demo data for 8 garden centers."""

import random
from datetime import date, timedelta
from pathlib import Path

from db import DB_PATH, get_connection, init_db

# A fixed seed means everyone who runs this gets exactly the same demo data.
random.seed(42)

WEEKS = 7
# Counted back from today so the live demo always looks current,
# instead of every store showing "Overdue 40 days" a month from now.
START_DATE = date.today() - timedelta(days=WEEKS * 7)

# Mimics a standing order: if stock was low last visit, this many units arrive.
LOW_LEVEL = 12
RESTOCK_AMOUNT = 24

# (name, city, visit_frequency_days, busyness). All names are invented.
# Busyness scales sales, so busy stores sell more of everything.
# Plain numbered names so nobody mistakes them for real stores.
STORES = [
    ("Tampa 1", "Tampa", 3, 1.5),
    ("Tampa 2", "Tampa", 4, 1.2),
    ("Tampa 3", "Tampa", 7, 1.0),
    ("Tampa 4", "Tampa", 7, 0.8),
]

# (name, size, category, average units sold per day at a normal store)
# Includes every plant named in NOTES below, so the notes parser has matches.
PRODUCTS = [
    ("Poinsettia", "6 in", "Seasonal", 1.5),
    ("Garden Mum", "8 in", "Seasonal", 1.8),
    ("Lavender", "1 gal", "Perennials", 1.2),
    ("Petunia", "4 in", "Annuals", 2.0),
    ("Boxwood", "3 gal", "Shrubs", 0.6),
    ("Hydrangea", "2 gal", "Shrubs", 0.5),
    ("Rosemary", "1 gal", "Herbs", 0.7),
    ("Tomato", "4 in", "Vegetables", 1.1),
]

# Sample visit notes in English, Spanish and a mix, for the notes parser later.
NOTES = [
    "Replace all petunias next visit, they look tired.",
    "Order more lavender, sold out before the weekend.",
    "Recibimos boxwood, 3 dañados.",
    "Manager wants the mums on the endcap.",
    "Faltan hydrangeas, pedir más.",
    "Rosemary looks great, no action needed.",
]


def reset_database():
    """Delete the old database file so every seed starts from a clean slate."""
    Path(DB_PATH).unlink(missing_ok=True)


def insert_stores(conn):
    """Insert the demo stores and return (id, visit_frequency_days, busyness) for each."""
    stores = []
    for name, city, frequency, busyness in STORES:
        cursor = conn.execute(
            "INSERT INTO stores (name, city, visit_frequency_days) VALUES (?, ?, ?)",
            (name, city, frequency),
        )
        stores.append((cursor.lastrowid, frequency, busyness))
    return stores


def insert_products(conn):
    """Insert the demo products and return (id, daily_sales) for each."""
    products = []
    for name, size, category, daily_sales in PRODUCTS:
        cursor = conn.execute(
            "INSERT INTO products (name, size, category) VALUES (?, ?, ?)",
            (name, size, category),
        )
        products.append((cursor.lastrowid, daily_sales))
    return products


def insert_visit(conn, store_id, visit_date):
    """Insert one visit, with a note about a quarter of the time, and return its id."""
    note = random.choice(NOTES) if random.random() < 0.25 else None
    cursor = conn.execute(
        "INSERT INTO visits (store_id, visit_date, notes) VALUES (?, ?, ?)",
        (store_id, visit_date.isoformat(), note),
    )
    return cursor.lastrowid


def next_count(previous_on_hand, daily_sales, days):
    """Return (on_hand, received) at the next visit after a delivery and some sales."""
    received = RESTOCK_AMOUNT if previous_on_hand < LOW_LEVEL else 0
    available = previous_on_hand + received
    # Real sales swing around the average, so vary them by up to 40% either way.
    sold = round(daily_sales * days * random.uniform(0.6, 1.4))
    return max(0, available - sold), received


def simulate_store(conn, store_id, frequency, busyness, products):
    """Create every visit and count for one store over the demo period."""
    # Each store carries its own selection of products.
    # Up to 2 products left out, so some stores show "not carried here yet".
    catalog = random.sample(products, k=random.randint(len(products) - 2, len(products)))
    on_hand = {product_id: random.randint(15, 40) for product_id, _ in catalog}
    visit_count = WEEKS * 7 // frequency

    for visit_number in range(visit_count):
        visit_date = START_DATE + timedelta(days=visit_number * frequency)
        visit_id = insert_visit(conn, store_id, visit_date)
        for product_id, daily_sales in catalog:
            received = 0  # the first visit has no previous delivery
            if visit_number > 0:
                on_hand[product_id], received = next_count(
                    on_hand[product_id], daily_sales * busyness, frequency
                )
            conn.execute(
                "INSERT INTO counts (visit_id, product_id, on_hand, received) "
                "VALUES (?, ?, ?, ?)",
                (visit_id, product_id, on_hand[product_id], received),
            )


def main():
    """Rebuild the database from scratch and fill it with demo data."""
    reset_database()
    conn = get_connection()
    init_db(conn)
    products = insert_products(conn)
    for store_id, frequency, busyness in insert_stores(conn):
        simulate_store(conn, store_id, frequency, busyness, products)
    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH} with demo data.")


# Runs main() only when started as "python seed.py", not when another file imports this one.
if __name__ == "__main__":
    main()
