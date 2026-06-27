"""
Picks one direction to go green at a time and decides how long, based on
queue weight. Handles three layers of priority: emergency override beats
everything, manual override pins a fixed duration, otherwise the
algorithm picks by congestion with a starvation guard so a quiet
direction can't get skipped forever.
"""

import time


class SignalOptimizer:
    def __init__(
        self,
        min_green: int = 10,
        max_green: int = 60,
        seconds_per_weight: float = 2.0,
        starvation_limit: int = 90,
    ):
        self.min_green = min_green
        self.max_green = max_green
        self.seconds_per_weight = seconds_per_weight
        self.starvation_limit = starvation_limit

        self.active_direction: str | None = None
        self.green_until: float = 0.0
        self.last_green_time: dict[str, float] = {}
        self.manual_overrides: dict[str, int] = {}
        self.emergency: str | None = None

    def set_emergency(self, direction: str | None):
        self.emergency = direction
        if direction:
            self.active_direction = direction
            self.green_until = time.time() + self.max_green

    def set_manual_override(self, direction: str, green_time: int):
        self.manual_overrides[direction] = green_time

    def clear_manual_overrides(self, weighted_counts: dict[str, float] | None = None):
        """Clears overrides and, if live counts are given, re-picks immediately
        instead of waiting for the current cycle to expire."""
        self.manual_overrides.clear()

        if weighted_counts:
            next_dir = self._pick_next(weighted_counts)
            self.active_direction = next_dir
            self.last_green_time[next_dir] = time.time()
            self.green_until = time.time() + self._green_time_for(next_dir, weighted_counts[next_dir])
        else:
            self.active_direction = None
            self.green_until = 0.0

    def _green_time_for(self, direction: str, weighted_count: float) -> int:
        if direction in self.manual_overrides:
            return self.manual_overrides[direction]
        gt = self.min_green + int(weighted_count * self.seconds_per_weight)
        return max(self.min_green, min(self.max_green, gt))

    def _pick_next(self, weighted_counts: dict[str, float]) -> str:
        now = time.time()
        starved, longest_wait = None, 0.0

        for direction, last_green in self.last_green_time.items():
            waited = now - last_green
            if waited >= self.starvation_limit and waited > longest_wait:
                starved, longest_wait = direction, waited

        if starved:
            return starved
        return max(weighted_counts, key=lambda d: weighted_counts[d])

    def compute(self, weighted_counts: dict[str, float]) -> dict[str, dict]:
        now = time.time()
        directions = list(weighted_counts.keys())

        for i, direction in enumerate(directions):
            self.last_green_time.setdefault(direction, now - i * 15)

        if self.emergency and self.emergency in directions:
            result = {}
            for direction in directions:
                if direction == self.emergency:
                    remaining = max(0, int(self.green_until - now))
                    result[direction] = {"green_time": remaining or self.max_green,
                                          "state": "green", "reason": "emergency"}
                else:
                    result[direction] = {"green_time": 0, "state": "red", "reason": "emergency_hold"}
            return result

        if self.active_direction is None or now >= self.green_until:
            next_dir = self._pick_next(weighted_counts)
            self.active_direction = next_dir
            self.last_green_time[next_dir] = now
            self.green_until = now + self._green_time_for(next_dir, weighted_counts[next_dir])

        remaining = max(0, int(self.green_until - now))
        result = {}
        for direction in directions:
            if direction == self.active_direction:
                result[direction] = {
                    "green_time": remaining, "state": "green",
                    "reason": "manual" if direction in self.manual_overrides else "weighted",
                }
            else:
                result[direction] = {"green_time": remaining, "state": "red", "reason": "waiting"}

        return result
