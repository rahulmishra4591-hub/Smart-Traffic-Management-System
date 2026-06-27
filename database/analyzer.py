from datetime import datetime, timedelta
from database.db import get_connection

TS_FORMAT = "%Y-%m-%d %H:%M:%S"
DIRECTIONS = ("north", "south", "east", "west")


_PERIOD_DAYS = {"week": 7, "month": 30, "year": 365}


def _date_filter(period: str) -> tuple[str, list]:
    now = datetime.now()

    if period == "today":
        cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return "timestamp >= ?", [cutoff.strftime(TS_FORMAT)]

    if period == "yesterday":
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
        return "timestamp >= ? AND timestamp < ?", [start.strftime(TS_FORMAT), end.strftime(TS_FORMAT)]

    if period in _PERIOD_DAYS:
        cutoff = now - timedelta(days=_PERIOD_DAYS[period])
        return "timestamp >= ?", [cutoff.strftime(TS_FORMAT)]

    # "hour" and any unrecognised value default to the last 60 minutes
    cutoff = now - timedelta(hours=1)
    return "timestamp >= ?", [cutoff.strftime(TS_FORMAT)]


def get_analytics_by_period(period: str = "hour") -> dict:
    connection = get_connection()
    where_clause, params = _date_filter(period)

    try:
        direction_rows = connection.execute(f"""
            SELECT direction,
                   COUNT(*) AS records,
                   AVG(congestion_score) AS avg_congestion,
                   MAX(congestion_score) AS peak_congestion,
                   AVG(incoming_count) AS avg_incoming,
                   SUM(incoming_count) AS total_incoming,
                   SUM(weighted_count) AS total_weight,
                   AVG(green_time) AS avg_green_time
            FROM detection_log
            WHERE {where_clause}
            GROUP BY direction
        """, params).fetchall()

        total_records = connection.execute(
            f"SELECT COUNT(*) AS c FROM detection_log WHERE {where_clause}", params
        ).fetchone()["c"]

        peak_hours = {}
        for direction in DIRECTIONS:
            rows = connection.execute(f"""
                SELECT hour, AVG(congestion_score) AS avg_score
                FROM detection_log
                WHERE direction = ? AND {where_clause}
                GROUP BY hour ORDER BY avg_score DESC LIMIT 3
            """, [direction] + params).fetchall()
            peak_hours[direction] = [
                {"hour": r["hour"], "avg_score": round(r["avg_score"] or 0, 3)} for r in rows
            ]
    finally:
        connection.close()

    directions = {}
    for row in direction_rows:
        d = row["direction"]
        directions[d] = {
            "records": row["records"],
            "avg_congestion": round(row["avg_congestion"] or 0, 3),
            "peak_congestion": round(row["peak_congestion"] or 0, 3),
            "avg_incoming": round(row["avg_incoming"] or 0, 1),
            "total_incoming": row["total_incoming"] or 0,
            "total_weight": round(row["total_weight"] or 0, 1),
            "avg_green_time": round(row["avg_green_time"] or 0, 1),
            "peak_hours": peak_hours.get(d, []),
        }

    return {"period": period, "total_records": total_records, "directions": directions}


def get_historical_pattern(hour: int, day_of_week: int) -> dict[str, float]:
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT direction, AVG(congestion_score) AS avg_score FROM detection_log "
            "WHERE hour = ? AND day_of_week = ? GROUP BY direction",
            (hour, day_of_week),
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        return {d: 0.25 for d in DIRECTIONS}
    return {row["direction"]: round(row["avg_score"], 3) for row in rows}


def has_enough_data(minimum_records: int = 50) -> bool:
    connection = get_connection()
    try:
        count = connection.execute("SELECT COUNT(*) AS c FROM detection_log").fetchone()["c"]
    finally:
        connection.close()
    return count >= minimum_records
