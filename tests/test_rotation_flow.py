from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.rotation_flow import (
    dollar_volume_shares,
    dollar_volume_wide,
    net_flow_ledger,
    rotation_intensity,
    share_shift,
)


def _frame(closes, volumes, start="2026-01-01"):
    index = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({"close": closes, "volume": volumes}, index=index)


def test_dollar_volume_wide_aligns_and_drops_gaps():
    prices = {
        "XLK": _frame([10.0, 11.0, 12.0], [100, 100, 100]),
        "XLF": _frame([20.0, 20.0], [50, 50], start="2026-01-02"),
    }

    wide = dollar_volume_wide(prices, ["XLK", "XLF", "XLE"])

    assert list(wide.columns) == ["XLK", "XLF"]
    assert len(wide) == 2
    assert wide.iloc[0]["XLK"] == pytest.approx(1100.0)
    assert wide.iloc[0]["XLF"] == pytest.approx(1000.0)


def test_shares_sum_to_one_on_every_date():
    wide = pd.DataFrame({"A": [1.0, 3.0], "B": [3.0, 1.0]})

    shares = dollar_volume_shares(wide)

    assert np.allclose(shares.sum(axis=1), 1.0)
    assert shares.iloc[0]["A"] == pytest.approx(0.25)


def test_share_shift_is_positive_when_recent_share_exceeds_baseline():
    # A takes 50% of volume for 60 days, then 90% for the next 20 days.
    a = [50.0] * 60 + [90.0] * 20
    b = [50.0] * 80
    shares = dollar_volume_shares(pd.DataFrame({"A": a, "B": b}))

    shifts = share_shift(shares, short=20, long=60)

    assert np.isnan(shifts["A"].iloc[58])
    last = shifts.iloc[-1]
    # recent 20 days: A = 90/(90+50) = 0.6429; 60-day baseline: 40 days at 0.5, 20 at 0.6429
    assert last["A"] > 0
    assert last["A"] + last["B"] == pytest.approx(0.0)


def test_shifts_sum_to_zero_across_sectors():
    rng = np.random.default_rng(7)
    wide = pd.DataFrame(rng.uniform(1, 10, size=(90, 4)), columns=list("ABCD"))

    shifts = share_shift(dollar_volume_shares(wide), short=5, long=20).dropna()

    assert np.allclose(shifts.sum(axis=1), 0.0)


def test_net_flow_ledger_pairs_outflows_with_inflows_and_balances():
    shifts = pd.Series({"XLK": 0.05, "XLF": 0.02, "XLE": -0.03, "XLU": -0.04, "XLP": 0.0})

    ledger = net_flow_ledger(shifts, top_n=3)

    assert ledger[0] == {"from": "XLU", "to": "XLK", "amount": 0.04}
    assert ledger[1] == {"from": "XLE", "to": "XLK", "amount": 0.01}
    assert ledger[2] == {"from": "XLE", "to": "XLF", "amount": 0.02}
    assert sum(item["amount"] for item in ledger) == pytest.approx(0.07)


def test_net_flow_ledger_is_empty_without_both_sides():
    assert net_flow_ledger(pd.Series({"XLK": 0.02, "XLF": 0.01})) == []


def test_rotation_intensity_is_zero_when_nothing_moves():
    shifts = pd.DataFrame({"A": [0.0, 0.1], "B": [0.0, -0.1]})

    assert list(rotation_intensity(shifts)) == [0.0, 0.2]
