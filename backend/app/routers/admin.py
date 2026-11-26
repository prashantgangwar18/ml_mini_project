from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Bus, Route, StopArrival, TelemetryLog
from ..schemas import SimulatorConfigIn, SimulatorStatusOut
from ..services.predictor import predictor_service
from ..services.simulator import simulator
from ml.train import train_and_evaluate

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/overview")
def get_admin_overview(db: Session = Depends(get_db)):
    buses = db.query(Bus).all()
    summaries = [predictor_service.predict_for_bus(db, b) for b in buses]

    on_time = sum(
        1
        for s in summaries
        if s.campus_prediction and s.campus_prediction.late_status == "On Time"
    )
    slightly_late = sum(
        1
        for s in summaries
        if s.campus_prediction and s.campus_prediction.late_status == "Slightly Late"
    )
    late = sum(
        1
        for s in summaries
        if s.campus_prediction and s.campus_prediction.late_status == "Late"
    )

    recent_arrivals = (
        db.query(StopArrival).order_by(StopArrival.id.desc()).limit(20).all()
    )
    route_delay_stats = []
    for route in db.query(Route).order_by(Route.id).all():
        route_buses = [s for s in summaries if s.route_id == route.id]
        avg_delay = 0.0
        if route_buses:
            delays = [
                b.campus_prediction.predicted_delay_min
                for b in route_buses
                if b.campus_prediction
            ]
            avg_delay = round(sum(delays) / max(len(delays), 1), 2)
        route_delay_stats.append(
            {
                "route_code": route.code,
                "route_name": route.name,
                "color": route.color,
                "avg_delay_min": avg_delay,
                "active_buses": len(route_buses),
            }
        )

    return {
        "fleet": {
            "total_buses": len(buses),
            "active_buses": sum(1 for b in buses if b.status == "active"),
            "on_time": on_time,
            "slightly_late": slightly_late,
            "late": late,
            "telemetry_logs_count": db.query(TelemetryLog).count(),
        },
        "route_delays": route_delay_stats,
        "recent_arrivals": [
            {
                "id": a.id,
                "stop_id": a.stop_id,
                "delay_min": a.delay_min,
                "actual_time": a.actual_time,
            }
            for a in recent_arrivals
        ],
        "simulator": simulator.status().model_dump(mode="json"),
    }


@router.get("/metrics")
def get_ml_metrics():
    predictor_service.ensure_models_loaded()
    return predictor_service.metrics


@router.post("/retrain")
def retrain_models(regenerate_data: bool = False):
    metrics = train_and_evaluate(regenerate_data=regenerate_data)
    predictor_service.load_models()
    return {"status": "retrained", "metrics": metrics}


@router.get("/simulator", response_model=SimulatorStatusOut)
def get_simulator_status():
    return simulator.status()


@router.post("/simulator", response_model=SimulatorStatusOut)
def update_simulator(cfg: SimulatorConfigIn, db: Session = Depends(get_db)):
    return simulator.configure(cfg, db)
