"""The web app: URL routes that read and write the Restock database."""

from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

import queries
from db import get_connection

app = FastAPI(title="Restock")


# --- Shapes of incoming data -------------------------------------------------
# FastAPI checks every request against these before our code runs, and replies
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


# --- Database connection per request ------------------------------------------

def get_db():
    """Give a route its own database connection and close it afterwards."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


# --- Routes ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home():
    """Placeholder home page until the real dashboard in step 4."""
    return "<h1>Restock</h1><p>API docs: <a href='/docs'>/docs</a></p>"


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
    store = queries.get_store(conn, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")
    return {"store": store, "visits": queries.store_history(conn, store_id)}


@app.post("/api/visits", status_code=201)
def log_visit(visit: VisitIn, conn=Depends(get_db)):
    """Save a new visit with its counts after checking the store and products exist."""
    if queries.get_store(conn, visit.store_id) is None:
        raise HTTPException(status_code=404, detail="Store not found")

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
