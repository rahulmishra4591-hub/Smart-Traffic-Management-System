"""
Tracks two separate counts per camera:

- crossing count: a vehicle is counted once when it crosses a thin
  reference line moving toward the intersection. Good for throughput
  analytics, but drops to zero whenever a red light stops traffic before
  it reaches the line - so it's a poor signal for "how congested is this
  road right now".

- queue count: every vehicle currently sitting inside a wider approach
  zone, moving or not. Stays accurate during a red phase, which is why
  the signal optimizer uses this one to decide timing.
"""

from detection.yolo_detector import DetectedVehicle


class CongestionCounter:
    def __init__(self, direction: str, line_pos: float = 0.55, zone_height: int = 20):
        self.direction = direction
        self.line_pos = line_pos
        self.zone_height = zone_height

        self.track_history: dict[int, list[int]] = {}
        self.counted_ids: set[int] = set()
        self.outgoing_ids: set[int] = set()
        self.vehicle_directions: dict[int, str] = {}

        self.incoming_count = 0
        self.incoming_weight = 0.0
        self.queue_count = 0
        self.queue_weight = 0.0

    def get_line_y(self, frame_height: int) -> int:
        return int(frame_height * self.line_pos)

    def get_zone(self, frame_height: int) -> tuple[int, int]:
        line_y = self.get_line_y(frame_height)
        return line_y - self.zone_height, line_y + self.zone_height

    def get_approach_zone(self, frame_height: int) -> tuple[int, int]:
        return int(frame_height * 0.40), int(frame_height * 0.75)

    def get_vehicle_direction(self, track_id: int) -> str:
        return self.vehicle_directions.get(track_id, "unknown")

    def update(self, vehicles: list[DetectedVehicle], frame_height: int):
        zone_top, zone_bot = self.get_zone(frame_height)
        approach_top, approach_bot = self.get_approach_zone(frame_height)

        queue_count = 0
        queue_weight = 0.0

        for vehicle in vehicles:
            track_id = vehicle.track_id
            cy = vehicle.center_y

            if approach_top <= cy <= approach_bot:
                queue_count += 1
                queue_weight += vehicle.weight

            if track_id == -1:
                continue

            if track_id not in self.track_history:
                self.track_history[track_id] = [cy]
                continue

            history = self.track_history[track_id]
            history.append(cy)
            if len(history) > 5:
                history.pop(0)

            avg_recent = sum(history[:-1]) / len(history[:-1])
            moving_in = cy > avg_recent
            self.vehicle_directions[track_id] = "incoming" if moving_in else "outgoing"

            on_line = zone_top <= cy <= zone_bot
            already_handled = track_id in self.counted_ids or track_id in self.outgoing_ids

            if on_line and not already_handled:
                if moving_in:
                    self.counted_ids.add(track_id)
                    self.incoming_count += 1
                    self.incoming_weight += vehicle.weight
                else:
                    self.outgoing_ids.add(track_id)

        self.queue_count = queue_count
        self.queue_weight = queue_weight
        return self.incoming_count, self.incoming_weight

    def reset_count(self):
        """Called when a looping demo video restarts, so counts don't carry over."""
        self.incoming_count = 0
        self.incoming_weight = 0.0
        self.counted_ids.clear()
        self.outgoing_ids.clear()
