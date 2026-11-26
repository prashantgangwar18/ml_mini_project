import math
from datetime import datetime

WEATHER_MAP = {
    "Clear": 0,
    "Cloudy": 1,
    "Rain": 2,
    "Fog": 3,
}

TRAFFIC_MAP = {
    "Low": 0,
    "Moderate": 1,
    "Heavy": 2,
}

LATE_CLASS_NAMES = {
    0: "On Time",
    1: "Slightly Late",
    2: "Late",
}

FEATURE_COLUMNS = [
    "route_id",
    "remaining_route_km",
    "haversine_to_stop_km",
    "stops_remaining",
    "progress_ratio",
    "current_speed_kmh",
    "rolling_speed_kmh",
    "schedule_deviation_so_far_min",
    "scheduled_remaining_min",
    "hour_sin",
    "hour_cos",
    "day_of_week",
    "is_weekend",
    "is_rush_hour",
    "weather_code",
    "traffic_code",
    "occupancy_pct",
]


def classify_delay(delay_min: float) -> tuple[int, str]:
    """Map delay minutes to class id and human-readable status."""
    if delay_min <= 2.0:
        return 0, LATE_CLASS_NAMES[0]
    if delay_min <= 7.0:
        return 1, LATE_CLASS_NAMES[1]
    return 2, LATE_CLASS_NAMES[2]


def is_rush_hour_dt(ts: datetime) -> int:
    """Return 1 during peak college morning/evening commute windows."""
    minutes = ts.hour * 60 + ts.minute
    morning = 7 * 60 + 30 <= minutes <= 9 * 60 + 45
    evening = 16 * 60 + 30 <= minutes <= 18 * 60 + 30
    return 1 if (morning or evening) else 0


def build_feature_dict(
    *,
    route_id: int,
    remaining_route_km: float,
    haversine_to_stop_km: float,
    stops_remaining: int,
    progress_ratio: float,
    current_speed_kmh: float,
    rolling_speed_kmh: float,
    schedule_deviation_so_far_min: float,
    scheduled_remaining_min: float,
    timestamp: datetime,
    weather: str,
    traffic_level: str,
    occupancy_pct: float,
) -> dict[str, float]:
    """Build a deterministic feature dictionary shared by training and inference."""
    hour_frac = timestamp.hour + timestamp.minute / 60.0
    angle = 2.0 * math.pi * (hour_frac / 24.0)
    dow = timestamp.weekday()

    return {
        "route_id": float(route_id),
        "remaining_route_km": float(max(0.0, remaining_route_km)),
        "haversine_to_stop_km": float(max(0.0, haversine_to_stop_km)),
        "stops_remaining": float(max(0, stops_remaining)),
        "progress_ratio": float(max(0.0, min(1.0, progress_ratio))),
        "current_speed_kmh": float(max(0.0, current_speed_kmh)),
        "rolling_speed_kmh": float(max(0.0, rolling_speed_kmh)),
        "schedule_deviation_so_far_min": float(schedule_deviation_so_far_min),
        "scheduled_remaining_min": float(scheduled_remaining_min),
        "hour_sin": math.sin(angle),
        "hour_cos": math.cos(angle),
        "day_of_week": float(dow),
        "is_weekend": 1.0 if dow >= 5 else 0.0,
        "is_rush_hour": float(is_rush_hour_dt(timestamp)),
        "weather_code": float(WEATHER_MAP.get(weather, 0)),
        "traffic_code": float(TRAFFIC_MAP.get(traffic_level, 1)),
        "occupancy_pct": float(max(0.0, min(100.0, occupancy_pct))),
    }
