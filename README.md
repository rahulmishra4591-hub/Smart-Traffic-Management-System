# 🚦 Smart Traffic Management System

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-purple)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?logo=opencv&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

Real-time, multi-camera traffic signal optimization. YOLOv8 detects and
tracks vehicles per direction, a queue-based congestion score drives
signal timing, and a FastAPI backend serves a live dashboard over
WebSocket — no real intersection hardware required to try it.

---

## Demo

> Add a screen recording or GIF of the dashboard here before sharing the repo —
> a 15-second clip of the Live Monitor tab is the single most convincing thing
> in this README.

## Features

- **Multi-camera coordination** — four independent video feeds (or RTSP
  streams) processed in parallel, one direction green at a time
- **Queue-based congestion detection** — counts vehicles physically
  waiting in an approach zone, not just ones crossing a line, so a red
  light correctly shows as congested instead of empty
- **Starvation prevention** — no direction can be skipped indefinitely
- **Manual + emergency override** — operator control from the dashboard,
  with one click back to automatic
- **Historical fallback** — if a camera goes stale, that direction falls
  back to a historical average instead of reporting zero traffic
- **Live analytics** — congestion trends, peak hours, and totals by hour
  /day/week/month/year, backed by SQLite

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

Runs as a single process: one thread per camera, one thread for the
signal-timing loop, the web server in the main thread — sharing state
through `api/state.py`, no Redis or message queue required at this scale.

## Project layout

```
config.py / app.py          settings + entry point
detection/                   YOLOv8 wrapper, queue/crossing counting
core/                        signal timing algorithm, camera loop, rendering
api/                         shared state, REST routes, WebSocket
database/                    SQLite storage, analytics queries, fallback logic
dashboard/index.html         live monitor, manual controls, analytics
```

## Getting started

```bash
git clone https://github.com/rahulmishra4591-hub/Smart-Traffic-Management-System.git
cd Smart-Traffic-Management-System

python -m venv venv
venv\Scripts\activate            # Windows
pip install -r requirements.txt
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Add four traffic videos to the project root named `north.mp4`,
`south.mp4`, `east.mp4`, `west.mp4` — any traffic footage works (try
[Pexels](https://www.pexels.com/search/videos/traffic/)). To use your
own filenames or real RTSP cameras, set `CAM_NORTH` / `CAM_SOUTH` /
`CAM_EAST` / `CAM_WEST` as environment variables (see `.env.example`).

```bash
python app.py
```

Open `http://localhost:8000/dashboard`.

## Why queue count, not just crossing count

Counting vehicles only as they cross a line near the stop point works
while traffic is moving, but during a red phase vehicles queue up and
never cross — so a naive crossing count reports "zero congestion" on the
most jammed direction. `CongestionCounter` also tracks a wider approach
zone and counts every vehicle present in it, moving or not. That queue
weight is what `SignalOptimizer` actually uses to decide timing; the
crossing count is kept only for throughput analytics.

## Why detection runs slower than video playback

Running YOLO on every frame is too slow for live playback on CPU.
`camera_worker.py` decouples the two: frames are read and displayed close
to the video's native frame rate, while detection samples the latest
frame on a fixed interval (~0.5s). Vehicle counts don't change
meaningfully within that window, so this keeps the demo watchable
without sacrificing measurement accuracy.

## Known limitations

- Detection runs on CPU at a sampled rate, not full frame rate — a
  production deployment would need GPU or edge inference hardware for
  true real-time throughput
- The approach zone is a fixed fraction of frame height, tuned for the
  demo videos — a real deployment needs per-camera calibration, or a
  motion-based (stopped vs. moving) approach instead of a fixed zone
- Occlusion causes undercounting, worse from ground-level camera angles
  than overhead ones
- Models a single intersection with no turn lanes or pedestrian phases;
  multi-intersection coordination (green waves) is out of scope

## License

MIT — see [LICENSE](LICENSE).
