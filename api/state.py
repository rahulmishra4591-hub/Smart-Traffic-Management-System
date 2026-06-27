"""
One shared object holding all live state, guarded by a single lock.

Earlier iterations of this used module-level globals with the `global`
keyword sprinkled across functions, which led to several subtle bugs
where a reassignment in one place wasn't visible elsewhere. Wrapping
everything in one instance and mutating its attributes avoids that class
of bug entirely.
"""

import threading


class SharedState:
    def __init__(self):
        self.lock = threading.Lock()

        self.current_signals = {
            d: {"green_time": 10, "state": "red", "reason": "init"}
            for d in ("north", "south", "east", "west")
        }

        self.current_congestion = {
            d: {"incoming": 0, "weighted": 0.0, "congestion_score": 0.0, "queue_count": 0}
            for d in ("north", "south", "east", "west")
        }

        self.trend_history = {d: [] for d in ("north", "south", "east", "west")}
        self.MAX_TREND_POINTS = 20

        self.latest_jpeg = {d: None for d in ("north", "south", "east", "west")}
        self.emergency_direction: str | None = None

        # set once detection starts (see core.camera_worker / app.py)
        self.optimizer = None
        self.fallback = None


shared = SharedState()
