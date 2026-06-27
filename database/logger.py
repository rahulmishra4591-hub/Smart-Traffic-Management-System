from datetime import datetime
from database.db import get_connection


def log_detection(direction, incoming_count, weighted_count, congestion_score, green_time, reason):
    now = datetime.now()
    connection = get_connection()
    try:
        connection.execute(
            """INSERT INTO detection_log
               (direction, incoming_count, weighted_count, congestion_score, green_time, reason, hour, day_of_week)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (direction, incoming_count, round(weighted_count, 2), round(congestion_score, 2),
             green_time, reason, now.hour, now.weekday()),
        )
        connection.commit()
    finally:
        connection.close()


def log_event(event_type: str, direction: str | None = None, details: str | None = None):
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO system_events (event_type, direction, details) VALUES (?, ?, ?)",
            (event_type, direction, details),
        )
        connection.commit()
    finally:
        connection.close()
