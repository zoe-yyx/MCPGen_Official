"""Hotel data tools for mcp_project72 — mock MySQL (SQLite) and Google Sheets pricing."""

import json
import sqlite3
import threading

from .utils.log_decorator import log_mcp_call

_DB_LOCK = threading.Lock()
_db_conn: sqlite3.Connection | None = None

# Pricing table (mock Google Sheets)
_PRICING_DATA = [
    {"room_type": "Standard", "weekday_price": 80,  "weekend_price": 100, "extra_bed": 20, "breakfast_included": False},
    {"room_type": "Deluxe",   "weekday_price": 120, "weekend_price": 150, "extra_bed": 25, "breakfast_included": False},
    {"room_type": "Suite",    "weekday_price": 200, "weekend_price": 250, "extra_bed": 30, "breakfast_included": True},
    {"room_type": "Family",   "weekday_price": 150, "weekend_price": 180, "extra_bed": 20, "breakfast_included": False},
]

_DB_SCHEMA = """
Tables in hotel_db:
  rooms(room_id INT, room_number TEXT, room_type TEXT, floor INT, price_per_night REAL, status TEXT)
    status values: 'available', 'occupied', 'maintenance'
    room_type values: 'Standard', 'Deluxe', 'Suite', 'Family'
  guests(guest_id INT, name TEXT, phone TEXT, email TEXT, wa_id TEXT)
  bookings(booking_id INT, guest_id INT, room_id INT, check_in DATE, check_out DATE, total_price REAL, status TEXT)
    status values: 'confirmed', 'checked_in', 'checked_out', 'cancelled'
"""


def _get_db() -> sqlite3.Connection:
    global _db_conn
    with _DB_LOCK:
        if _db_conn is None:
            _db_conn = sqlite3.connect(":memory:", check_same_thread=False)
            _db_conn.row_factory = sqlite3.Row
            _init_hotel_db(_db_conn)
    return _db_conn


def _init_hotel_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE rooms (
            room_id INTEGER PRIMARY KEY,
            room_number TEXT NOT NULL,
            room_type TEXT NOT NULL,
            floor INTEGER,
            price_per_night REAL,
            status TEXT NOT NULL DEFAULT 'available'
        );
        CREATE TABLE guests (
            guest_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            wa_id TEXT
        );
        CREATE TABLE bookings (
            booking_id INTEGER PRIMARY KEY,
            guest_id INTEGER,
            room_id INTEGER,
            check_in DATE,
            check_out DATE,
            total_price REAL,
            status TEXT DEFAULT 'confirmed',
            FOREIGN KEY(guest_id) REFERENCES guests(guest_id),
            FOREIGN KEY(room_id) REFERENCES rooms(room_id)
        );
    """)
    cur.executemany(
        "INSERT INTO rooms VALUES (?,?,?,?,?,?)",
        [
            (101, "101", "Standard", 1, 80.0,  "available"),
            (102, "102", "Standard", 1, 80.0,  "occupied"),
            (103, "103", "Deluxe",   1, 120.0, "available"),
            (201, "201", "Deluxe",   2, 120.0, "available"),
            (202, "202", "Suite",    2, 200.0, "occupied"),
            (203, "203", "Suite",    2, 200.0, "available"),
            (204, "204", "Family",   2, 150.0, "maintenance"),
            (301, "301", "Family",   3, 150.0, "available"),
            (302, "302", "Deluxe",   3, 120.0, "available"),
            (303, "303", "Standard", 3, 80.0,  "available"),
        ],
    )
    cur.executemany(
        "INSERT INTO guests VALUES (?,?,?,?,?)",
        [
            (1, "Alice Chen",   "+60123456789", "EMAIL_PLACEHOLDER",   "60123456789"),
            (2, "Bob Smith",    "+60198765432", "EMAIL_PLACEHOLDER",     "60198765432"),
            (3, "Carol Wong",   "+60177654321", "EMAIL_PLACEHOLDER",   "60177654321"),
            (4, "David Lee",    "+60156789012", "EMAIL_PLACEHOLDER",   "60156789012"),
            (5, "Emma Johnson", "+60134567890", "EMAIL_PLACEHOLDER",    "60134567890"),
        ],
    )
    cur.executemany(
        "INSERT INTO bookings VALUES (?,?,?,?,?,?,?)",
        [
            (1001, 1, 102, "2026-05-18", "2026-05-21", 240.0, "checked_in"),
            (1002, 2, 202, "2026-05-17", "2026-05-20", 600.0, "checked_in"),
            (1003, 3, 101, "2026-05-19", "2026-05-22", 240.0, "confirmed"),
            (1004, 4, 201, "2026-05-20", "2026-05-23", 360.0, "confirmed"),
            (1005, 5, 303, "2026-05-18", "2026-05-19",  80.0, "checked_out"),
        ],
    )
    conn.commit()


@log_mcp_call("tool", "get_pricing")
def get_pricing() -> str:
    """Return room pricing data from the mock Google Sheets pricing table."""
    return json.dumps({
        "source": "Google Sheets (mock)",
        "pricing": _PRICING_DATA,
        "schema_hint": "room_type, weekday_price, weekend_price, extra_bed_fee, breakfast_included",
    })


@log_mcp_call("tool", "execute_sql_query")
def execute_sql_query(query: str) -> str:
    """Execute a read-only SQL SELECT query on the mock hotel database.

    Only SELECT statements are permitted for security.
    """
    normalized = query.strip().upper()
    forbidden = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "REPLACE")
    if not normalized.startswith("SELECT") and not normalized.startswith("WITH"):
        raise ValueError("Only SELECT queries are permitted.")
    for kw in forbidden:
        if kw in normalized:
            raise ValueError(f"Forbidden keyword '{kw}' detected. Only SELECT statements allowed.")

    conn = _get_db()
    try:
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description] if cur.description else []
        results = [dict(zip(columns, row)) for row in rows]
        return json.dumps({
            "query": query,
            "row_count": len(results),
            "columns": columns,
            "results": results,
            "schema_info": _DB_SCHEMA,
        })
    except Exception as e:
        return json.dumps({"error": str(e), "query": query})


def get_db_schema() -> str:
    """Return the hotel database schema for use in system prompts."""
    return _DB_SCHEMA
