"""
If a direction reports zero incoming vehicles for longer than
stale_threshold seconds, we assume the camera (not the road) is the
problem and substitute a historical congestion estimate for that
direction instead of treating it as genuinely empty - otherwise a failed
camera's direction would starve indefinitely.
"""

import time
from datetime import datetime
from database.analyzer import get_historical_pattern, has_enough_data
from database.logger import log_event


class FallbackController:
    def __init__(self, stale_threshold: int = 30):
        self.stale_threshold = stale_threshold
        now = time.time()
        self.last_active_time = {d: now for d in ("north", "south", "east", "west")}
        self.failed_directions: set[str] = set()
        self.mode = "realtime"

    def update(self, direction: str, incoming_count: int):
        if incoming_count > 0:
            self.last_active_time[direction] = time.time()
            if direction in self.failed_directions:
                self.failed_directions.discard(direction)
                log_event("camera_restored", direction, f"{direction} camera restored")
                print(f"\n[Fallback] {direction} camera restored")

    def check_failures(self) -> set[str]:
        now = time.time()
        for direction, last_seen in self.last_active_time.items():
            if now - last_seen > self.stale_threshold and direction not in self.failed_directions:
                self.failed_directions.add(direction)
                log_event("camera_fail", direction, f"{direction} camera stale for {self.stale_threshold}s")
                print(f"\n[Fallback] {direction} camera may have failed — using historical data")
        return self.failed_directions

    def get_weighted_counts(self, live_counts: dict[str, float]) -> tuple[dict[str, float], str]:
        failed = self.check_failures()
        if not failed:
            return live_counts, "realtime"

        now = datetime.now()
        if not has_enough_data():
            # no history yet — use a neutral weight rather than guessing
            merged = {d: (5.0 if d in failed else live_counts[d]) for d in live_counts}
        else:
            historical = get_historical_pattern(now.hour, now.weekday())
            merged = {
                d: (historical.get(d, 0.25) * 20.0 if d in failed else live_counts[d])
                for d in live_counts
            }

        mode = "full_fallback" if len(failed) == len(live_counts) else "partial_fallback"
        if mode != self.mode:
            self.mode = mode
            log_event(f"mode_switch_{mode}", details=f"Failed: {list(failed)}")

        return merged, mode
