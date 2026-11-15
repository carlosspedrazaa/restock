"""Work out what the pages show about each store, in one place.

The dashboard and the store page both use store_overview(), so their numbers
can never disagree. Templates only display what this module returns.
"""

from datetime import date, timedelta

import queries
import reorder


def plural(n, word):
    """Return '1 day' or '3 days' (works for any word that just adds an s)."""
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def days_between(later_date, earlier_date):
    """Return whole days from earlier_date to later_date, both 'YYYY-MM-DD' strings."""
    return (date.fromisoformat(later_date) - date.fromisoformat(earlier_date)).days


def due_status(last_visit, frequency, today):
    """Return (days_until_due, status, label) for a store's next scheduled visit."""
    if last_visit is None:
        return 0, "due", "Never visited"  # never visited means go now
    next_due = date.fromisoformat(last_visit) + timedelta(days=frequency)
    days_until_due = (next_due - today).days
    if days_until_due < 0:
        return days_until_due, "overdue", f"Overdue {plural(-days_until_due, 'day')}"
    if days_until_due == 0:
        return 0, "due", "Due today"
    return days_until_due, "ok", f"Due in {plural(days_until_due, 'day')}"


def counts_with_suggestions(latest, previous, frequency):
    """Return the latest visit's counts, each with a suggested_order from reorder.py."""
    previous_on_hand = {}
    gap = None  # None tells reorder.py this is a first visit
    if previous:
        previous_on_hand = {c["product_id"]: c["on_hand"] for c in previous["counts"]}
        gap = days_between(latest["visit_date"], previous["visit_date"])

    counts = []
    for count in latest["counts"]:
        suggested = reorder.suggest_order(
            # .get() gives None if this product wasn't counted last visit.
            previous_on_hand=previous_on_hand.get(count["product_id"]),
            received=count["received"],
            current_on_hand=count["on_hand"],
            days_between=gap,
            # The order has to last until the next scheduled visit.
            days_until_next_visit=frequency,
        )
        counts.append({**count, "suggested_order": suggested})
    return counts


def order_first(count):
    """Sort key: biggest orders on top, then products with nothing to order, by name."""
    return (-(count["suggested_order"] or 0), count["name"])


def store_overview(conn, store, today):
    """Return a store's visits, sorted counts, order list and due status as one dict."""
    visits = queries.store_history(conn, store["id"])
    latest = visits[0] if visits else None
    counts = []
    if latest:
        previous = visits[1] if len(visits) > 1 else None
        counts = counts_with_suggestions(latest, previous, store["visit_frequency_days"])
        counts.sort(key=order_first)

    # None ("can't suggest") and 0 ("nothing needed") both stay off the order list.
    order_lines = [c for c in counts if c["suggested_order"]]
    last_visit = latest["visit_date"] if latest else None
    days_until_due, status, label = due_status(
        last_visit, store["visit_frequency_days"], today
    )
    return {
        "store": store,
        "latest": latest,
        "earlier": visits[1:],
        "counts": counts,
        "order_lines": order_lines,
        # False after a first visit: no product has enough history for a suggestion.
        "has_history": any(c["suggested_order"] is not None for c in counts),
        "units_to_order": sum(c["suggested_order"] for c in order_lines),
        "out_of_stock": sum(1 for c in counts if c["on_hand"] == 0),
        "days_until_due": days_until_due,
        "status": status,
        "label": label,
    }


def route_totals(overviews):
    """Add up every store's overview for the numbers across the top of the dashboard."""
    return {
        "overdue": sum(1 for o in overviews if o["status"] == "overdue"),
        "products_to_order": sum(len(o["order_lines"]) for o in overviews),
        "units_to_order": sum(o["units_to_order"] for o in overviews),
        "out_of_stock": sum(o["out_of_stock"] for o in overviews),
    }
