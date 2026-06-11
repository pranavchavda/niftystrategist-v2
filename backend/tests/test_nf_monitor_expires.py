"""Regression tests for cli-tools/nf-monitor:_parse_expires().

Guards against the premature-expiry footgun: a bare date like
"2026-06-12" used to parse as midnight UTC (05:30 IST) — before market
open — so the rule silently expired before it could ever fire.

Incident: 2026-06-11, rule #4480 (IDEA re-entry) was staged for the next
trading day with --expires 2026-06-12 and would have been dead on arrival.
"""
import importlib.machinery
import importlib.util
import os
import sys
from datetime import datetime

import pytest

_CLI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cli-tools")
if _CLI_DIR not in sys.path:
    sys.path.insert(0, _CLI_DIR)


@pytest.fixture(scope="module")
def nfmon():
    loader = importlib.machinery.SourceFileLoader("nfmon", os.path.join(_CLI_DIR, "nf-monitor"))
    spec = importlib.util.spec_from_loader("nfmon", loader)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nfmon"] = mod
    loader.exec_module(mod)
    return mod


def test_date_only_means_market_close_that_day(nfmon):
    assert nfmon._parse_expires("2026-06-12") == datetime(2026, 6, 12, 10, 0, 0)


def test_iso_datetime_within_market_hours_kept_no_warning(nfmon, capsys):
    assert nfmon._parse_expires("2026-06-12T09:00:00") == datetime(2026, 6, 12, 9, 0, 0)
    assert "WARNING" not in capsys.readouterr().err


def test_explicit_midnight_kept_but_warns(nfmon, capsys):
    assert nfmon._parse_expires("2026-06-12T00:00:00") == datetime(2026, 6, 12, 0, 0, 0)
    assert "outside NSE market hours" in capsys.readouterr().err


def test_tz_aware_converted_to_naive_utc(nfmon):
    assert nfmon._parse_expires("2026-06-12T15:30:00+05:30") == datetime(2026, 6, 12, 10, 0, 0)


def test_today_returns_market_close(nfmon):
    result = nfmon._parse_expires("today")
    assert (result.hour, result.minute) == (10, 0)
    assert result > datetime.utcnow()
