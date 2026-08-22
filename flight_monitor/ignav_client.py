"""Ignav Flight Prices API client."""

from __future__ import annotations

import os
from typing import Any

import requests

from storage import FlightOffer

BASE_URL = "https://ignav.com/api"
ROUND_TRIP_URL = f"{BASE_URL}/fares/round-trip"
BOOKING_LINKS_URL = f"{BASE_URL}/fares/booking-links"


def _api_key() -> str:
    key = os.environ.get("IGNAV_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "IGNAV_API_KEY must be set. Sign up at https://ignav.com"
        )
    return key


def _headers() -> dict[str, str]:
    return {
        "X-Api-Key": _api_key(),
        "Content-Type": "application/json",
    }


def google_flights_url(
    origin: str,
    destination: str,
    departure: str,
    return_date: str,
    adults: int,
    children: int,
) -> str:
    from urllib.parse import quote

    pax = f"{adults} adults"
    if children:
        pax += f" {children} children"
    query = (
        f"Flights from {origin} to {destination} on {departure} "
        f"returning {return_date} {pax}"
    )
    return f"https://www.google.com/travel/flights?q={quote(query)}"


def fetch_booking_link(ignav_id: str) -> str:
    resp = requests.post(
        BOOKING_LINKS_URL,
        headers=_headers(),
        json={"ignav_id": ignav_id},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    links = data.get("links") or data.get("booking_links") or []
    if isinstance(links, list) and links:
        first = links[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("link") or ""
    return data.get("url") or data.get("booking_url") or ""


def _count_stops(leg: dict | None) -> int:
    if not leg:
        return 0
    segments = leg.get("segments") or []
    return max(0, len(segments) - 1)


def _leg_duration(leg: dict | None) -> int:
    if not leg:
        return 0
    if leg.get("duration_minutes") is not None:
        return int(leg["duration_minutes"])
    return sum(int(s.get("duration_minutes") or 0) for s in leg.get("segments") or [])


def _leg_carrier(leg: dict | None) -> str:
    if not leg:
        return ""
    if leg.get("carrier"):
        return str(leg["carrier"])
    segments = leg.get("segments") or []
    carriers = []
    for seg in segments:
        name = seg.get("operating_carrier_name") or seg.get("marketing_carrier_code")
        if name and name not in carriers:
            carriers.append(str(name))
    return ", ".join(carriers)


def search_flights(
    origin: str,
    destination: str,
    departure: str,
    return_date: str,
    adults: int,
    children: int,
    currency: str = "USD",
    max_offers: int = 5,
    travel_class: str = "ECONOMY",
    stay_days: int = 14,
    market: str = "US",
    fetch_booking_links: bool = False,
) -> list[FlightOffer]:
    cabin = travel_class.lower().replace("_", " ")
    if cabin == "economy":
        cabin_class = "economy"
    elif cabin in {"premium economy", "premium_economy"}:
        cabin_class = "premium_economy"
    elif cabin == "business":
        cabin_class = "business"
    elif cabin == "first":
        cabin_class = "first"
    else:
        cabin_class = "economy"

    payload: dict[str, Any] = {
        "origin": origin,
        "destination": destination,
        "departure_date": departure,
        "return_date": return_date,
        "adults": adults,
        "children": children,
        "cabin_class": cabin_class,
        "market": market,
    }

    resp = requests.post(
        ROUND_TRIP_URL,
        headers=_headers(),
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    itineraries = data.get("itineraries") or []
    offers: list[FlightOffer] = []

    for item in itineraries[:max_offers]:
        price_info = item.get("price") or {}
        amount = float(price_info.get("amount") or 0)
        cur = price_info.get("currency") or currency
        outbound = item.get("outbound")
        inbound = item.get("inbound")
        stops = _count_stops(outbound) + _count_stops(inbound)
        duration = _leg_duration(outbound) + _leg_duration(inbound)
        carriers = " / ".join(
            c for c in [_leg_carrier(outbound), _leg_carrier(inbound)] if c
        )
        ignav_id = item.get("ignav_id") or ""
        booking_link = google_flights_url(
            origin, destination, departure, return_date, adults, children
        )
        if ignav_id and fetch_booking_links:
            try:
                link = fetch_booking_link(ignav_id)
                if link:
                    booking_link = link
            except Exception:
                pass

        status = price_info.get("status", "")
        offers.append(
            FlightOffer(
                origin=origin,
                destination=destination,
                departure_date=departure,
                return_date=return_date,
                stay_days=stay_days,
                total_price_usd=amount,
                currency=cur,
                airline=carriers,
                stops=stops,
                duration_minutes=duration or None,
                booking_link=booking_link,
                source="ignav",
                raw_summary=f"{carriers} | {stops} stops | {cur} {amount:.2f} ({status})",
            )
        )

    return offers
