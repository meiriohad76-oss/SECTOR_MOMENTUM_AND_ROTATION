"""Forward test of the sector dollar-volume share shift.

For each Friday, rank the 11 US sector ETFs by their share shift, then check
whether high-shift sectors beat low-shift sectors over the next 4 weeks.
Reports the mean rank correlation (IC) and the top-vs-bottom spread, with
sample sizes. Descriptive over the full history; not a walk-forward test.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from src.data import fetch_ohlcv
from src.rotation_flow import dollar_volume_shares, dollar_volume_wide, share_shift
from src.universe import US_SECTORS

HORIZON_WEEKS = 4


def main() -> int:
    prices = fetch_ohlcv(US_SECTORS, period="3y", interval="1d", provider="yfinance")
    dv = dollar_volume_wide(prices, US_SECTORS)
    shifts = share_shift(dollar_volume_shares(dv)).dropna()
    closes = pd.DataFrame({t: prices[t]["close"] for t in dv.columns}).reindex(dv.index)

    fridays = shifts.index[shifts.index.dayofweek == 4]
    rows = []
    for day in fridays:
        loc = closes.index.get_loc(day)
        if loc + HORIZON_WEEKS * 5 >= len(closes):
            continue
        future = closes.iloc[loc + HORIZON_WEEKS * 5] / closes.loc[day] - 1
        excess = future - future.mean()
        s = shifts.loc[day]
        ok = s.notna() & excess.notna()
        if ok.sum() < 8:
            continue
        rows.append({
            "date": day,
            "ic": s[ok].rank().corr(excess[ok].rank()),
            "top": excess[s[ok].nlargest(3).index].mean(),
            "bottom": excess[s[ok].nsmallest(3).index].mean(),
        })

    out = pd.DataFrame(rows)
    spread = out["top"] - out["bottom"]
    summary = {
        "weeks": int(len(out)),
        "mean_ic": round(float(out["ic"].mean()), 4),
        "ic_hit_rate_positive": round(float((out["ic"] > 0).mean()), 3),
        "mean_top3_excess_4w": round(float(out["top"].mean()), 4),
        "mean_bottom3_excess_4w": round(float(out["bottom"].mean()), 4),
        "mean_spread_top_minus_bottom": round(float(spread.mean()), 4),
        "spread_hit_rate": round(float((spread > 0).mean()), 3),
        "spread_t_stat": round(float(spread.mean() / (spread.std(ddof=1) / np.sqrt(len(spread)))), 2),
        "first_week": str(out["date"].min().date()),
        "last_week": str(out["date"].max().date()),
    }
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
