import os
from datetime import date, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import DayReport, Trip, TripIn
from .storage import AddResult, TripStore
from .summary import summarize, trip_day, trips_for_day

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def create_app(data_path: str | Path | None = None, tz_offset_hours: float | None = None) -> FastAPI:
    data_path = data_path or os.getenv("TRIPS_FILE", BASE_DIR / "data" / "trips.json")
    if tz_offset_hours is None:
        tz_offset_hours = float(os.getenv("DRIVER_TZ_OFFSET", "5"))  # Казахстан, UTC+5
    tz = timezone(timedelta(hours=tz_offset_hours))
    store = TripStore(data_path)

    app = FastAPI(title="Дневник смен водителя")

    @app.get("/api/days", response_model=list[str])
    def list_days():
        """Дни, в которые были поездки (для навигации в клиенте)."""
        return sorted({trip_day(t, tz).isoformat() for t in store.all()})

    @app.get("/api/days/{day}", response_model=DayReport)
    def day_report(day: date):
        trips = trips_for_day(store.all(), day, tz)
        return DayReport(date=day.isoformat(), summary=summarize(trips), trips=trips)

    @app.get("/api/trips", response_model=list[Trip])
    def trips_by_day(date: date):
        return trips_for_day(store.all(), date, tz)

    @app.get("/api/summary")
    def summary_by_day(date: date):
        return summarize(trips_for_day(store.all(), date, tz))

    @app.post("/api/trips", response_model=Trip, status_code=201)
    def add_trip(trip: TripIn):
        result, saved = store.add(trip)
        if result is AddResult.CONFLICT:
            raise HTTPException(409, f"поездка с id «{saved.id}» уже существует и отличается по данным")
        if result is AddResult.DUPLICATE:
            # Идемпотентность: повтор возвращает уже сохранённую поездку, новая не создаётся.
            return JSONResponse(saved.model_dump(mode="json"), status_code=200)
        return saved

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
