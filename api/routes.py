import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, FileResponse

from api.state import shared
from config import CAMERAS
from database.analyzer import get_analytics_by_period

router = APIRouter()


@router.get("/")
def root():
    return {"message": "Smart Traffic Management System", "docs": "/docs"}


@router.get("/dashboard")
def dashboard():
    return FileResponse("dashboard/index.html")


@router.get("/api/status")
def get_status():
    with shared.lock:
        return {
            "signals": shared.current_signals,
            "congestion": shared.current_congestion,
            "emergency": shared.emergency_direction,
            "trends": shared.trend_history,
        }


@router.post("/api/emergency")
def set_emergency(direction: str | None = None):
    shared.emergency_direction = direction
    shared.optimizer.set_emergency(direction)
    return {"message": f"Emergency set to: {direction}"}


@router.post("/api/override")
def override_signal(direction: str, green_time: int):
    shared.optimizer.set_manual_override(direction, green_time)
    return {"message": "Override applied", "direction": direction, "green_time": green_time}


@router.post("/api/override/reset")
def reset_overrides():
    with shared.lock:
        weighted_counts = {d: shared.current_congestion[d]["weighted"] for d in CAMERAS}
    shared.optimizer.clear_manual_overrides(weighted_counts)
    return {"message": "Reset to automatic — re-evaluating now"}


@router.get("/api/analytics")
def get_analytics(period: str = "hour"):
    return get_analytics_by_period(period)


async def _mjpeg_stream(direction: str):
    while True:
        with shared.lock:
            jpeg_bytes = shared.latest_jpeg.get(direction)
        if jpeg_bytes is not None:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n"
        await asyncio.sleep(0.033)


@router.get("/video/{direction}")
async def video_feed(direction: str):
    return StreamingResponse(_mjpeg_stream(direction), media_type="multipart/x-mixed-replace; boundary=frame")
