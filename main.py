"""The web app: HTML pages and JSON API routes that read and write the Restock database."""

from datetime import date, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

import forms
import queries
import reorder
from db import get_connection

BASE_DIR = Path(__file__).parent

app = FastAPI(title="Restock")
# Serves style.css at /static/style.css.
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# --- Shapes of incoming API data ----------------------------------------------
# FastAPI checks every API request against these before our code runs, and replies
# with a clear 422 error if a field is missing, negative, or the wrong type.

class CountIn(BaseModel):
    """One product's count on a visit."""

    product_id: int
    on_hand: int = Field(ge=0)
    received: int = Field(default=0, ge=0)


class VisitIn(BaseModel):
    """A visit to log: which store, when, optional notes, and the counts."""

    store_id: int
    visit_date: date  # must look like "2026-11-13"
    notes: str | None = None
    counts: list[CountIn] = Field(min_length=1)


# --- Shared helpers -------------------------------------------------------------

def get_db():
    """Give a route its own database connection and close it afterwards."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def load_store_or_404(conn, store_id):
    """Return the store, or stop the request with a 404 if it doesn't exist."""
    store = queries.get_store(conn, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


def plural_days(n):
    """Return '1 day' or 'n days'."""
    return "1 day" if n == 1 else f"{n} days"


def add_due_status(store, today):
    """Return the store plus days_until_due, a status for colour, and a label to show."""
    if store["last_visit"] is None:
        # Never visited means it should be visited now.
        return {**store, "days_until_due": 0, "status": "due", "label": "Never visited"}
    last_visit = date.fromisoformat(store["last_visit"])
    next_due = last_visit + timedelta(days=store["visit_frequency_days"])
    days_until_due = (next_due - today).days
    if days_until_due < 0:
        status, label = "overdue", f"Overdue {plural_days(-days_until_due)}"
    elif days_until_due == 0:
        status, label = "due", "Due today"
    else:
        status, label = "ok", f"Due in {plural_days(days_until_due)}"
    return {**store, "days_until_due": days_until_due, "status": status, "label": label}


def days_between(later_date, earlier_date):
    """Return whole days from earlier_date to later_date, both 'YYYY-MM-DD' strings."""
    return (date.fromisoformat(later_date) - date.fromisoformat(earlier_date)).days


def add_suggestions(store, visits):
    """Give each of the latest visit's counts a suggested_order from reorder.py."""
    latest = visits[0]
    previous = visits[1] if len(visits) > 1 else None
    previous_on_hand = {}
    gap = None  # None tells reorder.py this is a first visit
    if previous:
        previous_on_hand = {c["product_id"]: c["on_hand"] for c in previous["counts"]}
        gap = days_between(latest["visit_date"], previous["visit_date"])

    for count in latest["counts"]:
        count["suggested_order"] = reorder.suggest_order(
            # .get() gives None if this product wasn't counted last visit.
            previous_on_hand=previous_on_hand.get(count["product_id"]),
            received=count["received"],
            current_on_hand=count["on_hand"],
            days_between=gap,
            # The order has to last until the next scheduled visit.
            days_until_next_visit=store["visit_frequency_days"],
        )


def render_visit_form(request, conn, store, values, errors, status_code=200):
    """Show the log-a-visit form, refilled with what was typed and any error messages."""
    products = queries.products_for_store(conn, store["id"])
    carried = [p for p in products if p["carried"]]
    others = [p for p in products if not p["carried"]]
    if not carried:
        # A store with no visits yet: show every product up front.
        carried, others = others, []
    context = {
        "store": store,
        "carried": carried,
        "others": others,
        "values": values,
        "errors": errors,
    }
    return templates.TemplateResponse(
        request, "visit_form.html", context, status_code=status_code
    )


# --- HTML pages ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, conn=Depends(get_db)):
    """Show every store, most overdue first, so you can see where to go next."""
    today = date.today()
    stores = [add_due_status(s, today) for s in queries.stores_with_last_visit(conn)]
    stores.sort(key=lambda store: store["days_until_due"])
    return templates.TemplateResponse(
        request, "dashboard.html", {"stores": stores, "today": today}
    )


@app.get("/stores/{store_id}", response_class=HTMLResponse)
def store_page(request: Request, store_id: int, saved: bool = False, conn=Depends(get_db)):
    """Show one store's latest counts and a list of its earlier visits."""
    store = load_store_or_404(conn, store_id)
    visits = queries.store_history(conn, store_id)
    if visits:
        add_suggestions(store, visits)
    context = {
        "store": store,
        "latest": visits[0] if visits else None,
        "earlier": visits[1:],
        "saved": saved,  # true right after a visit was saved, to show a message
    }
    return templates.TemplateResponse(request, "store.html", context)


@app.get("/stores/{store_id}/visits/new", response_class=HTMLResponse)
def new_visit_page(request: Request, store_id: int, conn=Depends(get_db)):
    """Show an empty log-a-visit form with today's date filled in."""
    store = load_store_or_404(conn, store_id)
    values = {"visit_date": date.today().isoformat()}
    return render_visit_form(request, conn, store, values, errors={})


@app.post("/stores/{store_id}/visits", response_class=HTMLResponse)
async def save_visit_form(request: Request, store_id: int, conn=Depends(get_db)):
    """Save a submitted visit form, or show it again with errors if anything is wrong."""
    store = load_store_or_404(conn, store_id)
    # The product boxes are named on_hand_<id>, so we read the whole form
    # instead of listing every field as a function parameter.
    form = await request.form()
    product_ids = [p["id"] for p in queries.products_for_store(conn, store_id)]
    visit_date, counts, errors = forms.parse_visit_form(form, product_ids, date.today())
    if errors:
        # Nothing is saved; the user sees what they typed plus what to fix.
        return render_visit_form(request, conn, store, dict(form), errors, status_code=400)

    notes = form.get("notes", "").strip() or None
    queries.insert_visit(conn, store_id, visit_date.isoformat(), notes, counts)
    # 303 tells the browser to load the store page with GET, so refreshing
    # that page doesn't resubmit the form and save the visit twice.
    return RedirectResponse(f"/stores/{store_id}?saved=true", status_code=303)


# --- JSON API ------------------------------------------------------------------------

@app.get("/api/stores")
def get_stores(conn=Depends(get_db)):
    """List all stores."""
    return queries.list_stores(conn)


@app.get("/api/products")
def get_products(conn=Depends(get_db)):
    """List all products."""
    return queries.list_products(conn)


@app.get("/api/stores/{store_id}/visits")
def get_store_history(store_id: int, conn=Depends(get_db)):
    """Show one store and its visit history, newest visit first."""
    store = load_store_or_404(conn, store_id)
    return {"store": store, "visits": queries.store_history(conn, store_id)}


@app.post("/api/visits", status_code=201)
def log_visit(visit: VisitIn, conn=Depends(get_db)):
    """Save a new visit with its counts after checking the store and products exist."""
    load_store_or_404(conn, visit.store_id)

    product_ids = [count.product_id for count in visit.counts]
    if len(product_ids) != len(set(product_ids)):
        # Counting the same product twice in one visit is almost always a typo.
        raise HTTPException(status_code=400, detail="A product appears more than once")
    missing = queries.find_missing_products(conn, product_ids)
    if missing:
        raise HTTPException(status_code=400, detail=f"Unknown product ids: {missing}")

    visit_id = queries.insert_visit(
        conn,
        visit.store_id,
        visit.visit_date.isoformat(),
        visit.notes,
        [count.model_dump() for count in visit.counts],
    )
    return {"visit_id": visit_id}
