from bid_tracker.names import name_key, near_matches


def test_name_key_collapses_variants():
    assert name_key("ABC Construction, Inc.") == name_key("A.B.C. Construction Inc") == "abc construction"
    assert name_key("Smith & Sons Co.") == "smith and sons"
    assert name_key("Ideal Remodeling LLC dba Ideal Construction") == "ideal remodeling"
    assert name_key("The Hennessy Group, LLC") == "hennessy group"


def test_fuzzy_matches_are_suggestions_only():
    known = {"keystone builders": "Keystone Builders Inc", "kingston builders": "Kingston Builders LLC"}
    hits = near_matches("Keystone Bulders", known)
    assert hits and hits[0][0] == "Keystone Builders Inc"
    assert near_matches("Keystone Builders", {"keystone builders": "x"}) == []
