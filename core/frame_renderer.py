"""Draws the zones, vehicle boxes and stats panel onto a frame, then encodes to JPEG."""

import cv2

INCOMING_COLOR = (0, 255, 0)
OUTGOING_COLOR = (0, 0, 255)
LINE_COLOR = (0, 255, 255)


def encode_jpeg(frame) -> bytes:
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return buffer.tobytes()


def draw_frame(frame, direction, vehicles, counter, congestion, signal):
    height, width = frame.shape[:2]
    zone_top, zone_bot = counter.get_zone(height)
    approach_top, approach_bot = counter.get_approach_zone(height)

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, approach_top), (width, approach_bot), (255, 100, 0), -1)
    cv2.addWeighted(overlay, 0.08, frame, 0.92, 0, frame)
    cv2.putText(frame, "APPROACH ZONE (queue)", (10, approach_top + 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 150, 0), 1)

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, zone_top), (width, zone_bot), (0, 255, 255), -1)
    cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
    cv2.line(frame, (0, counter.get_line_y(height)), (width, counter.get_line_y(height)), LINE_COLOR, 2)
    cv2.putText(frame, "COUNTING LINE (throughput)", (10, zone_top - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, LINE_COLOR, 1)

    for vehicle in vehicles:
        moving = counter.get_vehicle_direction(vehicle.track_id)
        color = INCOMING_COLOR if moving == "incoming" else OUTGOING_COLOR
        arrow = "↓" if moving == "incoming" else "↑"
        cv2.rectangle(frame, (vehicle.x1, vehicle.y1), (vehicle.x2, vehicle.y2), color, 2)
        cv2.putText(frame, f"ID:{vehicle.track_id} {vehicle.vehicle_type} {arrow}",
                    (vehicle.x1, vehicle.y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1)

    cv2.rectangle(frame, (0, 0), (280, 105), (0, 0, 0), -1)
    cv2.putText(frame, direction.upper(), (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(frame, f"Queue: {congestion.get('queue_count', 0)} | Crossed: {congestion['incoming']}",
                (8, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.48, INCOMING_COLOR, 1)
    cv2.putText(frame, f"Congestion: {congestion['congestion_score']:.2f}/1.0",
                (8, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1)

    bar_w = int(260 * congestion["congestion_score"])
    bar_color = (
        (0, 255, 0) if congestion["congestion_score"] < 0.5 else
        (0, 165, 255) if congestion["congestion_score"] < 0.8 else
        (0, 0, 255)
    )
    cv2.rectangle(frame, (8, 78), (270, 93), (50, 50, 50), -1)
    cv2.rectangle(frame, (8, 78), (8 + bar_w, 93), bar_color, -1)

    green_time = signal.get("green_time", 10)
    reason = signal.get("reason", "")
    is_green = reason != "emergency_hold"
    signal_color = (0, 255, 0) if is_green else (0, 0, 255)
    signal_text = f"GREEN {green_time}s [{reason}]" if is_green else f"RED [{reason}]"

    cv2.rectangle(frame, (0, height - 35), (width, height), (0, 0, 0), -1)
    cv2.putText(frame, signal_text, (8, height - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, signal_color, 2)

    return frame
