"""Sector-to-sector money flow from relative dollar-volume share.

A sector's share of the group's dollar volume is compared with its own recent
baseline. Shares sum to 1 across the group on every date, so the shifts sum to
0: a gain in one sector is always paid for by a loss in another. That makes
the output read directly as "money moved from X to Y".
"""
from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

SHORT_WINDOW = 20
LONG_WINDOW = 60


def dollar_volume_wide(
    prices: dict[str, pd.DataFrame],
    tickers: Iterable[str],
) -> pd.DataFrame:
    """Return close * volume per ticker, one column each, aligned by date.

    Rows where any requested ticker is missing are dropped so every date
    compares the same group.
    """
    columns = {}
    for ticker in tickers:
        frame = prices.get(ticker)
        if frame is None or frame.empty:
            continue
        if "close" not in frame or "volume" not in frame:
            continue
        columns[ticker] = (frame["close"].astype(float) * frame["volume"].astype(float))
    wide = pd.DataFrame(columns).sort_index()
    return wide.dropna(how="any")


def dollar_volume_shares(dollar_volume: pd.DataFrame) -> pd.DataFrame:
    """Each ticker's fraction of the group's total dollar volume, per date."""
    totals = dollar_volume.sum(axis=1)
    return dollar_volume.div(totals.where(totals > 0), axis=0)


def share_shift(
    shares: pd.DataFrame,
    short: int = SHORT_WINDOW,
    long: int = LONG_WINDOW,
) -> pd.DataFrame:
    """Recent share minus baseline share, per ticker, per date.

    Positive means the sector is taking more of the group's trading than its
    usual level. Rows before the long window fills are NaN.
    """
    return shares.rolling(short).mean() - shares.rolling(long).mean()


def net_flow_ledger(shifts: pd.Series, top_n: int = 3) -> list[dict]:
    """Pair the largest outflows with the largest inflows on one date.

    Each pair moves the smaller of the two magnitudes, so the amounts balance
    and nothing is double-counted. Zero shifts are ignored.
    """
    inflows = shifts[shifts > 0].sort_values(ascending=False).head(top_n)
    outflows = shifts[shifts < 0].sort_values().head(top_n)
    donors = [[name, -float(value)] for name, value in outflows.items()]
    receivers = [[name, float(value)] for name, value in inflows.items()]
    ledger: list[dict] = []
    d = r = 0
    while d < len(donors) and r < len(receivers):
        amount = min(donors[d][1], receivers[r][1])
        if amount > 0:
            ledger.append({
                "from": donors[d][0],
                "to": receivers[r][0],
                "amount": round(amount, 6),
            })
        donors[d][1] -= amount
        receivers[r][1] -= amount
        if donors[d][1] <= 1e-12:
            d += 1
        if receivers[r][1] <= 1e-12:
            r += 1
    return ledger


def rotation_intensity(shifts: pd.DataFrame) -> pd.Series:
    """Sum of absolute share shifts per date: how much money is moving.

    Zero means no sector gained or lost share. Larger values mean more
    money is changing sectors on that date. It is a regime input, not a
    ranking.
    """
    return shifts.abs().sum(axis=1)
