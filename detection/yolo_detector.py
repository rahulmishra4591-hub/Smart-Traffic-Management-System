"""YOLOv8 + ByteTrack wrapper. Turns raw model output into DetectedVehicle objects."""

from dataclasses import dataclass
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


@dataclass
class DetectedVehicle:
    vehicle_type: str
    confidence: float
    x1: int
    y1: int
    x2: int
    y2: int
    track_id: int = -1   # -1 if the tracker couldn't assign an id this frame
    weight: float = 1.0  # relative road-space impact, feeds the signal algorithm

    @property
    def center_x(self) -> int:
        return (self.x1 + self.x2) // 2

    @property
    def center_y(self) -> int:
        return (self.y1 + self.y2) // 2


# COCO class id -> (label, congestion weight). Weights are a rough skew for
# Indian traffic (lots of two-wheelers; COCO has no separate auto-rickshaw class).
VEHICLE_CLASSES = {
    1: ("bicycle", 0.3),
    2: ("car", 1.0),
    3: ("motorcycle", 0.5),
    5: ("bus", 2.5),
    7: ("truck", 2.0),
}


class VehicleDetector:
    """Loads the model once; call detect_and_track() per frame."""

    def __init__(self, model_path: str | None = None):
        from ultralytics import YOLO

        path = model_path or settings.yolo_model
        print(f"[VehicleDetector] Loading YOLO model: {path}")
        self.model = YOLO(path)
        self.confidence_threshold = settings.confidence_threshold
        print("[VehicleDetector] Ready.")

    def detect_and_track(self, frame) -> list[DetectedVehicle]:
        results = self.model.track(
            frame, persist=True, verbose=False, tracker="bytetrack.yaml"
        )

        vehicles: list[DetectedVehicle] = []
        if results[0].boxes.id is None:
            return vehicles

        for box in results[0].boxes:
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])

            if class_id not in VEHICLE_CLASSES or confidence < self.confidence_threshold:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            track_id = int(box.id[0]) if box.id is not None else -1
            label, weight = VEHICLE_CLASSES[class_id]

            vehicles.append(DetectedVehicle(
                vehicle_type=label, confidence=confidence,
                x1=x1, y1=y1, x2=x2, y2=y2,
                track_id=track_id, weight=weight,
            ))

        return vehicles
