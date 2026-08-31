#!/usr/bin/env python3
"""Offline tests for the v3 pipeline — no API key, no network.

Covers the logic the prompt calls out as the rough edges:
  - dedupe() merges "Huel" + "Huel Ltd" (seen in two signal groups) into ONE
    Verified+ row.
  - icp_fit() returns "unknown" when a source never stated headcount.

Run:  python -m pytest pipeline/scripts/tests/ -q
  or:  python pipeline/scripts/tests/test_pipeline.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run_search import dedupe, icp_fit, norm  # noqa: E402


def test_norm_strips_company_suffixes():
    assert norm("Huel") == norm("Huel Ltd") == "huel"
    assert norm("Acme, Inc.") == "acme"


def test_dedupe_merges_same_domain_into_verified_plus():
    rows = [
        {"company": "Huel", "domain": "huel.com", "signal_group": "own_site",
         "confidence": "Verified", "quote": "q1", "source_url": "https://a"},
        {"company": "Huel Ltd", "domain": "huel.com", "signal_group": "job_postings",
         "confidence": "Verified", "quote": "q2", "source_url": "https://b"},
    ]
    out = dedupe(rows)
    assert len(out) == 1, "same-domain rows must collapse to one company"
    assert out[0]["confidence"] == "Verified+", "2+ signal groups => Verified+"
    assert set(out[0]["signal_group"].split(" + ")) == {"own_site", "job_postings"}


def test_dedupe_merges_by_normalised_name_when_no_domain():
    rows = [
        {"company": "Huel", "domain": "", "signal_group": "blog_press",
         "confidence": "Verified", "quote": "q1", "source_url": "https://a"},
        {"company": "Huel Ltd", "domain": "", "signal_group": "review_sites",
         "confidence": "Likely", "quote": "q2", "source_url": "https://b"},
    ]
    out = dedupe(rows)
    assert len(out) == 1, "Huel and Huel Ltd normalise to the same key"
    assert out[0]["confidence"] == "Verified+"


def test_dedupe_keeps_distinct_companies_apart():
    rows = [
        {"company": "Huel", "domain": "huel.com", "signal_group": "own_site",
         "confidence": "Verified", "quote": "q", "source_url": "https://a"},
        {"company": "Gymshark", "domain": "gymshark.com", "signal_group": "own_site",
         "confidence": "Verified", "quote": "q", "source_url": "https://b"},
    ]
    assert len(dedupe(rows)) == 2


def test_icp_fit_unknown_when_employees_null():
    assert icp_fit({"employees": None, "country": "UK"}) == "unknown"
    assert icp_fit({"employees": "", "country": "UK"}) == "unknown"
    assert icp_fit({"country": "UK"}) == "unknown"


def test_icp_fit_core_when_size_and_geo_match():
    # geo match is a case-insensitive SUBSTRING test of the ICP country ("UK")
    # against the row's country, so rows must carry the code, e.g. "UK".
    assert icp_fit({"employees": "250 Employees", "country": "UK"}) == "core"


def test_icp_fit_geo_is_substring_match_not_country_name():
    # Sharp edge (documented, not fixed here): "United Kingdom" does NOT contain
    # the substring "uk", so it scores size_only, not core. Sources that spell the
    # country out rather than using the code lose the geo match.
    assert icp_fit({"employees": "250", "country": "United Kingdom"}) == "size_only"


def test_icp_fit_size_only_when_geo_wrong():
    assert icp_fit({"employees": "250", "country": "Germany"}) == "size_only"


def test_icp_fit_outside_when_too_big():
    assert icp_fit({"employees": "50,000 employees", "country": "UK"}) == "outside"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
