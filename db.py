"""Database helpers: open a connection and create the tables."""

import os
import sqlite3
from pathlib import Path

# An environment variable lets tests and the deployed app use a different file.
DB_PATH = os.environ.get("RESTOCK_DB", "restock.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path=DB_PATH):
    """Open a SQLite connection with foreign keys enforced and dict-style rows."""
    conn = sqlite3.connect(db_path)
    # Lets code write row["name"] instead of remembering that name is row[1].
    conn.row_factory = sqlite3.Row
    # SQLite ignores REFERENCES rules unless this is switched on per connection.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """Create any missing tables from schema.sql."""
    conn.executescript(SCHEMA_PATH.read_text())
