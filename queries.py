"""All the SQL the app runs, kept in one place so main.py only deals with web requests."""


def list_stores(conn):
    """Return every store, alphabetical by name."""
    rows = conn.execute(
        "SELECT id, name, city, visit_frequency_days FROM stores ORDER BY name"
    ).fetchall()
    return [dict(row) for row in rows]


def list_products(conn):
    """Return every product, grouped by category and then by name."""
    rows = conn.execute(
        "SELECT id, name, size, category FROM products ORDER BY category, name"
    ).fetchall()
    return [dict(row) for row in rows]


def get_store(conn, store_id):
    """Return one store as a dict, or None if the id does not exist."""
    row = conn.execute(
        "SELECT id, name, city, visit_frequency_days FROM stores WHERE id = ?",
        (store_id,),
    ).fetchone()
    return dict(row) if row else None


def find_missing_products(conn, product_ids):
    """Return the ids from product_ids that are not in the products table."""
    existing = {row["id"] for row in conn.execute("SELECT id FROM products")}
    return sorted(set(product_ids) - existing)


def insert_visit(conn, store_id, visit_date, notes, counts):
    """Save a visit and all its counts together, and return the new visit id."""
    # "with conn" commits if everything succeeds and undoes everything if any
    # insert fails, so we never end up with a visit that is missing its counts.
    with conn:
        cursor = conn.execute(
            "INSERT INTO visits (store_id, visit_date, notes) VALUES (?, ?, ?)",
            (store_id, visit_date, notes),
        )
        visit_id = cursor.lastrowid
        for count in counts:
            conn.execute(
                "INSERT INTO counts (visit_id, product_id, on_hand, received) "
                "VALUES (?, ?, ?, ?)",
                (visit_id, count["product_id"], count["on_hand"], count["received"]),
            )
    return visit_id


def store_history(conn, store_id):
    """Return a store's visits, newest first, each with its product counts."""
    visits = conn.execute(
        "SELECT id, visit_date, notes FROM visits "
        "WHERE store_id = ? ORDER BY visit_date DESC, id DESC",
        (store_id,),
    ).fetchall()
    # One query for all counts instead of one query per visit.
    count_rows = conn.execute(
        "SELECT c.visit_id, p.id AS product_id, p.name, p.size, c.on_hand, c.received "
        "FROM counts c "
        "JOIN visits v ON v.id = c.visit_id "
        "JOIN products p ON p.id = c.product_id "
        "WHERE v.store_id = ? "
        "ORDER BY p.name",
        (store_id,),
    ).fetchall()

    counts_by_visit = {}
    for row in count_rows:
        count = dict(row)
        visit_id = count.pop("visit_id")
        counts_by_visit.setdefault(visit_id, []).append(count)

    return [
        {**dict(visit), "counts": counts_by_visit.get(visit["id"], [])}
        for visit in visits
    ]
