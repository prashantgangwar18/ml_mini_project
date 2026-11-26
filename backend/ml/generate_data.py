from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import ML_DATA_DIR
from app.seed import SEED_ROUTES
from app.services.geo import haversine_km, interpolate_point
from ml.features import build_feature_dict, classify_delay, is_rush_hour_dt


def generate_synthetic_dataset(
    num_trips: int = 900,
    seed: int = 42,
    output_path: Path | None = None,
) -> Path:
    """Simulate realistic historical college bus trips and save training samples to CSV."""
    rng = np.random.default_rng(seed)
    out_file = output_path or (ML_DATA_DIR / "historical_trips.csv")
    out_file.parent.mkdir(parents=True, exist_ok=True)

    start_base = datetime(2026, 9, 1, 7, 15, tzinfo=timezone.utc)
    rows: list[dict] = []

    weather_choices = ["Clear", "Cloudy", "Rain", "Fog"]
    weather_probs = [0.58, 0.20, 0.16, 0.06]
    traffic_choices = ["Low", "Moderate", "Heavy"]

    for trip_idx in range(1, num_trips + 1):
        route_idx = (trip_idx - 1) % len(SEED_ROUTES)
        route_id = route_idx + 1
        stops = SEED_ROUTES[route_idx]["stops"]

        day_offset = (trip_idx - 1) // 15
        slot = (trip_idx - 1) % 15
        slot_hours = [7, 7, 8, 8, 8, 9, 12, 13, 16, 17, 17, 17, 18, 18, 19]
        slot_mins = [15, 45, 0, 20, 45, 10, 30, 15, 40, 0, 20, 45, 10, 35, 0]
        scheduled_start = (
            start_base.replace(hour=slot_hours[slot], minute=slot_mins[slot])
            + timedelta(days=day_offset)
        )

        weather = str(rng.choice(weather_choices, p=weather_probs))
        rush = is_rush_hour_dt(scheduled_start)
        if rush:
            traffic = str(rng.choice(traffic_choices, p=[0.10, 0.42, 0.48]))
        else:
            traffic = str(rng.choice(traffic_choices, p=[0.45, 0.43, 0.12]))

        occupancy_pct = float(
            np.clip(rng.normal(76 if rush else 46, 14), 15.0, 98.0)
        )

        # Departure jitter (some buses start 0-4 min late)
        start_delay_min = float(max(-0.5, rng.normal(1.2 if rush else 0.3, 1.4)))

        weather_factor = {"Clear": 1.0, "Cloudy": 0.96, "Rain": 0.78, "Fog": 0.73}[weather]
        traffic_factor = {"Low": 1.08, "Moderate": 0.88, "Heavy": 0.64}[traffic]
        rush_factor = 0.86 if rush else 1.0
        driver_factor = float(np.clip(rng.normal(1.0, 0.07), 0.82, 1.16))

        # Build segment-by-segment timeline with intermediate GPS pings
        seg_distances = [
            haversine_km(stops[i][1], stops[i][2], stops[i + 1][1], stops[i + 1][2])
            for i in range(len(stops) - 1)
        ]
        total_dist = sum(seg_distances)

        # Simulate stop arrival offsets from scheduled_start
        cum_elapsed_min = start_delay_min
        stop_actual_offsets = [cum_elapsed_min]
        seg_speeds: list[float] = []

        for seg_i, seg_km in enumerate(seg_distances):
            sched_seg_min = stops[seg_i + 1][3] - stops[seg_i][3]
            nominal_kmh = max(16.0, (seg_km / max(sched_seg_min / 60.0, 0.05)))
            seg_noise = float(np.clip(rng.normal(1.0, 0.12), 0.70, 1.25))
            eff_speed_kmh = max(
                10.0,
                nominal_kmh * weather_factor * traffic_factor * rush_factor * driver_factor * seg_noise,
            )
            seg_speeds.append(eff_speed_kmh)

            travel_min = (seg_km / eff_speed_kmh) * 60.0
            dwell_min = (
                0.35 + (occupancy_pct / 100.0) * 0.55 + (0.35 if rush else 0.0)
            ) * float(np.clip(rng.normal(1.0, 0.25), 0.5, 1.8))
            if seg_i == len(seg_distances) - 1:
                dwell_min = 0.0

            cum_elapsed_min += travel_min + dwell_min
            stop_actual_offsets.append(cum_elapsed_min)

        # Sample GPS observations along each segment and pair with every upcoming stop
        cum_dist_so_far = 0.0
        recent_speeds: list[float] = []

        for seg_i, seg_km in enumerate(seg_distances):
            s_a = stops[seg_i]
            s_b = stops[seg_i + 1]
            seg_speed = seg_speeds[seg_i]
            seg_start_min = stop_actual_offsets[seg_i]
            seg_travel_min = (seg_km / seg_speed) * 60.0

            for frac in (0.15, 0.50, 0.85):
                cur_lat, cur_lon = interpolate_point(s_a[1], s_a[2], s_b[1], s_b[2], frac)
                inst_speed = float(max(6.0, seg_speed + rng.normal(0.0, 3.2)))
                recent_speeds.append(inst_speed)
                rolling_speed = float(np.mean(recent_speeds[-3:]))

                cur_elapsed_min = seg_start_min + frac * seg_travel_min
                cur_ts = scheduled_start + timedelta(minutes=cur_elapsed_min)

                sched_at_pos = s_a[3] + frac * (s_b[3] - s_a[3])
                sched_dev_so_far = cur_elapsed_min - sched_at_pos
                dist_done = cum_dist_so_far + frac * seg_km
                progress_ratio = dist_done / max(total_dist, 0.1)

                # Pair with upcoming stops from seg_i + 1 to end
                for target_idx in range(seg_i + 1, len(stops)):
                    t_stop = stops[target_idx]
                    rem_km = haversine_km(cur_lat, cur_lon, s_b[1], s_b[2]) + sum(
                        seg_distances[seg_i + 1 : target_idx]
                    )
                    hav_km = haversine_km(cur_lat, cur_lon, t_stop[1], t_stop[2])
                    stops_rem = target_idx - (seg_i + 1)

                    actual_rem_min = max(0.2, stop_actual_offsets[target_idx] - cur_elapsed_min)
                    actual_delay_min = stop_actual_offsets[target_idx] - t_stop[3]
                    sched_rem_min = t_stop[3] - cur_elapsed_min
                    late_cls, _ = classify_delay(actual_delay_min)

                    feat = build_feature_dict(
                        route_id=route_id,
                        remaining_route_km=rem_km,
                        haversine_to_stop_km=hav_km,
                        stops_remaining=stops_rem,
                        progress_ratio=progress_ratio,
                        current_speed_kmh=inst_speed,
                        rolling_speed_kmh=rolling_speed,
                        schedule_deviation_so_far_min=sched_dev_so_far,
                        scheduled_remaining_min=sched_rem_min,
                        timestamp=cur_ts,
                        weather=weather,
                        traffic_level=traffic,
                        occupancy_pct=occupancy_pct,
                    )
                    feat["trip_id"] = trip_idx
                    feat["actual_remaining_min"] = round(actual_rem_min, 3)
                    feat["actual_delay_min"] = round(actual_delay_min, 3)
                    feat["late_label"] = late_cls
                    rows.append(feat)

            cum_dist_so_far += seg_km

    df = pd.DataFrame(rows)
    df.to_csv(out_file, index=False)
    return out_file


if __name__ == "__main__":
    path = generate_synthetic_dataset()
    print(f"Generated dataset at {path}")
