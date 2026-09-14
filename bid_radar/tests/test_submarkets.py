"""Acceptance test for the submarket polygons (PLAN.md §2.1)."""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geo  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _load(name: str) -> list[dict]:
    with open(os.path.join(FIXTURES, name)) as fh:
        return json.load(fh)["features"]


PERMITS = _load("permit_points.geojson")
PROJECTS = _load("projects.geojson")


@pytest.mark.parametrize("feat", PERMITS, ids=[f["properties"]["record_id"] for f in PERMITS])
def test_real_permit_points_resolve_to_the_right_submarket(feat):
    """The substantive test: real ArcGIS coordinates, resolved by precedence.

    A permit inside a tracked submarket must get that submarket, and a permit
    outside all of them must get None — a false positive costs a wasted call,
    a false negative loses the lead.
    """
    lon, lat = feat["geometry"]["coordinates"]
    assert geo.hood_of(lon, lat) == feat["properties"]["expect"], (
        f"{feat['properties']['record_id']} at {feat['properties']['address']} "
        f"resolved to {geo.hood_of(lon, lat)!r}; "
        f"containing polygons were {geo.hoods_containing(lon, lat)}"
    )


@pytest.mark.parametrize("feat", PROJECTS, ids=[f["properties"]["id"] for f in PROJECTS])
def test_tracker_projects_fall_inside_their_assigned_submarket(feat):
    """Every project in the tracker's P[] must lie inside its own polygon.

    Containment, not resolution: riverwalk and downtown deliberately overlap
    along Ashley Dr (the tracker files The Pendry under one and 601 N Ashley
    under the other), so a downtown project may also sit inside riverwalk.
    """
    lon, lat = feat["geometry"]["coordinates"]
    inside = geo.hoods_containing(lon, lat)
    assert feat["properties"]["expect"] in inside, (
        f"{feat['properties']['id']} ({feat['properties']['locator']}) "
        f"expected {feat['properties']['expect']!r}, inside {inside}"
    )


def test_every_tracked_submarket_has_a_project():
    assert {f["properties"]["expect"] for f in PROJECTS} == set(geo.all_hoods())


def test_precedence_covers_every_polygon_exactly_once():
    hoods = geo.all_hoods()
    assert len(hoods) == len(set(hoods)) == 8
