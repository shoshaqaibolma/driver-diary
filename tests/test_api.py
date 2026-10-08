import json

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

SEED = [
    {"id": "t1", "start": "2026-10-01T08:10:00+05:00", "end": "2026-10-01T08:32:00+05:00", "amount": 2400, "payment": "card", "commission": 360},
    {"id": "t2", "start": "2026-10-01T09:05:00+05:00", "end": "2026-10-01T09:20:00+05:00", "amount": 1500, "payment": "cash", "commission": 225},
]

NEW_TRIP = {"start": "2026-10-01T12:00:00+05:00", "end": "2026-10-01T12:25:00+05:00", "amount": 2000, "payment": "cash", "commission": 300}


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "trips.json"
    path.write_text(json.dumps(SEED), encoding="utf-8")
    return path


@pytest.fixture
def client(data_file):
    return TestClient(create_app(data_file, tz_offset_hours=5))


def day(client, d="2026-10-01"):
    r = client.get(f"/api/days/{d}")
    assert r.status_code == 200
    return r.json()


# --- чтение ---------------------------------------------------------------

def test_day_report(client):
    body = day(client)
    assert [t["id"] for t in body["trips"]] == ["t1", "t2"]
    assert body["summary"] == {
        "trips_count": 2, "revenue": 3900, "commission": 585, "net": 3315,
        "cash": {"count": 1, "amount": 1500}, "card": {"count": 1, "amount": 2400},
    }


def test_separate_trips_and_summary_endpoints(client):
    assert len(client.get("/api/trips", params={"date": "2026-10-01"}).json()) == 2
    assert client.get("/api/summary", params={"date": "2026-10-01"}).json()["net"] == 3315


def test_empty_day(client):
    body = day(client, "2026-10-05")
    assert body["trips"] == [] and body["summary"]["trips_count"] == 0


def test_bad_date_rejected(client):
    assert client.get("/api/days/not-a-date").status_code == 422


def test_list_days(client):
    assert client.get("/api/days").json() == ["2026-10-01"]


# --- добавление и валидация ----------------------------------------------

def test_add_trip_updates_summary(client):
    r = client.post("/api/trips", json=NEW_TRIP)
    assert r.status_code == 201
    assert r.json()["id"]  # id выдан сервером
    s = day(client)["summary"]
    assert s["trips_count"] == 3 and s["revenue"] == 5900 and s["cash"]["amount"] == 3500


@pytest.mark.parametrize("patch", [
    {"amount": 0},
    {"amount": -100},
    {"end": "2026-10-01T11:00:00+05:00"},           # окончание раньше начала
    {"end": NEW_TRIP["start"]},                     # окончание равно началу
    {"payment": "crypto"},
    {"commission": -1},
    {"commission": 2500},                           # комиссия больше суммы
    {"start": "2026-10-01T12:00:00"},               # без часового пояса
    {"amount": "много"},
])
def test_invalid_trip_rejected(client, data_file, patch):
    before = data_file.read_text(encoding="utf-8")
    r = client.post("/api/trips", json={**NEW_TRIP, **patch})
    assert r.status_code == 422
    assert data_file.read_text(encoding="utf-8") == before  # ничего не записано


def test_missing_field_rejected(client):
    trip = dict(NEW_TRIP)
    del trip["amount"]
    assert client.post("/api/trips", json=trip).status_code == 422


# --- защита от дублей ----------------------------------------------------

def test_resend_with_same_id_does_not_duplicate(client):
    trip = {**NEW_TRIP, "id": "t100"}
    first = client.post("/api/trips", json=trip)
    second = client.post("/api/trips", json=trip)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    assert day(client)["summary"]["trips_count"] == 3


def test_resend_without_id_does_not_duplicate(client):
    first = client.post("/api/trips", json=NEW_TRIP)
    second = client.post("/api/trips", json=NEW_TRIP)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert day(client)["summary"]["trips_count"] == 3


def test_resend_of_seed_trip_is_duplicate(client):
    r = client.post("/api/trips", json=SEED[0])
    assert r.status_code == 200
    assert day(client)["summary"]["trips_count"] == 2


def test_same_trip_under_new_id_is_duplicate(client):
    r = client.post("/api/trips", json={**SEED[0], "id": "other-id"})
    assert r.status_code == 200 and r.json()["id"] == "t1"
    assert day(client)["summary"]["trips_count"] == 2


def test_same_moment_written_in_other_timezone_is_duplicate(client):
    utc = {**SEED[0], "id": None, "start": "2026-10-01T03:10:00Z", "end": "2026-10-01T03:32:00Z"}
    assert client.post("/api/trips", json=utc).status_code == 200
    assert day(client)["summary"]["trips_count"] == 2


def test_existing_id_with_different_data_is_conflict(client):
    r = client.post("/api/trips", json={**SEED[0], "amount": 9999})
    assert r.status_code == 409
    assert day(client)["summary"]["revenue"] == 3900


def test_duplicates_survive_restart(data_file):
    client_a = TestClient(create_app(data_file, tz_offset_hours=5))
    assert client_a.post("/api/trips", json=NEW_TRIP).status_code == 201
    client_b = TestClient(create_app(data_file, tz_offset_hours=5))  # «перезапуск» сервера
    assert client_b.post("/api/trips", json=NEW_TRIP).status_code == 200
    assert len(json.loads(data_file.read_text(encoding="utf-8"))) == 3


def test_concurrent_resends_create_one_trip(client):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(lambda _: client.post("/api/trips", json=NEW_TRIP).status_code, range(8)))
    assert sorted(codes) == [200] * 7 + [201]
    assert day(client)["summary"]["trips_count"] == 3
