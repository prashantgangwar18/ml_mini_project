from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Bus
from ..schemas import BusSummaryOut
from ..services.predictor import predictor_service

router = APIRouter(prefix="/api/buses", tags=["buses"])


@router.get("", response_model=list[BusSummaryOut])
def list_buses(route_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(Bus).order_by(Bus.id)
    if route_id is not None:
        query = query.filter(Bus.route_id == route_id)
    buses = query.all()
    return [predictor_service.predict_for_bus(db, bus) for bus in buses]


@router.get("/{bus_id}", response_model=BusSummaryOut)
def get_bus(bus_id: int, db: Session = Depends(get_db)):
    bus = db.query(Bus).filter(Bus.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    return predictor_service.predict_for_bus(db, bus)
