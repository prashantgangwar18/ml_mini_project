from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class StopOut(BaseModel):
    id: int
    route_id: int
    name: str
    sequence_order: int
    lat: float
    lon: float
    scheduled_offset_min: float
    is_campus: bool

    model_config = {"from_attributes": True}


class RouteOut(BaseModel):
    id: int
    code: str
    name: str
    color: str
    direction: str
    description: str
    stops: list[StopOut] = []

    model_config = {"from_attributes": True}


class StopPredictionOut(BaseModel):
    stop_id: int
    stop_name: str
    sequence_order: int
    lat: float
    lon: float
    is_campus: bool
    status: Literal["passed", "next", "upcoming"]
    scheduled_arrival: datetime
    predicted_toa: datetime
    remaining_min: float
    predicted_delay_min: float
    late_status: Literal["On Time", "Slightly Late", "Late"]
    late_probability: dict[str, float]
    distance_km: float


class BusSummaryOut(BaseModel):
    id: int
    bus_number: str
    driver_name: str
    capacity: int
    occupancy_pct: int
    route_id: int
    route_code: str
    route_name: str
    route_color: str
    status: str
    current_lat: float
    current_lon: float
    current_speed_kmh: float
    heading: float
    current_stop_seq: int
    last_updated: datetime
    weather: str
    traffic_level: str
    next_stop: Optional[StopPredictionOut] = None
    campus_prediction: Optional[StopPredictionOut] = None
    predictions: list[StopPredictionOut] = []


class TelemetryIn(BaseModel):
    bus_id: int
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    speed_kmh: float = Field(default=25.0, ge=0, le=140)
    occupancy_pct: Optional[int] = Field(default=None, ge=0, le=100)
    weather: Optional[Literal["Clear", "Cloudy", "Rain", "Fog"]] = None
    traffic_level: Optional[Literal["Low", "Moderate", "Heavy"]] = None


class SimulatorConfigIn(BaseModel):
    running: Optional[bool] = None
    weather: Optional[Literal["Clear", "Cloudy", "Rain", "Fog"]] = None
    traffic_level: Optional[Literal["Low", "Moderate", "Heavy"]] = None
    speed_multiplier: Optional[float] = Field(default=None, ge=0.25, le=10.0)
    inject_delay_bus_id: Optional[int] = None
    inject_delay_min: Optional[float] = Field(default=5.0, ge=1.0, le=30.0)


class SimulatorStatusOut(BaseModel):
    running: bool
    weather: str
    traffic_level: str
    speed_multiplier: float
    tick_count: int
