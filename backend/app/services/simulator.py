import asyncio
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..config import SIMULATION_TICK_SECONDS
from ..database import SessionLocal
from ..models import Bus, StopArrival, TelemetryLog, Trip
from ..schemas import SimulatorConfigIn, SimulatorStatusOut
from .geo import bearing_deg, haversine_km, interpolate_point
from .predictor import predictor_service
from .ws_manager import ws_manager


class BusSimulator:
    """Real-time multi-bus GPS simulator that drives live telemetry and WebSocket broadcasts."""

    def __init__(self) -> None:
        self.running: bool = True
        self.weather: str = "Clear"
        self.traffic_level: str = "Moderate"
        self.speed_multiplier: float = 1.0
        self.tick_count: int = 0
        self._task: Optional[asyncio.Task] = None
        self._slowdown_ticks: dict[int, int] = {}

    def status(self) -> SimulatorStatusOut:
        return SimulatorStatusOut(
            running=self.running,
            weather=self.weather,
            traffic_level=self.traffic_level,
            speed_multiplier=self.speed_multiplier,
            tick_count=self.tick_count,
        )

    def configure(self, cfg: SimulatorConfigIn, db: Session) -> SimulatorStatusOut:
        if cfg.running is not None:
            self.running = cfg.running
        if cfg.weather is not None:
            self.weather = cfg.weather
        if cfg.traffic_level is not None:
            self.traffic_level = cfg.traffic_level
        if cfg.speed_multiplier is not None:
            self.speed_multiplier = cfg.speed_multiplier

        # Update active trips with current weather/traffic conditions
        if cfg.weather is not None or cfg.traffic_level is not None:
            active_trips = db.query(Trip).filter(Trip.status == "in_progress").all()
            for trip in active_trips:
                if cfg.weather is not None:
                    trip.weather = cfg.weather
                if cfg.traffic_level is not None:
                    trip.traffic_level = cfg.traffic_level
            db.commit()

        # Inject realistic delay on a specific bus by shifting its schedule back & slowing it
        if cfg.inject_delay_bus_id is not None:
            delay_min = cfg.inject_delay_min or 5.0
            trip = (
                db.query(Trip)
                .filter(Trip.bus_id == cfg.inject_delay_bus_id, Trip.status == "in_progress")
                .order_by(Trip.id.desc())
                .first()
            )
            if trip:
                sched = trip.scheduled_start
                if sched.tzinfo is None:
                    sched = sched.replace(tzinfo=timezone.utc)
                trip.scheduled_start = sched - timedelta(minutes=delay_min)
                self._slowdown_ticks[cfg.inject_delay_bus_id] = 6
                db.commit()

        return self.status()

    def _step_bus(self, db: Session, bus: Bus, now: datetime) -> None:
        stops = sorted(bus.route.stops, key=lambda s: s.sequence_order)
        if len(stops) < 2:
            return

        trip = (
            db.query(Trip)
            .filter(Trip.bus_id == bus.id, Trip.status == "in_progress")
            .order_by(Trip.id.desc())
            .first()
        )
        if trip is None:
            trip = Trip(
                bus_id=bus.id,
                route_id=bus.route_id,
                scheduled_start=now,
                actual_start=now,
                weather=self.weather,
                traffic_level=self.traffic_level,
                status="in_progress",
            )
            db.add(trip)
            db.flush()

        # Time-compressed simulation step (4x faster than wall clock at 1.0x multiplier)
        sim_dt_sec = SIMULATION_TICK_SECONDS * self.speed_multiplier * 4.0
        extra_sim_sec = max(0.0, sim_dt_sec - SIMULATION_TICK_SECONDS)
        sched_start = trip.scheduled_start
        if sched_start.tzinfo is None:
            sched_start = sched_start.replace(tzinfo=timezone.utc)
        trip.scheduled_start = sched_start - timedelta(seconds=extra_sim_sec)

        next_stop = next(
            (s for s in stops if s.sequence_order > bus.current_stop_seq),
            None,
        )

        # If bus reached campus, reset smoothly to stop 1 for continuous route service
        if next_stop is None:
            trip.status = "completed"
            first_stop = stops[0]
            bus.current_stop_seq = first_stop.sequence_order
            bus.current_lat = first_stop.lat
            bus.current_lon = first_stop.lon
            bus.current_speed_kmh = 26.0
            bus.last_updated = now
            new_trip = Trip(
                bus_id=bus.id,
                route_id=bus.route_id,
                scheduled_start=now,
                actual_start=now,
                weather=self.weather,
                traffic_level=self.traffic_level,
                status="in_progress",
            )
            db.add(new_trip)
            return

        prev_stop = next(
            (s for s in stops if s.sequence_order == bus.current_stop_seq),
            stops[0],
        )

        weather_factor = {"Clear": 1.0, "Cloudy": 0.96, "Rain": 0.78, "Fog": 0.72}.get(
            trip.weather, 1.0
        )
        traffic_factor = {"Low": 1.10, "Moderate": 0.88, "Heavy": 0.62}.get(
            trip.traffic_level, 0.88
        )

        seg_km = max(haversine_km(prev_stop.lat, prev_stop.lon, next_stop.lat, next_stop.lon), 0.1)
        sched_seg_min = max(next_stop.scheduled_offset_min - prev_stop.scheduled_offset_min, 1.0)
        nominal_kmh = max(18.0, seg_km / (sched_seg_min / 60.0))

        slow_ticks = self._slowdown_ticks.get(bus.id, 0)
        slow_factor = 0.45 if slow_ticks > 0 else 1.0
        if slow_ticks > 0:
            self._slowdown_ticks[bus.id] = slow_ticks - 1

        speed_kmh = max(
            7.0,
            nominal_kmh * weather_factor * traffic_factor * slow_factor * random.uniform(0.90, 1.10),
        )
        step_km = speed_kmh * (sim_dt_sec / 3600.0)
        dist_to_next = haversine_km(bus.current_lat, bus.current_lon, next_stop.lat, next_stop.lon)

        if step_km >= dist_to_next:
            # Arrived at next_stop
            bus.current_lat = next_stop.lat
            bus.current_lon = next_stop.lon
            bus.current_stop_seq = next_stop.sequence_order
            bus.current_speed_kmh = round(speed_kmh * 0.55, 1)

            sched_time = trip.scheduled_start + timedelta(minutes=next_stop.scheduled_offset_min)
            delay_min = (now - sched_time).total_seconds() / 60.0
            db.add(
                StopArrival(
                    trip_id=trip.id,
                    stop_id=next_stop.id,
                    scheduled_time=sched_time,
                    actual_time=now,
                    delay_min=round(delay_min, 2),
                )
            )
            # Slight realistic occupancy shift at intermediate stops
            if not next_stop.is_campus:
                bus.occupancy_pct = max(15, min(98, bus.occupancy_pct + random.randint(-4, 7)))
        else:
            frac = step_km / max(dist_to_next, 1e-6)
            new_lat, new_lon = interpolate_point(
                bus.current_lat, bus.current_lon, next_stop.lat, next_stop.lon, frac
            )
            bus.heading = bearing_deg(bus.current_lat, bus.current_lon, next_stop.lat, next_stop.lon)
            bus.current_lat = new_lat
            bus.current_lon = new_lon
            bus.current_speed_kmh = round(speed_kmh, 1)

        bus.last_updated = now
        db.add(
            TelemetryLog(
                trip_id=trip.id,
                bus_id=bus.id,
                lat=bus.current_lat,
                lon=bus.current_lon,
                speed_kmh=bus.current_speed_kmh,
                current_stop_seq=bus.current_stop_seq,
                timestamp=now,
            )
        )

    async def step_once(self) -> list[dict]:
        """Advance all active buses one tick and return serialized live summaries."""
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            buses = db.query(Bus).filter(Bus.status == "active").all()
            if self.running:
                self.tick_count += 1
                for bus in buses:
                    self._step_bus(db, bus, now)
                db.commit()

            summaries = [predictor_service.predict_for_bus(db, bus).model_dump(mode="json") for bus in buses]
            return summaries
        finally:
            db.close()

    async def _run_loop(self) -> None:
        while True:
            try:
                summaries = await self.step_once()
                if ws_manager.active_connections:
                    await ws_manager.broadcast_json(
                        {
                            "type": "fleet_update",
                            "simulator": self.status().model_dump(mode="json"),
                            "buses": summaries,
                        }
                    )
            except Exception as exc:
                print(f"[Simulator] Tick error: {exc}")
            await asyncio.sleep(SIMULATION_TICK_SECONDS)

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass


simulator = BusSimulator()
