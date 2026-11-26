from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ML_DIR = BASE_DIR / "ml"
ML_DATA_DIR = ML_DIR / "data"
ML_ARTIFACTS_DIR = ML_DIR / "artifacts"

DATA_DIR.mkdir(parents=True, exist_ok=True)
ML_DATA_DIR.mkdir(parents=True, exist_ok=True)
ML_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{(DATA_DIR / 'bus_tracker.db').as_posix()}"

ON_TIME_MAX_DELAY_MIN = 2.0
SLIGHTLY_LATE_MAX_DELAY_MIN = 7.0
SIMULATION_TICK_SECONDS = 2.0
