from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#3b82f6")
    direction: Mapped[str] = mapped_column(String(40), default="To Campus")
    description: Mapped[str] = mapped_column(Text, default="")

    stops: Mapped[list["Stop"]] = relationship(
        "Stop", back_populates="route", order_by="Stop.sequence_order", cascade="all, delete-orphan"
    )
    buses: Mapped[list["Bus"]] = relationship("Bus", back_populates="route")


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    scheduled_offset_min: Mapped[float] = mapped_column(Float, nullable=False)
    is_campus: Mapped[bool] = mapped_column(Boolean, default=False)

    route: Mapped["Route"] = relationship("Route", back_populates="stops")


class Bus(Base):
    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bus_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    driver_name: Mapped[str] = mapped_column(String(80), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=45)
    occupancy_pct: Mapped[int] = mapped_column(Integer, default=55)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active")
    current_lat: Mapped[float] = mapped_column(Float, nullable=False)
    current_lon: Mapped[float] = mapped_column(Float, nullable=False)
    current_speed_kmh: Mapped[float] = mapped_column(Float, default=0.0)
    heading: Mapped[float] = mapped_column(Float, default=0.0)
    current_stop_seq: Mapped[int] = mapped_column(Integer, default=1)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    route: Mapped["Route"] = relationship("Route", back_populates="buses")
    trips: Mapped[list["Trip"]] = relationship("Trip", back_populates="bus")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bus_id: Mapped[int] = mapped_column(ForeignKey("buses.id"), nullable=False, index=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False, index=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    weather: Mapped[str] = mapped_column(String(24), default="Clear")
    traffic_level: Mapped[str] = mapped_column(String(24), default="Moderate")
    status: Mapped[str] = mapped_column(String(24), default="in_progress")

    bus: Mapped["Bus"] = relationship("Bus", back_populates="trips")
    telemetry_logs: Mapped[list["TelemetryLog"]] = relationship(
        "TelemetryLog", back_populates="trip", cascade="all, delete-orphan"
    )


class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    bus_id: Mapped[int] = mapped_column(ForeignKey("buses.id"), nullable=False, index=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    speed_kmh: Mapped[float] = mapped_column(Float, nullable=False)
    current_stop_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    trip: Mapped["Trip"] = relationship("Trip", back_populates="telemetry_logs")


class StopArrival(Base):
    __tablename__ = "stop_arrivals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), nullable=False, index=True)
    stop_id: Mapped[int] = mapped_column(ForeignKey("stops.id"), nullable=False, index=True)
    scheduled_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    actual_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delay_min: Mapped[float] = mapped_column(Float, nullable=False)
