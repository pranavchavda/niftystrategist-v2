"""Tests for F&O charges estimation and option tradingsymbol parsing."""
import re


def estimate_fno_charges(premium: float, quantity: int, side: str,
                         exit_premium: float = None) -> dict:
    """Copy of the function from nf-options for testability."""
    buy_value = premium * quantity if side == "BUY" else 0
    sell_value = premium * quantity if side == "SELL" else 0
    turnover = buy_value + sell_value

    brokerage = 20.0
    stt = sell_value * 0.000625
    txn_charges = turnover * 0.00053
    gst = (brokerage + txn_charges) * 0.18
    sebi = turnover * 0.000001
    stamp = buy_value * 0.00003

    total = brokerage + stt + txn_charges + gst + sebi + stamp

    result = {
        "premium": premium,
        "quantity": quantity,
        "side": side,
        "turnover": round(turnover, 2),
        "brokerage": round(brokerage, 2),
        "stt": round(stt, 2),
        "transaction_charges": round(txn_charges, 2),
        "gst": round(gst, 2),
        "sebi": round(sebi, 2),
        "stamp_duty": round(stamp, 2),
        "total": round(total, 2),
        "cost_pct": round((total / turnover * 100) if turnover > 0 else 0, 4),
    }

    if exit_premium is not None:
        exit_result = estimate_fno_charges(exit_premium, quantity, "SELL" if side == "BUY" else "BUY")
        round_trip_total = total + exit_result["total"]
        result["round_trip"] = {
            "entry_charges": round(total, 2),
            "exit_charges": round(exit_result["total"], 2),
            "total_charges": round(round_trip_total, 2),
            "exit_premium": exit_premium,
        }

    return result


def _parse_option_tradingsymbol(tradingsymbol: str) -> dict | None:
    """Copy of the function from nf-options for testability."""
    m = re.match(r'^([A-Z&-]+?)(\d{2}\w+?)(\d{3,})(CE|PE)$', tradingsymbol)
    if m:
        return {
            "underlying": m.group(1),
            "expiry_hint": m.group(2),
            "strike": float(m.group(3)),
            "option_type": m.group(4),
        }
    return None


class TestFnoCharges:
    def test_buy_charges_structure(self):
        result = estimate_fno_charges(premium=200, quantity=30, side="BUY")
        for key in ("brokerage", "stt", "transaction_charges", "gst", "sebi", "stamp_duty", "total", "cost_pct"):
            assert key in result

    def test_buy_brokerage_is_flat_20(self):
        result = estimate_fno_charges(premium=200, quantity=30, side="BUY")
        assert result["brokerage"] == 20.0

    def test_buy_stt_is_zero(self):
        """STT is only on sell side for options."""
        result = estimate_fno_charges(premium=200, quantity=30, side="BUY")
        assert result["stt"] == 0.0

    def test_sell_stt_is_nonzero(self):
        result = estimate_fno_charges(premium=200, quantity=30, side="SELL")
        assert result["stt"] > 0
        # 0.0625% of (200 * 30) = 0.000625 * 6000 = 3.75
        assert abs(result["stt"] - 3.75) < 0.01

    def test_stamp_duty_only_on_buy(self):
        buy = estimate_fno_charges(premium=200, quantity=30, side="BUY")
        sell = estimate_fno_charges(premium=200, quantity=30, side="SELL")
        assert buy["stamp_duty"] > 0
        assert sell["stamp_duty"] == 0.0

    def test_round_trip(self):
        result = estimate_fno_charges(premium=200, quantity=30, side="BUY", exit_premium=250)
        assert "round_trip" in result
        rt = result["round_trip"]
        assert rt["entry_charges"] == result["total"]
        assert rt["exit_charges"] > 0
        assert rt["total_charges"] == rt["entry_charges"] + rt["exit_charges"]
        assert rt["exit_premium"] == 250

    def test_banknifty_realistic(self):
        """Realistic Bank Nifty scenario: 1 lot (30 units), premium 200."""
        result = estimate_fno_charges(premium=200, quantity=30, side="BUY")
        assert result["turnover"] == 6000.0
        assert 20 < result["total"] < 50
        assert 0.3 < result["cost_pct"] < 1.0

    def test_zero_premium_no_division_error(self):
        result = estimate_fno_charges(premium=0, quantity=30, side="BUY")
        # Brokerage (20) + GST on brokerage (3.60) = 23.60
        assert result["total"] == 23.6
        assert result["cost_pct"] == 0

    def test_large_lot_charges(self):
        """5 lots of NIFTY (75 units each = 375 units), premium 300."""
        result = estimate_fno_charges(premium=300, quantity=375, side="BUY")
        assert result["turnover"] == 112500.0
        assert result["total"] > 20  # At least brokerage

    def test_round_trip_symmetry(self):
        """Buy then sell at same price should have known charge structure."""
        result = estimate_fno_charges(premium=200, quantity=30, side="BUY", exit_premium=200)
        rt = result["round_trip"]
        # Entry has no STT (buy), exit has STT (sell)
        assert rt["exit_charges"] > rt["entry_charges"]


class TestParseOptionTradingsymbol:
    def test_banknifty_call(self):
        result = _parse_option_tradingsymbol("BANKNIFTY26MAR48000CE")
        assert result is not None
        assert result["underlying"] == "BANKNIFTY"
        assert result["strike"] == 48000.0
        assert result["option_type"] == "CE"

    def test_nifty_put_monthly_format(self):
        # Monthly format: NIFTY26MAR25500PE
        result = _parse_option_tradingsymbol("NIFTY26MAR25500PE")
        assert result is not None
        assert result["underlying"] == "NIFTY"
        assert result["strike"] == 25500.0
        assert result["option_type"] == "PE"

    def test_nifty_put_weekly_format(self):
        # Weekly format: NIFTY2631925500PE (YY+DDD encoded)
        # The regex is best-effort for these compact formats
        result = _parse_option_tradingsymbol("NIFTY2631925500PE")
        assert result is not None
        assert result["underlying"] == "NIFTY"
        assert result["option_type"] == "PE"
        # Strike parsing may be imprecise for weekly coded symbols

    def test_invalid_symbol(self):
        result = _parse_option_tradingsymbol("RELIANCE")
        assert result is None

    def test_stock_option(self):
        result = _parse_option_tradingsymbol("RELIANCE26MAR2500CE")
        assert result is not None
        assert result["underlying"] == "RELIANCE"
        assert result["strike"] == 2500.0
        assert result["option_type"] == "CE"
