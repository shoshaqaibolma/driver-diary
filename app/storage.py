import hashlib
import json
import os
import threading
from enum import Enum
from pathlib import Path

from .models import Trip, TripIn


class AddResult(Enum):
    CREATED = "created"
    DUPLICATE = "duplicate"  # та же поездка уже есть — ничего не добавлено
    CONFLICT = "conflict"  # id занят другой поездкой


def _fingerprint(t: TripIn) -> tuple:
    """Содержимое поездки без id: по нему узнаём повторную отправку."""
    return (t.start.timestamp(), t.end.timestamp(), t.amount, t.payment, t.commission)


def derive_id(t: TripIn) -> str:
    raw = json.dumps(_fingerprint(t))
    return "t-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


class TripStore:
    """Поездки хранятся в JSON-файле; запись атомарная (через временный файл), доступ под замком."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("[]", encoding="utf-8")

    def all(self) -> list[Trip]:
        with self._lock:
            return self._load()

    def add(self, incoming: TripIn) -> tuple[AddResult, Trip]:
        with self._lock:
            trips = self._load()
            fp = _fingerprint(incoming)
            trip_id = incoming.id or derive_id(incoming)

            by_id = next((t for t in trips if t.id == trip_id), None)
            if by_id is not None:
                if _fingerprint(by_id) == fp:
                    return AddResult.DUPLICATE, by_id
                return AddResult.CONFLICT, by_id

            # Та же поездка, отправленная повторно под другим/пустым id, тоже считается дублем.
            same = next((t for t in trips if _fingerprint(t) == fp), None)
            if same is not None:
                return AddResult.DUPLICATE, same

            trip = Trip(**incoming.model_dump(exclude={"id"}), id=trip_id)
            trips.append(trip)
            self._save(trips)
            return AddResult.CREATED, trip

    def _load(self) -> list[Trip]:
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [Trip.model_validate(item) for item in data]

    def _save(self, trips: list[Trip]) -> None:
        tmp = self.path.with_suffix(".tmp")
        payload = [t.model_dump(mode="json") for t in trips]
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
