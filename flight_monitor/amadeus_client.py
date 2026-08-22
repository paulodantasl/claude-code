"""Amadeus Flight Offers Search client."""

from __future__ import annotations

import os
import time
from typing import Any

import requests

from storage import FlightOffer

TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
PROD_TOKEN_URL = "https://api.amadeus.com/v1/security/oauth2/token"
SEARCH_URL_TEST = "https://test.api.amadeus.com/v2/shopping/flight-offers"
SEARCH_URL_PROD = "https://api.amadeus.com/v2/shopping/flight-offers"

_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}


def _get_credentials() -> tuple[str, str]:
    key = os.environ.get("AMADEUS_API_KEY", "")
    secret = os.environ.get("AMADEUS_API_SECRET", "")
    if not key or not secret:
        raise RuntimeError(
            "AMADEUS_API_KEY and AMADEUS_API_SECRET must be set. "
            "Register free at https://developers.amadeus.com/register"
        )
    return key, secret


def _use_production() -> bool:
    return os.environ.get("AMADEUS_ENV", "test").lower() == "production"


def get_access_token() -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["token"]

    key, secret = _get_credentials()
    url = PROD_TOKEN_URL if _use_production() else TOKEN_URL
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": key,
            "client_secret": secret,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 1799))
    return _token_cache["token"]


def google_flights_url(
    origin: str,
    destination: str,
    departure: str,
    return_date: str,
    adults: int,
    children: int,
) -> str:
    """Build a Google Flights search URL for manual verification."""
    # Format: https://www.google.com/travel/flights?q=Flights%20from%20TPA%20to%20NAT%20on%202026-12-20%20returning%202027-01-03
    pax = f"{adults}%20adults"
    if children:
        pax += f"%20{children}%20children"
    query = (
        f"Flights from {origin} to {destination} on {departure} "
        f"returning {return_date} {pax}"
    )
    from urllib.parse import quote

    return f"https://www.google.com/travel/flights?q={quote(query)}"


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
) -> list[FlightOffer]:
    token = get_access_token()
    base = SEARCH_URL_PROD if _use_production() else SEARCH_URL_TEST
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure,
        "returnDate": return_date,
        "adults": adults,
        "children": children,
        "currencyCode": currency,
        "max": max_offers,
        "travelClass": travel_class,
        "nonStop": "false",
    }
    resp = requests.get(
        base,
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=60,
    )
    if resp.status_code == 401:
        _token_cache["token"] = None
        token = get_access_token()
        resp = requests.get(
            base,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=60,
        )
    resp.raise_for_status()
    data = resp.json()
    return _parse_offers(
        data,
        origin=origin,
        destination=destination,
        departure=departure,
        return_date=return_date,
        stay_days=stay_days,
        adults=adults,
        children=children,
        currency=currency,
    )


def _parse_offers(
    data: dict,
    origin: str,
    destination: str,
    departure: str,
    return_date: str,
    stay_days: int,
    adults: int,
    children: int,
    currency: str,
) -> list[FlightOffer]:
    offers: list[FlightOffer] = []
    carrier_dict = data.get("dictionaries", {}).get("carriers", {})
    carriers: dict[str, str] = {}
    if isinstance(carrier_dict, dict):
        carriers = {code: str(name) for code, name in carrier_dict.items()}

    for item in data.get("data", []):
        price = float(item["price"]["grandTotal"])
        cur = item["price"].get("currency", currency)
        itineraries = item.get("itineraries", [])
        segments_out = itineraries[0]["segments"] if itineraries else []
        segments_in = itineraries[1]["segments"] if len(itineraries) > 1 else []
        all_segments = segments_out + segments_in
        stops = max(0, len(segments_out) - 1) + max(0, len(segments_in) - 1)
        duration = sum(int(it.get("duration", "PT0M").replace("PT", "").replace("H", " ").replace("M", "").split()[0] or 0) * 60 for it in itineraries)  # rough
        airline_codes = list({s["carrierCode"] for s in all_segments})
        airline_names = ", ".join(carriers.get(c, c) for c in airline_codes)
        link = google_flights_url(origin, destination, departure, return_date, adults, children)
        offers.append(
            FlightOffer(
                origin=origin,
                destination=destination,
                departure_date=departure,
                return_date=return_date,
                stay_days=stay_days,
                total_price_usd=price,
                currency=cur,
                airline=airline_names,
                stops=stops,
                duration_minutes=duration or None,
                booking_link=link,
                source="amadeus",
                raw_summary=f"{airline_names} | {stops} stops | {cur} {price:.2f}",
            )
        )
    return offers
