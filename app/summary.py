from datetime import date, timezone, tzinfo

from .models import DaySummary, PaymentBreakdown, Trip


def trip_day(trip: Trip, tz: tzinfo) -> date:
    """День поездки — дата её начала в часовом поясе водителя (поездка через полночь относится к дню начала)."""
    return trip.start.astimezone(tz).date()


def trips_for_day(trips: list[Trip], day: date, tz: tzinfo = timezone.utc) -> list[Trip]:
    return sorted((t for t in trips if trip_day(t, tz) == day), key=lambda t: t.start)


def summarize(trips: list[Trip]) -> DaySummary:
    revenue = sum(t.amount for t in trips)
    commission = sum(t.commission for t in trips)
    cash = [t for t in trips if t.payment == "cash"]
    card = [t for t in trips if t.payment == "card"]
    return DaySummary(
        trips_count=len(trips),
        revenue=revenue,
        commission=commission,
        net=revenue - commission,
        cash=PaymentBreakdown(count=len(cash), amount=sum(t.amount for t in cash)),
        card=PaymentBreakdown(count=len(card), amount=sum(t.amount for t in card)),
    )
