"""
Run with: python app.py

Starts one detection thread per camera, one thread for the signal
optimizer loop, then the FastAPI server in the main thread. Everything
runs in a single process sharing memory through api.state - no Redis or
separate cache needed for live state (SQLite is used only for the
analytics history, not for the live signal decisions).
"""

import threading
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import CAMERAS, settings
from detection.yolo_detector import VehicleDetector
from core.signal_optimizer import SignalOptimizer
from core.camera_worker import camera_loop, optimizer_loop
from database.db import create_tables
from database.fallback import FallbackController
from api.state import shared
from api.routes import router as rest_router
from api.websocket import router as websocket_router


def start_background_workers():
    print("Loading YOLO model...")
    detector = VehicleDetector()

    shared.optimizer = SignalOptimizer(
        min_green=settings.min_green_time,
        max_green=settings.max_green_time,
        seconds_per_weight=settings.seconds_per_vehicle,
        starvation_limit=settings.starvation_limit,
    )
    shared.fallback = FallbackController(stale_threshold=30)

    create_tables()
    print("YOLO ready!\n")

    model_lock = threading.Lock()  # only one thread may call the model at a time
    directions = list(CAMERAS.keys())

    for direction, path in CAMERAS.items():
        threading.Thread(
            target=camera_loop, args=(direction, path, detector, model_lock), daemon=True
        ).start()

    threading.Thread(target=optimizer_loop, args=(directions,), daemon=True).start()

    print(f"Detection running. Open: http://localhost:{settings.app_port}/dashboard\n")


def create_app() -> FastAPI:
    app = FastAPI(title="Smart Traffic Management System")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(rest_router)
    app.include_router(websocket_router)
    return app


app = create_app()


if __name__ == "__main__":
    print("=" * 55)
    print("  Smart Traffic Management System")
    print("=" * 55 + "\n")

    start_background_workers()
    uvicorn.run(app, host=settings.app_host, port=settings.app_port)
