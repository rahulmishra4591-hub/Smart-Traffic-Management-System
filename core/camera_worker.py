"""
Two background loops:

camera_loop - one per direction. Reads frames at the video's own pace, but
only runs YOLO every DETECTION_INTERVAL seconds rather than every frame -
inference is too slow on CPU to keep up with full frame rate, and vehicle
counts don't change meaningfully within a fraction of a second anyway.

optimizer_loop - one for the whole system. Every 5s, pulls live congestion,
applies fallback substitution for any stale camera, asks the optimizer for
a decision, and logs the result.
"""

import cv2
import time
import threading

from detection.congestion_counter import CongestionCounter
from core.frame_renderer import draw_frame, encode_jpeg
from database.logger import log_detection
from api.state import shared

MAX_CONGESTION_WEIGHT = 20.0
DETECTION_INTERVAL = 0.5


def camera_loop(direction: str, video_path: str, detector, model_lock: threading.Lock):
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        print(f"ERROR: Cannot open {video_path} — marking {direction} as failed")
        with shared.lock:
            shared.fallback.failed_directions.add(direction)
            shared.fallback.last_active_time[direction] = 0
        return

    print(f"Opened: {direction}")
    counter = CongestionCounter(direction)
    fps = capture.get(cv2.CAP_PROP_FPS) or 25
    frame_delay = 1.0 / fps

    last_detect_time = 0.0
    last_vehicles = []

    while True:
        loop_start = time.time()

        success, frame = capture.read()
        if not success:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            counter.reset_count()
            continue

        frame = cv2.resize(frame, (640, 360))
        height = frame.shape[0]

        now = time.time()
        if now - last_detect_time >= DETECTION_INTERVAL:
            with model_lock:
                last_vehicles = detector.detect_and_track(frame)
            counter.update(last_vehicles, height)
            last_detect_time = now

        queue_score = min(1.0, counter.queue_weight / MAX_CONGESTION_WEIGHT)

        with shared.lock:
            shared.current_congestion[direction] = {
                "incoming": counter.incoming_count,
                "weighted": round(counter.queue_weight, 2),
                "congestion_score": round(queue_score, 2),
                "queue_count": counter.queue_count,
            }
            signal_snapshot = dict(shared.current_signals[direction])

            trend = shared.trend_history[direction]
            trend.append(round(queue_score, 2))
            if len(trend) > shared.MAX_TREND_POINTS:
                trend.pop(0)

        frame = draw_frame(frame, direction, last_vehicles, counter,
                            shared.current_congestion[direction], signal_snapshot)

        with shared.lock:
            shared.latest_jpeg[direction] = encode_jpeg(frame)

        elapsed = time.time() - loop_start
        remaining = frame_delay - elapsed
        if remaining > 0:
            time.sleep(remaining)


def optimizer_loop(directions: list[str]):
    last_logged_incoming = {d: 0 for d in directions}

    while True:
        time.sleep(5)

        with shared.lock:
            weighted_counts = {d: shared.current_congestion[d]["weighted"] for d in directions}

        for d in directions:
            shared.fallback.update(d, shared.current_congestion[d]["incoming"])

        final_counts, mode = shared.fallback.get_weighted_counts(weighted_counts)
        new_signals = shared.optimizer.compute(final_counts)

        with shared.lock:
            shared.current_signals = new_signals

        for d in directions:
            with shared.lock:
                congestion = shared.current_congestion[d]
                signal = shared.current_signals.get(d, {})

            # log the delta, not the running total, or analytics inflate over a long session
            delta = max(0, congestion["incoming"] - last_logged_incoming[d])
            last_logged_incoming[d] = congestion["incoming"]

            if delta > 0 or congestion["congestion_score"] > 0:
                log_detection(
                    direction=d,
                    incoming_count=delta,
                    weighted_count=congestion["weighted"],
                    congestion_score=congestion["congestion_score"],
                    green_time=signal.get("green_time", 0),
                    reason=signal.get("reason", "weighted"),
                )

        print(
            f"\r[{mode}] "
            f"N:{shared.current_congestion['north']['congestion_score']:.2f} "
            f"S:{shared.current_congestion['south']['congestion_score']:.2f} "
            f"E:{shared.current_congestion['east']['congestion_score']:.2f} "
            f"W:{shared.current_congestion['west']['congestion_score']:.2f}  "
            f"Green — "
            f"N:{shared.current_signals['north']['green_time']}s "
            f"S:{shared.current_signals['south']['green_time']}s "
            f"E:{shared.current_signals['east']['green_time']}s "
            f"W:{shared.current_signals['west']['green_time']}s",
            end="",
        )
