"""Tests for sector metadata + filtering in instruments_cache.

The Nifty 500 / Total Market constituent CSVs carry an ``Industry`` column;
these tests verify it's loaded into the symbol→sector map and that the
alias/substring matching used by ``nf-morning-scan --sector`` behaves.

Relies on the on-disk index caches (backend/.cache/*.csv) being present, which
they are in any working checkout. Reads are offline (no Upstox token needed).
"""
import services.instruments_cache as ic


def test_sectors_loaded():
    sectors = ic.list_sectors()
    assert "Information Technology" in sectors
    assert "Financial Services" in sectors
    assert "Healthcare" in sectors


def test_get_sector_known_symbols():
    assert ic.get_sector("TCS") == "Information Technology"
    assert ic.get_sector("INFY") == "Information Technology"
    assert ic.get_sector("RELIANCE") == "Oil Gas & Consumable Fuels"


def test_get_sector_unknown_returns_none():
    assert ic.get_sector("NOTAREALSYMBOL") is None


def test_match_alias_tech():
    assert ic.match_sectors("tech") == {"Information Technology"}
    assert ic.match_sectors("it") == {"Information Technology"}


def test_match_alias_pharma_and_bank():
    assert ic.match_sectors("pharma") == {"Healthcare"}
    assert ic.match_sectors("bank") == {"Financial Services"}


def test_match_exact_canonical_label():
    # The frontend dropdown sends the exact NSE label.
    assert ic.match_sectors("Information Technology") == {"Information Technology"}


def test_match_broad_term_unions():
    # "consumer" deliberately spans every consumer-* sector.
    matched = ic.match_sectors("consumer")
    assert "Fast Moving Consumer Goods" in matched
    assert "Consumer Durables" in matched
    assert "Consumer Services" in matched


def test_match_garbage_is_empty():
    assert ic.match_sectors("garbagexyz") == set()
    assert ic.match_sectors("") == set()


def test_every_matched_label_is_a_real_sector():
    real = set(ic.list_sectors())
    for term in ("tech", "pharma", "bank", "auto", "metal", "energy"):
        assert ic.match_sectors(term) <= real, term


# ── force_include (debug single stock) ───────────────────────────────────────
# Loads the CLI module's _build_symbol_universe offline (no Upstox token).
import importlib.util  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
from importlib.machinery import SourceFileLoader  # noqa: E402

_CLI = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "cli-tools", "nf-morning-scan")


def _load_scan_module():
    cli_dir = os.path.dirname(_CLI)
    if cli_dir not in sys.path:
        sys.path.insert(0, cli_dir)
    loader = SourceFileLoader("nf_morning_scan", _CLI)
    spec = importlib.util.spec_from_loader("nf_morning_scan", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def test_force_include_pulls_symbol_past_sector_filter():
    mod = _load_scan_module()
    # RELIANCE is Oil & Gas, so a tech-sector filter would normally exclude it.
    tech_only = mod._build_symbol_universe("nifty500", sector="tech")
    assert "RELIANCE" not in tech_only
    forced = mod._build_symbol_universe("nifty500", sector="tech",
                                        force_include="RELIANCE")
    assert "RELIANCE" in forced
    # The rest of the tech universe is preserved.
    assert set(tech_only) < set(forced)


def test_force_include_ignores_unresolvable_symbol():
    mod = _load_scan_module()
    base = mod._build_symbol_universe("nifty50")
    forced = mod._build_symbol_universe("nifty50", force_include="NOTAREALSYM")
    assert set(forced) == set(base)


def test_force_include_no_duplicate_when_already_present():
    mod = _load_scan_module()
    forced = mod._build_symbol_universe("nifty500", sector="tech",
                                        force_include="TCS")
    assert forced.count("TCS") == 1
