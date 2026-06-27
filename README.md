# Smart Traffic Management System

Real-time, multi-camera traffic signal control: YOLOv8 detects and tracks
vehicles per direction, a queue-based congestion score drives signal
timing, and a FastAPI backend serves a live dashboard over WebSocket.

## Architecture

```
4 camera feeds (video files / RTSP)
        │
        ▼
YOLOv8 + ByteTrack  ──►  CongestionCounter (queue + crossing counts)
        │
        ▼
SignalOptimizer  ◄──  FallbackController (historical data if a camera goes stale)
        │
        ▼
FastAPI  ──►  WebSocket  ──►  Dashboard (live video, controls, analytics)
        │
        ▼
   SQLite (history for analytics + fallback)
```

Everything runs in a single Python process: one thread per camera, one
thread for the signal-timing loop, and the web server in the main thread.
They share state directly through `api/state.py` - no Redis or message
queue needed at this scale.

## Project layout

```
config.py                  settings + camera sources
app.py                     entry point - starts workers + FastAPI

detection/
  yolo_detector.py         YOLOv8 + ByteTrack wrapper
  congestion_counter.py    queue count (drives timing) vs crossing count (analytics)

core/
  signal_optimizer.py      picks which direction goes green, and for how long
  camera_worker.py         per-camera detection loop + the optimizer scheduling loop
  frame_renderer.py        draws zones/boxes/stats onto each frame

api/
  state.py                 single shared state object, thread-safe via one lock
  routes.py                REST endpoints + MJPEG video streaming
  websocket.py             pushes live state to the dashboard every second

database/
  db.py                    SQLite connection + schema
  logger.py                writes detection logs / system events
  analyzer.py              analytics queries for the dashboard
  fallback.py              swaps in historical data when a camera looks stale

dashboard/index.html       live monitor, manual controls, analytics
```

## Why queue count, not just crossing count

Counting vehicles only as they cross a line near the stop point works
fine while traffic is moving, but during a red phase, vehicles queue up
and never cross - so a naive crossing count reports "zero congestion"
on the most jammed direction. `CongestionCounter` also tracks a wider
"approach zone" and counts every vehicle present in it, moving or not.
That queue weight is what `SignalOptimizer` actually uses to decide
timing; the crossing count is kept only for throughput analytics.

## Why detection runs slower than video playback

Running YOLO on every frame is too slow for live playback on a CPU.
`camera_worker.py` decouples the two: frames are read and displayed close
to the video's native frame rate, while detection samples the latest
frame on a fixed interval (every ~0.5s). Vehicle counts don't change
meaningfully within that window, so this keeps the demo watchable
without sacrificing measurement accuracy.

## Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Place four traffic videos in the project root named `north.mp4`,
`south.mp4`, `east.mp4`, `west.mp4` (or set `CAM_NORTH` etc. in `.env` to
RTSP URLs for a real deployment).

## Run

```bash
python app.py
```

Open `http://localhost:8000/dashboard`.

## Known limitations

- Detection runs on CPU at a sampled rate, not full frame rate - fine for
  a demo, but a production deployment would need GPU or edge inference
  hardware for true real-time throughput.
- Zone boundaries (`congestion_counter.py`) are fixed fractions of frame
  height, tuned for these specific demo videos - a real deployment needs
  per-camera calibration.
- Occlusion (one vehicle blocking another from view) causes undercounting,
  worse from ground-level camera angles than overhead ones.
- This models a single intersection with no turn lanes or pedestrian
  phases; multi-intersection coordination (green waves) is out of scope.
