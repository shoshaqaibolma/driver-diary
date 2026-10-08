from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TripIn(BaseModel):
    """Поездка, приходящая через API. id необязателен: если его нет, он выводится из содержимого."""

    id: str | None = Field(default=None, min_length=1, max_length=64)
    start: datetime
    end: datetime
    amount: int = Field(gt=0, description="Сумма поездки в тенге, > 0")
    payment: Literal["cash", "card"]
    commission: int = Field(ge=0, description="Комиссия сервиса в тенге, >= 0")

    @field_validator("start", "end")
    @classmethod
    def must_have_timezone(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("время должно содержать часовой пояс, например 2026-10-01T08:10:00+05:00")
        return v

    @model_validator(mode="after")
    def check_consistency(self) -> "TripIn":
        if self.end <= self.start:
            raise ValueError("время окончания должно быть позже времени начала")
        if self.commission > self.amount:
            raise ValueError("комиссия не может превышать сумму поездки")
        return self


class Trip(TripIn):
    id: str


class PaymentBreakdown(BaseModel):
    count: int
    amount: int


class DaySummary(BaseModel):
    trips_count: int
    revenue: int
    commission: int
    net: int
    cash: PaymentBreakdown
    card: PaymentBreakdown


class DayReport(BaseModel):
    date: str
    summary: DaySummary
    trips: list[Trip]
