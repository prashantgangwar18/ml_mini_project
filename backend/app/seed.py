from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from .models import Bus, Route, Stop, TelemetryLog, Trip

# Sample campus-centric college bus routes (Bengaluru metro region coordinates)
SEED_ROUTES = [
    {
        "code": "R1-NORTH",
        "name": "North Campus Express",
        "color": "#38bdf8",
        "direction": "To Main Campus",
        "description": "Hebbal -> Mekhri Circle -> MG Road -> Silk Board -> College Campus",
        "stops": [
            ("Hebbal Flyover", 13.0358, 77.5970, 0.0, False),
            ("Mekhri Circle", 13.0126, 77.5830, 7.0, False),
            ("Cubbon Park Gate", 12.9763, 77.5929, 14.0, False),
            ("Koramangala Water Tank", 12.9352, 77.6245, 22.0, False),
            ("Silk Board Junction", 12.9177, 77.6238, 29.0, False),
            ("College Main Gate", 12.8452, 77.6602, 41.0, True),
        ],
    },
    {
        "code": "R2-WEST",
        "name": "West Corridor Shuttle",
        "color": "#f59e0b",
        "direction": "To Main Campus",
        "description": "Rajajinagar -> Vijayanagar -> Banashankari -> BTM -> College Campus",
        "stops": [
            ("Rajajinagar Metro", 12.9982, 77.5530, 0.0, False),
            ("Vijayanagar TTMC", 12.9719, 77.5327, 8.0, False),
            ("Mysore Road Junction", 12.9507, 77.5416, 15.0, False),
            ("Banashankari Bus Stand", 12.9255, 77.5468, 22.0, False),
            ("JP Nagar Central", 12.9063, 77.5857, 29.0, False),
            ("HSR Sector 2", 12.9081, 77.6476, 36.0, False),
            ("College Main Gate", 12.8452, 77.6602, 45.0, True),
        ],
    },
    {
        "code": "R3-EAST",
        "name": "IT Corridor & Hostel Line",
        "color": "#10b981",
        "direction": "To Main Campus",
        "description": "KR Puram -> Marathahalli -> Bellandur -> Kudlu Gate -> College Campus",
        "stops": [
            ("KR Puram Station", 13.0012, 77.6960, 0.0, False),
            ("Mahadevapura", 12.9885, 77.6956, 6.0, False),
            ("Marathahalli Bridge", 12.9591, 77.6974, 13.0, False),
            ("Bellandur Gate", 12.9279, 77.6762, 20.0, False),
            ("Kudlu Gate", 12.8902, 77.6406, 27.0, False),
            ("College Main Gate", 12.8452, 77.6602, 36.0, True),
        ],
    },
    {
        "code": "R4-SOUTH",
        "name": "South Hostel Loop",
        "color": "#a855f7",
        "direction": "To Main Campus",
        "description": "Jayanagar -> Bannerghatta -> Meenakshi Mall -> Electronic City -> Campus",
        "stops": [
            ("Jayanagar 4th Block", 12.9250, 77.5838, 0.0, False),
            ("IIMB Gate", 12.8957, 77.6020, 8.0, False),
            ("Meenakshi Mall", 12.8758, 77.5960, 14.0, False),
            ("Hosa Road Cross", 12.8650, 77.6480, 22.0, False),
            ("College Main Gate", 12.8452, 77.6602, 29.0, True),
        ],
    },
]

SEED_BUSES = [
    ("CB-101", "Rajesh Kumar", 48, 72, "R1-NORTH", 2, 13.0126, 77.5830, 31.0),
    ("CB-102", "Suresh Patel", 48, 58, "R1-NORTH", 4, 12.9352, 77.6245, 24.0),
    ("CB-204", "Manoj Verma", 42, 64, "R2-WEST", 3, 12.9507, 77.5416, 27.0),
    ("CB-308", "Anil Sharma", 50, 81, "R3-EAST", 2, 12.9885, 77.6956, 29.0),
    ("CB-405", "Vikram Singh", 40, 46, "R4-SOUTH", 2, 12.8957, 77.6020, 33.0),
]


def seed_database(db: Session) -> None:
    """Populate initial routes, stops, buses, and active trips if database is empty."""
    if db.query(Route).count() > 0:
        return

    code_to_route: dict[str, Route] = {}
    for route_def in SEED_ROUTES:
        route = Route(
            code=route_def["code"],
            name=route_def["name"],
            color=route_def["color"],
            direction=route_def["direction"],
            description=route_def["description"],
        )
        db.add(route)
        db.flush()

        for seq, (stop_name, lat, lon, offset_min, is_campus) in enumerate(
            route_def["stops"], start=1
        ):
            db.add(
                Stop(
                    route_id=route.id,
                    name=stop_name,
                    sequence_order=seq,
                    lat=lat,
                    lon=lon,
                    scheduled_offset_min=offset_min,
                    is_campus=is_campus,
                )
            )
        code_to_route[route.code] = route

    db.flush()
    now = datetime.now(timezone.utc)

    for bus_num, driver, cap, occ, route_code, stop_seq, lat, lon, speed in SEED_BUSES:
        route = code_to_route[route_code]
        bus = Bus(
            bus_number=bus_num,
            driver_name=driver,
            capacity=cap,
            occupancy_pct=occ,
            route_id=route.id,
            status="active",
            current_lat=lat,
            current_lon=lon,
            current_speed_kmh=speed,
            heading=150.0,
            current_stop_seq=stop_seq,
            last_updated=now,
        )
        db.add(bus)
        db.flush()

        # Stagger trip start slightly in the past so scheduled vs actual deviation is realistic
        sched_start = now - timedelta(minutes=10 + stop_seq * 3)
        actual_start = sched_start + timedelta(minutes=1 if stop_seq % 2 == 0 else 0)
        trip = Trip(
            bus_id=bus.id,
            route_id=route.id,
            scheduled_start=sched_start,
            actual_start=actual_start,
            weather="Clear",
            traffic_level="Moderate",
            status="in_progress",
        )
        db.add(trip)
        db.flush()

        db.add(
            TelemetryLog(
                trip_id=trip.id,
                bus_id=bus.id,
                lat=lat,
                lon=lon,
                speed_kmh=speed,
                current_stop_seq=stop_seq,
                timestamp=now,
            )
        )

    db.commit()
