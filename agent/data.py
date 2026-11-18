"""Loaders for the synthetic CSV and JSON files in data/."""
import csv
import json
from pathlib import Path

from .models import Appointment, FeeItem

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_appointments(path: Path = DATA_DIR / "appointments.csv") -> list[Appointment]:
    with open(path, newline="") as f:
        return [Appointment(**row) for row in csv.DictReader(f)]


def load_fees(path: Path = DATA_DIR / "fee_schedule.csv") -> dict[str, FeeItem]:
    with open(path, newline="") as f:
        return {row["cdt_code"]: FeeItem(**row) for row in csv.DictReader(f)}


def load_json(name: str) -> dict:
    data = json.loads((DATA_DIR / name).read_text())
    return {k: v for k, v in data.items() if not k.startswith("_")}
