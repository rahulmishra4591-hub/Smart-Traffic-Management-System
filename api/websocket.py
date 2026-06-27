import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.state import shared

router = APIRouter()


@router.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            with shared.lock:
                payload = {
                    "signals": shared.current_signals,
                    "congestion": shared.current_congestion,
                    "emergency": shared.emergency_direction,
                    "trends": shared.trend_history,
                    "fallback_mode": shared.fallback.mode if shared.fallback else "realtime",
                    "failed_cameras": list(shared.fallback.failed_directions) if shared.fallback else [],
                }
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
