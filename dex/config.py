import os
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "profile.yaml"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "dex.db"
PHOTO_DIR = DATA_DIR / "photos"
WEB_DIR = ROOT / "web"

OLLAMA_OPTIONS = {"num_ctx": 4096}  # keeps 3-4B models inside a 4GB GPU

# Demo clock. Set DEX_DEBUG=1 to allow skipping ahead a day (for recording demos);
# DEX_DAY_OFFSET starts the server already N days in the future.
DEBUG = os.environ.get("DEX_DEBUG") == "1"
_day_offset = int(os.environ.get("DEX_DAY_OFFSET", "0"))


def now() -> datetime:
    return datetime.now() + timedelta(days=_day_offset)


def today() -> date:
    return now().date()


def advance_day() -> int:
    global _day_offset
    _day_offset += 1
    return _day_offset


def load_profile(path: Path = PROFILE_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)
