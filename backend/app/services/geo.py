import math
from typing import Sequence

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometers between two coordinates."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute forward azimuth bearing in degrees (0-360)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def interpolate_point(
    lat1: float, lon1: float, lat2: float, lon2: float, fraction: float
) -> tuple[float, float]:
    """Linearly interpolate between two GPS coordinates clamped to [0, 1]."""
    t = max(0.0, min(1.0, fraction))
    return lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t


def total_route_distance_km(stops: Sequence) -> float:
    """Return total polyline distance across ordered stops."""
    if len(stops) < 2:
        return 0.0
    total = 0.0
    for i in range(len(stops) - 1):
        total += haversine_km(stops[i].lat, stops[i].lon, stops[i + 1].lat, stops[i + 1].lon)
    return total


def remaining_route_distance_km(
    cur_lat: float,
    cur_lon: float,
    stops: Sequence,
    next_stop_seq: int,
    target_stop_seq: int,
) -> float:
    """Compute remaining path distance from current GPS position to target stop sequence."""
    ordered = sorted(stops, key=lambda s: s.sequence_order)
    if not ordered:
        return 0.0

    seq_to_idx = {s.sequence_order: i for i, s in enumerate(ordered)}
    if target_stop_seq not in seq_to_idx:
        return 0.0

    target_idx = seq_to_idx[target_stop_seq]
    next_idx = seq_to_idx.get(next_stop_seq, 0)
    if target_idx < next_idx:
        return 0.0

    dist = haversine_km(cur_lat, cur_lon, ordered[next_idx].lat, ordered[next_idx].lon)
    for idx in range(next_idx, target_idx):
        dist += haversine_km(
            ordered[idx].lat,
            ordered[idx].lon,
            ordered[idx + 1].lat,
            ordered[idx + 1].lon,
        )
    return dist
