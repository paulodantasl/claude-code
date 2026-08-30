from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any

from ideal_apis.config import Settings
from ideal_apis.http import HTTPClient


def _as_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


class ScheduleService:
    """Working-day math for CPM schedules, draw schedules, and LD counts.

    Calendar days and working days differ by roughly 30 percent over a year, which is
    the difference between a defensible completion date and one that quietly slips.
    """

    BASE = "https://date.nager.at/api/v3"

    def __init__(self, http: HTTPClient, settings: Settings):
        self.http = http
        self.settings = settings
        self._cache: dict[tuple[int, str], set[date]] = {}

    def holidays(self, year: int, *, country: str = "US") -> list[dict[str, Any]]:
        return self.http.get(f"{self.BASE}/PublicHolidays/{year}/{country}", service="Nager.Date")

    def _holiday_dates(self, year: int, country: str) -> set[date]:
        key = (year, country)
        if key not in self._cache:
            self._cache[key] = {
                _as_date(h["date"]) for h in self.holidays(year, country=country) if h.get("date")
            }
        return self._cache[key]

    def is_working_day(self, day: str | date, *, country: str = "US") -> bool:
        d = _as_date(day)
        if d.weekday() >= 5:
            return False
        return d not in self._holiday_dates(d.year, country)

    def working_days(
        self,
        start: str | date,
        end: str | date,
        *,
        country: str = "US",
    ) -> dict[str, Any]:
        """Count working days between two dates, inclusive of both ends."""
        s, e = _as_date(start), _as_date(end)
        if e < s:
            s, e = e, s
        years = range(s.year, e.year + 1)
        holidays: set[date] = set()
        for year in years:
            holidays |= self._holiday_dates(year, country)

        total = (e - s).days + 1
        working = 0
        observed: list[str] = []
        for offset in range(total):
            d = s + timedelta(days=offset)
            if d.weekday() >= 5:
                continue
            if d in holidays:
                observed.append(d.isoformat())
                continue
            working += 1
        return {
            "start": s.isoformat(),
            "end": e.isoformat(),
            "calendar_days": total,
            "working_days": working,
            "weekend_days": sum(
                1 for o in range(total) if (s + timedelta(days=o)).weekday() >= 5
            ),
            "holidays_observed": observed,
        }

    def add_working_days(
        self,
        start: str | date,
        days: int,
        *,
        country: str = "US",
    ) -> dict[str, Any]:
        """Project a completion date N working days out — the durations-to-dates step."""
        d = _as_date(start)
        remaining = days
        step = 1 if days >= 0 else -1
        skipped: list[str] = []
        while remaining != 0:
            d += timedelta(days=step)
            if d.weekday() >= 5:
                continue
            if d in self._holiday_dates(d.year, country):
                skipped.append(d.isoformat())
                continue
            remaining -= step
        return {
            "start": _as_date(start).isoformat(),
            "working_days_added": days,
            "end": d.isoformat(),
            "holidays_skipped": skipped,
        }
