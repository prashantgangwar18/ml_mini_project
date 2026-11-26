from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Bus, TelemetryLog, Trip
from ..schemas import BusSummaryOut, TelemetryIn
from ..services.geo import bearing_deg, haversine_km
from ..services.predictor import predictor_service
from ..services.simulator import simulator
from ..services.ws_manager import ws_manager

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.post("", response_model=BusSummaryOut)
async def ingest_telemetry(payload: TelemetryIn, db: Session = Depends(get_db)):
    """Ingest live GPS ping from Driver Mode or external tracker and return updated predictions."""
    bus = db.query(Bus).filter(Bus.id == payload.bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    now = datetime.now(timezone.utc)
    bus.heading = bearing_deg(bus.current_lat, bus.current_lon, payload.lat, payload.lon)
    bus.current_lat = payload.lat
    bus.current_lon = payload.lon
    bus.current_speed_kmh = payload.speed_kmh
    if payload.occupancy_pct is not None:
        bus.occupancy_pct = payload.occupancy_pct
    bus.last_updated = now

    # Snap current_stop_seq forward if bus is within 180m of the next stop
    stops = sorted(bus.route.stops, key=lambda s: s.sequence_order)
    for s in stops:
        if s.sequence_order > bus.current_stop_seq:
            if haversine_km(payload.lat, payload.lon, s.lat, s.lon) <= 0.18:
                bus.current_stop_seq = s.sequence_order
            break

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
            weather=payload.weather or simulator.weather,
            traffic_level=payload.traffic_level or simulator.traffic_level,
            status="in_progress",
        )
        db.add(trip)
        db.flush()
    else:
        if payload.weather is not None:
            trip.weather = payload.weather
        if payload.traffic_level is not None:
            trip.traffic_level = payload.traffic_level

    db.add(
        TelemetryLog(
            trip_id=trip.id,
            bus_id=bus.id,
            lat=payload.lat,
            lon=payload.lon,
            speed_kmh=payload.speed_kmh,
            current_stop_seq=bus.current_stop_seq,
            timestamp=now,
        )
    )
    db.commit()
    db.refresh(bus)

    summary = predictor_service.predict_for_bus(db, bus)
    if ws_manager.active_connections:
        all_buses = db.query(Bus).filter(Bus.status == "active").all()
        await ws_manager.broadcast_json(
            {
                "type": "fleet_update",
                "simulator": simulator.status().model_dump(mode="json"),
                "buses": [predictor_service.predict_for_bus(db, b).model_dump(mode="json") for b in all_buses],
            }
        )
    return summary
