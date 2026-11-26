from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, SessionLocal, engine
from .models import Bus
from .routers import admin, buses, routes, telemetry
from .seed import seed_database
from .services.predictor import predictor_service
from .services.simulator import simulator
from .services.ws_manager import ws_manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()

    predictor_service.ensure_models_loaded()
    simulator.start()
    try:
        yield
    finally:
        await simulator.stop()


app = FastAPI(
    title="College Bus Tracking & ML TOA/Delay API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(buses.router)
app.include_router(telemetry.router)
app.include_router(admin.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "models_loaded": predictor_service.models_exist()}


@app.websocket("/ws/live")
async def live_feed(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        db = SessionLocal()
        try:
            active_buses = db.query(Bus).filter(Bus.status == "active").all()
            await websocket.send_json(
                {
                    "type": "fleet_update",
                    "simulator": simulator.status().model_dump(mode="json"),
                    "buses": [
                        predictor_service.predict_for_bus(db, b).model_dump(mode="json")
                        for b in active_buses
                    ],
                }
            )
        finally:
            db.close()

        while True:
            # Keep socket alive; ignore client ping text
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
