import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from app.main import app


def test_health_routes_buses_and_predictions():
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["models_loaded"] is True

        routes_resp = client.get("/api/routes")
        assert routes_resp.status_code == 200
        routes = routes_resp.json()
        assert len(routes) >= 4
        assert len(routes[0]["stops"]) >= 5

        buses_resp = client.get("/api/buses")
        assert buses_resp.status_code == 200
        buses = buses_resp.json()
        assert len(buses) >= 5

        first_bus = buses[0]
        assert first_bus["next_stop"] is not None
        assert first_bus["campus_prediction"] is not None
        assert first_bus["next_stop"]["late_status"] in {"On Time", "Slightly Late", "Late"}
        assert first_bus["next_stop"]["remaining_min"] >= 0.2


def test_telemetry_ingest_and_admin_endpoints():
    with TestClient(app) as client:
        buses = client.get("/api/buses").json()
        bus = buses[0]

        ingest = client.post(
            "/api/telemetry",
            json={
                "bus_id": bus["id"],
                "lat": bus["current_lat"] + 0.001,
                "lon": bus["current_lon"] + 0.001,
                "speed_kmh": 18.5,
                "occupancy_pct": 85,
                "weather": "Rain",
                "traffic_level": "Heavy",
            },
        )
        assert ingest.status_code == 200
        updated = ingest.json()
        assert updated["current_speed_kmh"] == 18.5
        assert updated["weather"] == "Rain"
        assert updated["traffic_level"] == "Heavy"

        metrics = client.get("/api/admin/metrics")
        assert metrics.status_code == 200
        m_json = metrics.json()
        assert "toa_models" in m_json
        assert "late_classification" in m_json

        overview = client.get("/api/admin/overview")
        assert overview.status_code == 200
        assert overview.json()["fleet"]["total_buses"] >= 5
