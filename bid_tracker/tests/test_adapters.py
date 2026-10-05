import json
import shutil
import subprocess
from datetime import date

import pytest

from bid_tracker.adapters import bls_ppi
from bid_tracker.db import load_sources
from bid_tracker.importer import import_package
from bid_tracker.pdftext import extract_text, parse_pages


def fake_bls_payload(series_ids, drop=None):
    series = []
    for sid in series_ids:
        if sid == drop:
            continue
        series.append({"seriesID": sid, "data": [
            {"year": "2026", "period": "M08", "value": "110.0", "footnotes": [{"code": "P", "text": "preliminary"}]},
            {"year": "2025", "period": "M13", "value": "105.0", "footnotes": [{}]},
            {"year": "2025", "period": "M01", "value": "100.0", "footnotes": [{}]},
        ]})
    return {"status": "REQUEST_SUCCEEDED", "Results": {"series": series}}


def test_parse_bls_drops_annual_and_flags_preliminary():
    rows = bls_ppi.parse_bls(fake_bls_payload(["X"]), "2026-10-01")
    assert [(r["period"], r["value"], r["preliminary"]) for r in rows] == [("2026-08", 110.0, 1), ("2025-01", 100.0, 0)]
    with pytest.raises(bls_ppi.BLSError):
        bls_ppi.parse_bls({"status": "REQUEST_NOT_PROCESSED", "message": ["limit"]}, "2026-10-01")


def test_build_package_and_import(conn, tmp_path, monkeypatch):
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    ids = [s["series_id"] for s in load_sources()["cost_index_series"]]
    seen = {}

    def fetch(url, data, headers):
        seen["url"], seen["body"] = url, json.loads(data)
        return json.dumps(fake_bls_payload(ids)).encode()

    out, n = bls_ppi.build_package(tmp_path / "idx", fetch=fetch, today=date(2026, 10, 1))
    assert n == 2 * len(ids)
    assert seen["url"].endswith("/v1/timeseries/data/") and seen["body"]["startyear"] == "2017"
    res = import_package(conn, out)
    assert res.status == "ok" and res.index_rows == n


def test_api_key_falls_back_to_the_private_key_file(tmp_path, monkeypatch):
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    assert bls_ppi.api_key() is None
    key_file = tmp_path / "data" / bls_ppi.KEY_FILE          # conftest points BID_TRACKER_DATA at tmp/data
    key_file.parent.mkdir(parents=True)
    key_file.write_text("fake-key-0000\n")
    assert bls_ppi.api_key() == "fake-key-0000"
    ids = [s["series_id"] for s in load_sources()["cost_index_series"]]
    seen = {}

    def fetch(url, data, headers):
        seen["url"], seen["body"] = url, json.loads(data)
        return json.dumps(fake_bls_payload(ids)).encode()

    bls_ppi.build_package(tmp_path / "idx", fetch=fetch, today=date(2026, 10, 1))
    assert seen["url"].endswith("/v2/timeseries/data/") and seen["body"]["registrationkey"] == "fake-key-0000"
    monkeypatch.setenv("BLS_API_KEY", "env-key")              # the environment wins over the file
    assert bls_ppi.api_key() == "env-key"


def test_bls_error_never_echoes_the_key(tmp_path, monkeypatch):
    monkeypatch.setenv("BLS_API_KEY", "secret-123")
    fetch = lambda url, data, headers: json.dumps(
        {"status": "REQUEST_NOT_PROCESSED", "message": ["The key:secret-123 provided by the User is invalid."]}).encode()
    with pytest.raises(bls_ppi.BLSError) as err:
        bls_ppi.build_package(tmp_path / "idx", fetch=fetch)
    assert "secret-123" not in str(err.value) and err.value.__cause__ is None


def test_missing_series_is_a_hard_error(tmp_path):
    ids = [s["series_id"] for s in load_sources()["cost_index_series"]]
    fetch = lambda url, data, headers: json.dumps(fake_bls_payload(ids, drop=ids[0])).encode()
    with pytest.raises(bls_ppi.BLSError, match=ids[0]):
        bls_ppi.build_package(tmp_path / "idx", fetch=fetch)


def test_parse_pages():
    assert parse_pages("1-3,5") == [1, 2, 3, 5]
    assert parse_pages(None) is None


@pytest.mark.skipif(not (shutil.which("pdftotext") and shutil.which("gs")),
                    reason="needs poppler and a PDF writer")
def test_pdf_text_roundtrip(tmp_path):
    ps = tmp_path / "t.ps"
    ps.write_text("%!PS\n/Helvetica findfont 12 scalefont setfont 72 720 moveto (FAKE TAB LOW 100000.00) show showpage\n")
    pdf = tmp_path / "t.pdf"
    subprocess.run(["gs", "-q", "-sDEVICE=pdfwrite", "-o", str(pdf), str(ps)], check=True)
    assert "FAKE TAB LOW 100000.00" in extract_text(pdf)


@pytest.mark.integration
def test_live_bls(tmp_path):
    out, n = bls_ppi.build_package(tmp_path / "idx")
    assert n > 0
