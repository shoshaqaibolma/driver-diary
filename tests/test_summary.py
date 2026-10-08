from datetime import date, timedelta, timezone

from app.models import Trip
from app.summary import summarize, trips_for_day

TZ = timezone(timedelta(hours=5))


def trip(id, start, end, amount, payment, commission):
    return Trip(id=id, start=start, end=end, amount=amount, payment=payment, commission=commission)


SAMPLE = [
    trip("t1", "2026-10-01T08:10:00+05:00", "2026-10-01T08:32:00+05:00", 2400, "card", 360),
    trip("t2", "2026-10-01T09:05:00+05:00", "2026-10-01T09:20:00+05:00", 1500, "cash", 225),
]


def test_summary_of_sample_from_task():
    s = summarize(SAMPLE)
    assert s.trips_count == 2
    assert s.revenue == 3900
    assert s.commission == 585
    assert s.net == 3315
    assert (s.cash.count, s.cash.amount) == (1, 1500)
    assert (s.card.count, s.card.amount) == (1, 2400)


def test_summary_of_empty_day_is_zero():
    s = summarize([])
    assert (s.trips_count, s.revenue, s.commission, s.net) == (0, 0, 0, 0)
    assert s.cash.amount == s.card.amount == 0


def test_cash_and_card_add_up_to_revenue():
    trips = SAMPLE + [trip("t3", "2026-10-01T10:00:00+05:00", "2026-10-01T10:30:00+05:00", 3000, "cash", 450)]
    s = summarize(trips)
    assert s.cash.amount + s.card.amount == s.revenue == 6900
    assert s.cash.count + s.card.count == s.trips_count == 3


def test_day_is_taken_in_driver_timezone():
    # 01:30 по Алматы 2 октября = 20:30 UTC 1 октября; должна попасть во 2 октября.
    early = trip("e", "2026-10-01T20:30:00+00:00", "2026-10-01T20:50:00+00:00", 1000, "cash", 150)
    assert trips_for_day([early], date(2026, 10, 2), TZ) == [early]
    assert trips_for_day([early], date(2026, 10, 1), TZ) == []


def test_trip_over_midnight_belongs_to_start_day():
    night = trip("n", "2026-10-01T23:40:00+05:00", "2026-10-02T00:10:00+05:00", 2800, "card", 420)
    assert trips_for_day([night], date(2026, 10, 1), TZ) == [night]
    assert trips_for_day([night], date(2026, 10, 2), TZ) == []


def test_trips_for_day_sorted_by_start():
    later, earlier = SAMPLE[1], SAMPLE[0]
    assert trips_for_day([later, earlier], date(2026, 10, 1), TZ) == [earlier, later]
