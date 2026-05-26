"""Read-only methodology snapshots for user-supplied tickers.

These helpers score tickers that are not part of the fixed dashboard universe.
They deliberately avoid ``apply_state_machine()`` so ad hoc analysis never
writes transition state or changes the production scored universe.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import pandas as pd

from .flow import compute_flow_signals, flow_composite_z
from .indicators import compute_all_indicators
from .portfolio import normalize_ticker
from .scoring import compute_composite, decide_state


AD_HOC_CLASS = "Ad Hoc Stock"


@dataclass(frozen=True)
class AdHocTickerScoreResult:
    scored: pd.DataFrame
    missing_tickers: list[str]
    warnings: list[str]
    peer_count: int = 0


def score_ad_hoc_tickers(
    tickers: Iterable[str],
    ohlcv: Mapping[str, pd.DataFrame],
    phase: str,
    *,
    bench_ticker: str = "SPY",
    bil_ticker: str = "BIL",
) -> AdHocTickerScoreResult:
    requested = _normalize_requested_tickers(tickers)
    if not requested:
        return AdHocTickerScoreResult(pd.DataFrame(), [], [])

    bench_df = _lookup_ohlcv(ohlcv, bench_ticker)
    bil_df = _lookup_ohlcv(ohlcv, bil_ticker)
    warnings: list[str] = []
    if bench_df is None or bil_df is None:
        missing_benchmarks = [
            ticker for ticker, frame in ((bench_ticker, bench_df), (bil_ticker, bil_df)) if frame is None
        ]
        warnings.append("Missing benchmark OHLCV for ad hoc analysis: " + ", ".join(missing_benchmarks))
        return AdHocTickerScoreResult(pd.DataFrame(), requested, warnings)

    scoring_ohlcv = {
        bench_ticker: bench_df,
        bil_ticker: bil_df,
    }
    missing_tickers: list[str] = []
    for ticker in requested:
        frame = _lookup_ohlcv(ohlcv, ticker)
        if frame is None or frame.empty:
            missing_tickers.append(ticker)
            warnings.append(f"Missing OHLCV for ad hoc ticker: {ticker}")
            continue
        scoring_ohlcv[ticker] = frame

    available_tickers = [ticker for ticker in requested if ticker not in missing_tickers]
    if not available_tickers:
        return AdHocTickerScoreResult(pd.DataFrame(), missing_tickers, warnings)

    peer_tickers = _peer_context_tickers(ohlcv, available_tickers, bench_ticker, bil_ticker)
    for ticker in peer_tickers:
        if ticker in scoring_ohlcv:
            continue
        frame = _lookup_ohlcv(ohlcv, ticker)
        if frame is not None and not frame.empty:
            scoring_ohlcv[ticker] = frame

    try:
        indicators_df = compute_all_indicators(scoring_ohlcv, bench_ticker, bil_ticker, max_workers=1)
        flow_df = compute_flow_signals(scoring_ohlcv)
        flow_z = flow_composite_z(flow_df)
        class_overrides = {ticker: AD_HOC_CLASS for ticker in peer_tickers}
        scored = compute_composite(indicators_df, flow_df, flow_z, phase=phase, class_overrides=class_overrides)
    except ValueError as exc:
        warnings.append(f"Could not score ad hoc tickers: {exc}")
        return AdHocTickerScoreResult(pd.DataFrame(), requested, warnings)

    scored = scored.reindex([ticker for ticker in available_tickers if ticker in scored.index]).copy()
    if scored.empty:
        missing = list(dict.fromkeys(missing_tickers + available_tickers))
        for ticker in available_tickers:
            warnings.append(f"Insufficient indicator history for ad hoc ticker: {ticker}")
        return AdHocTickerScoreResult(pd.DataFrame(), missing, warnings)

    scored["top_n_target"] = 0
    scored["selected"] = pd.Series([False] * len(scored), index=scored.index, dtype=object)
    scored["state"] = [decide_state(row) for _, row in scored.iterrows()]
    scored["analysis_scope"] = "ad_hoc_peer_relative"
    scored["ad_hoc"] = True
    missing_after_scoring = [ticker for ticker in available_tickers if ticker not in scored.index]
    for ticker in missing_after_scoring:
        warnings.append(f"Insufficient indicator history for ad hoc ticker: {ticker}")

    return AdHocTickerScoreResult(
        scored=scored,
        missing_tickers=list(dict.fromkeys(missing_tickers + missing_after_scoring)),
        warnings=warnings,
        peer_count=len(peer_tickers),
    )


def _normalize_requested_tickers(tickers: Iterable[str]) -> list[str]:
    out: list[str] = []
    for ticker in tickers:
        normalized = normalize_ticker(ticker)
        if normalized is not None and normalized not in out:
            out.append(normalized)
    return out


def _lookup_ohlcv(ohlcv: Mapping[str, pd.DataFrame], ticker: str) -> pd.DataFrame | None:
    if ticker in ohlcv:
        return ohlcv[ticker]
    upper_lookup = {str(key).upper(): key for key in ohlcv}
    key = upper_lookup.get(str(ticker).upper())
    if key is None:
        return None
    return ohlcv[key]


def _peer_context_tickers(
    ohlcv: Mapping[str, pd.DataFrame],
    requested: Iterable[str],
    bench_ticker: str,
    bil_ticker: str,
) -> list[str]:
    blocked = {str(bench_ticker).upper(), str(bil_ticker).upper()}
    out: list[str] = []
    for ticker in list(requested) + [str(key) for key in ohlcv]:
        normalized = normalize_ticker(ticker)
        if normalized is None or normalized in blocked or normalized in out:
            continue
        out.append(normalized)
    return out
