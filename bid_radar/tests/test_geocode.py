"""
The geocoder.

What matters here is not that it resolves an address — the Census does that —
but that it refuses to invent one. The probe on 2026-09-14 showed the failure
mode that makes this necessary: 1050 Water St came back "Tie", because Water
Street is new construction and the TIGER road file has not caught up. A
geocoder that guessed at that would put a real lead in the wrong submarket.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import geocode  # noqa: E402

# Verbatim from the Census batch endpoint, 2026-09-14.
REAL_RESPONSE = (
    '"1","1050 Water St, Tampa, FL, 33602","Tie"\n'
    '"2","1616 E 7th Ave, Tampa, FL, 33605","Match","Exact",'
    '"1616 E 7TH AVE, TAMPA, FL, 33605","-82.441460343028,27.960332331173",'
    '"104524202","L"\n'
    '"3","253 N West Shore Blvd, Tampa, FL, 33609","Match","Exact",'
    '"253 N WEST SHORE BLVD, TAMPA, FL, 33609","-82.524155107224,27.946456976484",'
    '"104524580","R"\n'
    '"0","999 Nowhere Rd, Tampa, FL, 33602","No_Match"\n'
)


#: Keyed by the address the Census echoes back, so a stub response can be
#: assembled for whatever ids a caller actually sends — the real service
#: echoes the id it was given, and a fixed-id stub would not test the mapping.
BY_STREET = {
    "1050 WATER ST": '"{id}","{a}","Tie"',
    "1616 E 7TH AVE": ('"{id}","{a}","Match","Exact","1616 E 7TH AVE, TAMPA, FL, 33605",'
                       '"-82.441460343028,27.960332331173","104524202","L"'),
    "253 N WEST SHORE BLVD": ('"{id}","{a}","Match","Exact",'
                              '"253 N WEST SHORE BLVD, TAMPA, FL, 33609",'
                              '"-82.524155107224,27.946456976484","104524580","R"'),
}


class _Resp:
    status_code = 200
    text = REAL_RESPONSE


def _echo(*args, **kwargs):
    """Stub that answers with the ids it was actually given."""
    sent = kwargs.get("files", {}).get("addressFile", (None, "", None))[1]
    lines = []
    for row in csv.reader(io.StringIO(sent)):
        if len(row) < 5:
            continue
        rid, street = row[0], row[1].strip().upper()
        tmpl = BY_STREET.get(street)
        addr = f"{row[1]}, {row[2]}, {row[3]}, {row[4]}"
        lines.append(tmpl.format(id=rid, a=addr) if tmpl
                     else f'"{rid}","{addr}","No_Match"')

    class R:
        status_code = 200
        text = "\n".join(lines) + "\n"
    return R()


def test_a_tie_resolves_to_nothing_rather_than_a_guess(monkeypatch):
    """The exact case seen live: Water Street is too new for TIGER."""
    monkeypatch.setattr(geocode.requests, "post", lambda *a, **k: _Resp())
    got = geocode._post_batch([("1", "1050 Water St", "Tampa", "FL", "33602")])
    assert "1" not in got


def test_a_no_match_resolves_to_nothing(monkeypatch):
    monkeypatch.setattr(geocode.requests, "post", lambda *a, **k: _Resp())
    got = geocode._post_batch([("0", "999 Nowhere Rd", "Tampa", "FL", "33602")])
    assert "0" not in got


def test_a_real_match_returns_lon_lat_in_that_order(monkeypatch):
    """The Census writes "lon,lat"; getting it backwards puts Tampa in Somalia."""
    monkeypatch.setattr(geocode.requests, "post", lambda *a, **k: _Resp())
    got = geocode._post_batch([("2", "1616 E 7th Ave", "Tampa", "FL", "33605")])
    lon, lat = got["2"]
    assert -83 < lon < -82          # longitude is negative in Florida
    assert 27 < lat < 29


def test_a_resolved_address_lands_in_the_submarket_arcgis_agrees_with(monkeypatch):
    """A 200 is not enough. The coordinates have to fall in the same polygon
    the ArcGIS geometry put that address in."""
    import geo
    monkeypatch.setattr(geocode.requests, "post", lambda *a, **k: _Resp())
    got = geocode._post_batch([("2", "1616 E 7th Ave", "Tampa", "FL", "33605"),
                               ("3", "253 N West Shore Blvd", "Tampa", "FL", "33609")])
    assert geo.hood_of(*got["2"]) == "ybor"
    assert geo.hood_of(*got["3"]) == "airport"


def test_the_cache_key_is_insensitive_to_case_and_spacing():
    a = geocode.key("1616 E 7th Ave", "Tampa", "FL", "33605")
    b = geocode.key("  1616   e 7TH ave ", "TAMPA", "fl", "33605")
    assert a == b


def test_an_unresolved_signal_keeps_no_hood_and_says_so(monkeypatch, tmp_path):
    monkeypatch.setattr(geocode, "CACHE_PATH", str(tmp_path / "g.json"))
    monkeypatch.setattr(geocode.requests, "post", _echo)
    sigs = [{"address": "1050 Water St, Tampa", "zip": "33602",
             "needs_geocode": True, "hood": None}]
    stats = geocode.resolve_signals(sigs)
    assert stats["resolved"] == 0
    assert sigs[0]["hood"] is None
    assert sigs[0]["needs_geocode"] is True      # still honest about not knowing


def test_a_resolved_signal_is_placed_and_flagged(monkeypatch, tmp_path):
    monkeypatch.setattr(geocode, "CACHE_PATH", str(tmp_path / "g.json"))
    monkeypatch.setattr(geocode.requests, "post", _echo)
    sigs = [{"address": "1616 E 7th Ave, Tampa", "zip": "33605",
             "needs_geocode": True, "hood": None}]
    stats = geocode.resolve_signals(sigs)
    assert stats["resolved"] == 1 and stats["placed"] == 1
    assert sigs[0]["hood"] == "ybor"
    assert sigs[0]["needs_geocode"] is False
    assert sigs[0]["geocoded_by"] == "census"


def test_a_miss_is_cached_so_a_bad_address_is_not_re_sent_every_run(monkeypatch, tmp_path):
    monkeypatch.setattr(geocode, "CACHE_PATH", str(tmp_path / "g.json"))
    calls = []

    def once(*a, **k):
        calls.append(1)
        return _echo(*a, **k)

    monkeypatch.setattr(geocode.requests, "post", once)
    addr = [("1050 Water St", "Tampa", "FL", "33602")]
    geocode.resolve(addr)
    geocode.resolve(addr)
    assert len(calls) == 1
    assert geocode.load_cache()[geocode.key(*addr[0])] == geocode.MISS
