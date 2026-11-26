import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from ..config import ML_ARTIFACTS_DIR
from ..models import Bus, Route, Stop, TelemetryLog, Trip
from ..schemas import BusSummaryOut, StopPredictionOut
from .geo import haversine_km, remaining_route_distance_km, total_route_distance_km
from ml.features import FEATURE_COLUMNS, LATE_CLASS_NAMES, build_feature_dict, classify_delay


class MLPredictorService:
    """Loads trained LightGBM artifacts and produces live stop-by-stop TOA and delay predictions."""

    def __init__(self, artifacts_dir: Path = ML_ARTIFACTS_DIR) -> None:
        self.artifacts_dir = artifacts_dir
        self.toa_model = None
        self.delay_model = None
        self.late_classifier = None
        self.metrics: dict = {}
        self.load_models()

    def models_exist(self) -> bool:
        return (
            (self.artifacts_dir / "toa_model.joblib").exists()
            and (self.artifacts_dir / "delay_model.joblib").exists()
            and (self.artifacts_dir / "late_classifier.joblib").exists()
        )

    def load_models(self) -> bool:
        """Load serialized ML models and evaluation metrics if present."""
        if not self.models_exist():
            return False

        self.toa_model = joblib.load(self.artifacts_dir / "toa_model.joblib")
        self.delay_model = joblib.load(self.artifacts_dir / "delay_model.joblib")
        self.late_classifier = joblib.load(self.artifacts_dir / "late_classifier.joblib")

        metrics_file = self.artifacts_dir / "metrics.json"
        if metrics_file.exists():
            self.metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
        return True

    def ensure_models_loaded(self) -> None:
        """Train models automatically on first boot if artifacts are missing."""
        if not self.load_models():
            from ml.train import train_and_evaluate

            train_and_evaluate(regenerate_data=True)
            self.load_models()

    def _as_utc(self, dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def predict_for_bus(self, db: Session, bus: Bus) -> BusSummaryOut:
        """Compute live TOA and late predictions for every upcoming stop on the bus's route."""
        self.ensure_models_loaded()

        route: Route = bus.route
        stops = sorted(route.stops, key=lambda s: s.sequence_order)

        active_trip: Optional[Trip] = (
            db.query(Trip)
            .filter(Trip.bus_id == bus.id, Trip.status == "in_progress")
            .order_by(Trip.id.desc())
            .first()
        )

        now = datetime.now(timezone.utc)
        sched_start = (
            self._as_utc(active_trip.scheduled_start)
            if active_trip
            else now - timedelta(minutes=12)
        )
        weather = active_trip.weather if active_trip else "Clear"
        traffic_level = active_trip.traffic_level if active_trip else "Moderate"

        # Rolling average speed from last 3 telemetry logs
        recent_logs = (
            db.query(TelemetryLog)
            .filter(TelemetryLog.bus_id == bus.id)
            .order_by(TelemetryLog.id.desc())
            .limit(3)
            .all()
        )
        if recent_logs:
            rolling_speed = sum(log.speed_kmh for log in recent_logs) / len(recent_logs)
        else:
            rolling_speed = bus.current_speed_kmh

        total_dist = max(total_route_distance_km(stops), 0.1)
        next_stop_seq = min(bus.current_stop_seq + 1, stops[-1].sequence_order) if stops else 1

        # Estimate scheduled offset at current GPS position along route
        cur_seq_stop = next(
            (s for s in stops if s.sequence_order == bus.current_stop_seq),
            stops[0] if stops else None,
        )
        next_seq_stop = next(
            (s for s in stops if s.sequence_order == next_stop_seq),
            stops[-1] if stops else None,
        )

        if cur_seq_stop and next_seq_stop and cur_seq_stop.id != next_seq_stop.id:
            seg_len = max(
                haversine_km(cur_seq_stop.lat, cur_seq_stop.lon, next_seq_stop.lat, next_seq_stop.lon),
                0.05,
            )
            dist_from_cur = haversine_km(
                cur_seq_stop.lat, cur_seq_stop.lon, bus.current_lat, bus.current_lon
            )
            frac = max(0.0, min(1.0, dist_from_cur / seg_len))
            sched_at_pos = cur_seq_stop.scheduled_offset_min + frac * (
                next_seq_stop.scheduled_offset_min - cur_seq_stop.scheduled_offset_min
            )
        elif cur_seq_stop:
            sched_at_pos = cur_seq_stop.scheduled_offset_min
        else:
            sched_at_pos = 0.0

        elapsed_min = (now - sched_start).total_seconds() / 60.0
        sched_dev_so_far = elapsed_min - sched_at_pos

        upcoming_stops: list[Stop] = [s for s in stops if s.sequence_order > bus.current_stop_seq]
        predictions: list[StopPredictionOut] = []

        # Mark passed stops
        for s in stops:
            if s.sequence_order <= bus.current_stop_seq:
                sched_arr = sched_start + timedelta(minutes=s.scheduled_offset_min)
                _, late_lbl = classify_delay(sched_dev_so_far)
                predictions.append(
                    StopPredictionOut(
                        stop_id=s.id,
                        stop_name=s.name,
                        sequence_order=s.sequence_order,
                        lat=s.lat,
                        lon=s.lon,
                        is_campus=s.is_campus,
                        status="passed",
                        scheduled_arrival=sched_arr,
                        predicted_toa=sched_arr + timedelta(minutes=max(0.0, sched_dev_so_far)),
                        remaining_min=0.0,
                        predicted_delay_min=round(sched_dev_so_far, 1),
                        late_status=late_lbl,  # type: ignore[arg-type]
                        late_probability={"On Time": 1.0, "Slightly Late": 0.0, "Late": 0.0},
                        distance_km=0.0,
                    )
                )

        if upcoming_stops:
            feature_rows = []
            rem_distances = []
            for idx, target_stop in enumerate(upcoming_stops):
                rem_km = remaining_route_distance_km(
                    bus.current_lat,
                    bus.current_lon,
                    stops,
                    next_stop_seq,
                    target_stop.sequence_order,
                )
                rem_distances.append(rem_km)
                hav_km = haversine_km(
                    bus.current_lat, bus.current_lon, target_stop.lat, target_stop.lon
                )
                rem_to_end = remaining_route_distance_km(
                    bus.current_lat,
                    bus.current_lon,
                    stops,
                    next_stop_seq,
                    stops[-1].sequence_order,
                )
                progress_ratio = max(0.0, min(1.0, 1.0 - (rem_to_end / total_dist)))
                sched_rem_min = target_stop.scheduled_offset_min - elapsed_min

                feature_rows.append(
                    build_feature_dict(
                        route_id=route.id,
                        remaining_route_km=rem_km,
                        haversine_to_stop_km=hav_km,
                        stops_remaining=idx,
                        progress_ratio=progress_ratio,
                        current_speed_kmh=bus.current_speed_kmh,
                        rolling_speed_kmh=rolling_speed,
                        schedule_deviation_so_far_min=sched_dev_so_far,
                        scheduled_remaining_min=sched_rem_min,
                        timestamp=now,
                        weather=weather,
                        traffic_level=traffic_level,
                        occupancy_pct=float(bus.occupancy_pct),
                    )
                )

            X_inf = pd.DataFrame(feature_rows)[FEATURE_COLUMNS]
            toa_preds = self.toa_model.predict(X_inf)
            delay_preds = self.delay_model.predict(X_inf)
            late_probs = self.late_classifier.predict_proba(X_inf)

            prev_rem = 0.0
            for idx, target_stop in enumerate(upcoming_stops):
                # Enforce monotonic arrival times along the route
                rem_min = max(0.3, float(toa_preds[idx]), prev_rem + (0.4 if idx > 0 else 0.0))
                prev_rem = rem_min

                sched_arr = sched_start + timedelta(minutes=target_stop.scheduled_offset_min)
                pred_toa = now + timedelta(minutes=rem_min)

                # Blend direct delay regressor with schedule-consistent TOA delay
                toa_implied_delay = (pred_toa - sched_arr).total_seconds() / 60.0
                blended_delay = 0.65 * toa_implied_delay + 0.35 * float(delay_preds[idx])
                _, late_label = classify_delay(blended_delay)

                probs_row = late_probs[idx]
                prob_dict = {
                    LATE_CLASS_NAMES[c]: round(float(probs_row[i]), 3)
                    for i, c in enumerate(self.late_classifier.classes_)
                }

                predictions.append(
                    StopPredictionOut(
                        stop_id=target_stop.id,
                        stop_name=target_stop.name,
                        sequence_order=target_stop.sequence_order,
                        lat=target_stop.lat,
                        lon=target_stop.lon,
                        is_campus=target_stop.is_campus,
                        status="next" if idx == 0 else "upcoming",
                        scheduled_arrival=sched_arr,
                        predicted_toa=pred_toa,
                        remaining_min=round(rem_min, 1),
                        predicted_delay_min=round(blended_delay, 1),
                        late_status=late_label,  # type: ignore[arg-type]
                        late_probability=prob_dict,
                        distance_km=round(rem_distances[idx], 2),
                    )
                )

        next_pred = next((p for p in predictions if p.status == "next"), None)
        campus_pred = next((p for p in reversed(predictions) if p.is_campus), None)

        return BusSummaryOut(
            id=bus.id,
            bus_number=bus.bus_number,
            driver_name=bus.driver_name,
            capacity=bus.capacity,
            occupancy_pct=bus.occupancy_pct,
            route_id=route.id,
            route_code=route.code,
            route_name=route.name,
            route_color=route.color,
            status=bus.status,
            current_lat=round(bus.current_lat, 6),
            current_lon=round(bus.current_lon, 6),
            current_speed_kmh=round(bus.current_speed_kmh, 1),
            heading=round(bus.heading, 1),
            current_stop_seq=bus.current_stop_seq,
            last_updated=self._as_utc(bus.last_updated),
            weather=weather,
            traffic_level=traffic_level,
            next_stop=next_pred,
            campus_prediction=campus_pred,
            predictions=predictions,
        )


predictor_service = MLPredictorService()
