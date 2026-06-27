"""SQLite storage for detection history and system events. No server to install -
single file, created automatically on first run."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "traffic.db")


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detection_log (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            direction         TEXT NOT NULL,
            incoming_count    INTEGER DEFAULT 0,
            weighted_count    REAL DEFAULT 0.0,
            congestion_score  REAL DEFAULT 0.0,
            green_time        INTEGER DEFAULT 0,
            reason            TEXT DEFAULT 'weighted',
            hour              INTEGER,
            day_of_week       INTEGER,
            timestamp         TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type  TEXT,
            direction   TEXT,
            details     TEXT,
            timestamp   TEXT DEFAULT (datetime('now'))
        )
    """)

    connection.commit()
    connection.close()
    print("[DB] Tables ready.")
