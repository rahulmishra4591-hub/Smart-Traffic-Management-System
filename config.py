import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # YOLO
    yolo_model: str = "yolov8s.pt"
    confidence_threshold: float = 0.3

    # Signal timing
    min_green_time: int = 10
    max_green_time: int = 60
    seconds_per_vehicle: float = 2.0
    starvation_limit: int = 90

    # Server
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# Each "camera" is a video file for the demo. In production these become
# RTSP URLs, e.g. rtsp://admin:password@192.168.1.100:554/stream1
CAMERAS = {
    "north": os.environ.get("CAM_NORTH", "north.mp4"),
    "south": os.environ.get("CAM_SOUTH", "south.mp4"),
    "east":  os.environ.get("CAM_EAST",  "east.mp4"),
    "west":  os.environ.get("CAM_WEST",  "west.mp4"),
}
