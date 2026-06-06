"""Persistent local OHLCV cache backed by DuckDB."""
from __future__ import annotations

from datetime import date, timedelta
import os
from pathlib import Path
from typing import Iterable

import pandas as pd

try:
    import duckdb
except ImportError:  # pragma: no cover - dependency should be installed from requirements.
    duckdb = None


OHLCV_COLUMNS = ["open", "high", "low", "close", "volume", "adj_close"]
DEFAULT_CACHE_PATH = Path(__file__).resolve().parent.parent / "data_cache" / "ohlcv.duckdb"
FRESHNESS_TOLERANCE_DAYS = 5
COVERAGE_TOLERANCE_DAYS = 10
MIN_PERIOD_COVERAGE_RATIO = 0.75


def ohlcv_cache_enabled() -> bool:
    configured = os.environ.get("OHLCV_CACHE_ENABLED", "true").strip().lower()
    return configured not in {"0", "false", "no", "off"}


def ohlcv_cache_path(cache_path: str | Path | None = None) -> Path:
    configured = cache_path or os.environ.get("OHLCV_CACHE_PATH") or DEFAULT_CACHE_PATH
    return Path(configured)


def _period_start(period: str, today: date | None = None) -> pd.Timestamp:
    end = today or date.today()
    text = str(period).strip().lower()
    try:
        if text.endswith("mo"):
            return pd.Timestamp(end - timedelta(days=int(text[:-2]) * 31))
        if text.endswith("y"):
            years = int(text[:-1])
            return pd.Timestamp(end - timedelta(days=years * 365 + years // 4))
        if text.endswith("d"):
            return pd.Timestamp(end - timedelta(days=int(text[:-1])))
    except ValueError:
        pass
    return pd.Timestamp("2003-01-01")


def _connect(cache_path: str | Path | None = None):
    if duckdb is None:
        return None
    path = ohlcv_cache_path(cache_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        return duckdb.connect(str(path))
    except Exception:
        return None


def _ensure_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ohlcv (
            ticker VARCHAR NOT NULL,
            interval VARCHAR NOT NULL,
            date TIMESTAMP NOT NULL,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume DOUBLE,
            adj_close DOUBLE,
            provider VARCHAR,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ticker, interval, date)
        )
        """
    )


def _normalize_index(index) -> pd.DatetimeIndex:
    normalized = pd.DatetimeIndex(pd.to_datetime(index))
    if normalized.tz is not None:
        normalized = normalized.tz_convert(None)
    return normalized.normalize()


def _normalized_frame(ticker: str, frame: pd.DataFrame, provider: str, interval: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    values = frame.copy()
    values.index = _normalize_index(values.index)
    if "adj_close" not in values.columns and "close" in values.columns:
        values["adj_close"] = values["close"]
    for column in OHLCV_COLUMNS:
        if column not in values.columns:
            values[column] = pd.NA
    values = values[OHLCV_COLUMNS].apply(pd.to_numeric, errors="coerce")
    values = values.dropna(subset=["close"])
    if values.empty:
        return pd.DataFrame()
    values = values.reset_index(names="date")
    values.insert(0, "interval", interval)
    values.insert(0, "ticker", str(ticker))
    values["provider"] = provider
    values["updated_at"] = pd.Timestamp.now(tz="UTC").tz_convert(None)
    return values[
        [
            "ticker",
            "interval",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "adj_close",
            "provider",
            "updated_at",
        ]
    ]


def write_cached_ohlcv(
    frames: dict[str, pd.DataFrame],
    cache_path: str | Path | None = None,
    provider: str = "",
    interval: str = "1d",
) -> None:
    if duckdb is None or not frames:
        return
    conn = _connect(cache_path)
    if conn is None:
        return
    try:
        try:
            _ensure_schema(conn)
        except Exception:
            return
        for ticker, frame in frames.items():
            try:
                incoming = _normalized_frame(str(ticker), frame, provider, interval)
                if incoming.empty:
                    continue
                start = incoming["date"].min()
                end = incoming["date"].max()
                conn.execute(
                    "DELETE FROM ohlcv WHERE ticker = ? AND interval = ? AND date BETWEEN ? AND ?",
                    [str(ticker), interval, start, end],
                )
                conn.register("incoming_ohlcv", incoming)
                try:
                    conn.execute("INSERT INTO ohlcv SELECT * FROM incoming_ohlcv")
                finally:
                    conn.unregister("incoming_ohlcv")
            except Exception:
                continue
    finally:
        conn.close()


def _frame_is_usable(
    frame: pd.DataFrame,
    start: pd.Timestamp,
    today: date,
    stale_after_days: int,
    allow_stale: bool = False,
) -> bool:
    requested = frame.loc[frame.index >= start]
    if len(requested) <= 30:
        return False
    if frame.index.min() > start + pd.Timedelta(days=COVERAGE_TOLERANCE_DAYS):
        return False
    fresh_after = pd.Timestamp(today - timedelta(days=stale_after_days))
    if not allow_stale and requested.index.max() < fresh_after:
        return False
    expected = pd.bdate_range(start=start.normalize(), end=pd.Timestamp(today).normalize())
    if len(expected) == 0:
        return True
    covered_dates = requested.index.normalize().unique().intersection(expected)
    return len(covered_dates) / len(expected) >= MIN_PERIOD_COVERAGE_RATIO


def read_cached_ohlcv(
    tickers: Iterable[str],
    period: str = "3y",
    interval: str = "1d",
    cache_path: str | Path | None = None,
    today: date | None = None,
    stale_after_days: int = FRESHNESS_TOLERANCE_DAYS,
    allow_stale: bool = False,
) -> dict[str, pd.DataFrame]:
    path = ohlcv_cache_path(cache_path)
    if duckdb is None or not path.exists():
        return {}
    as_of = today or date.today()
    start = _period_start(period, as_of)
    out: dict[str, pd.DataFrame] = {}
    conn = _connect(path)
    if conn is None:
        return out
    try:
        try:
            _ensure_schema(conn)
        except Exception:
            return out
        for ticker in list(dict.fromkeys(tickers)):
            try:
                frame = conn.execute(
                    """
                    SELECT date, open, high, low, close, volume, adj_close
                    FROM ohlcv
                    WHERE ticker = ? AND interval = ? AND date >= ?
                    ORDER BY date
                    """,
                    [str(ticker), interval, start - pd.Timedelta(days=COVERAGE_TOLERANCE_DAYS)],
                ).fetchdf()
            except Exception:
                continue
            if frame.empty:
                continue
            try:
                frame["date"] = _normalize_index(frame["date"])
                frame = frame.set_index("date").sort_index()
                frame.index.name = None
                frame = frame[OHLCV_COLUMNS].apply(pd.to_numeric, errors="coerce")
                if not _frame_is_usable(frame, start, as_of, stale_after_days, allow_stale=allow_stale):
                    continue
                out[str(ticker)] = frame.loc[frame.index >= start, OHLCV_COLUMNS].copy()
            except Exception:
                continue
    finally:
        conn.close()
    return out


def read_cached_ohlcv_metadata(
    tickers: Iterable[str],
    period: str = "3y",
    interval: str = "1d",
    cache_path: str | Path | None = None,
    today: date | None = None,
    stale_after_days: int = FRESHNESS_TOLERANCE_DAYS,
    allow_stale: bool = False,
) -> dict[str, dict[str, object]]:
    """Read usable cached OHLCV with cache provenance for operator health UI."""
    path = ohlcv_cache_path(cache_path)
    if duckdb is None or not path.exists():
        return {}
    as_of = today or date.today()
    start = _period_start(period, as_of)
    out: dict[str, dict[str, object]] = {}
    conn = _connect(path)
    if conn is None:
        return out
    try:
        try:
            _ensure_schema(conn)
        except Exception:
            return out
        for ticker in list(dict.fromkeys(tickers)):
            try:
                frame = conn.execute(
                    """
                    SELECT date, open, high, low, close, volume, adj_close, provider, updated_at
                    FROM ohlcv
                    WHERE ticker = ? AND interval = ? AND date >= ?
                    ORDER BY date
                    """,
                    [str(ticker), interval, start - pd.Timedelta(days=COVERAGE_TOLERANCE_DAYS)],
                ).fetchdf()
            except Exception:
                continue
            if frame.empty:
                continue
            try:
                frame["date"] = _normalize_index(frame["date"])
                updated_at = pd.to_datetime(frame.get("updated_at"), errors="coerce").dropna()
                provider_values = frame.get("provider", pd.Series(dtype=object)).dropna().astype(str)
                provider = str(provider_values.iloc[-1]) if not provider_values.empty else "unknown"
                ohlcv_frame = frame.set_index("date").sort_index()
                ohlcv_frame.index.name = None
                ohlcv_frame = ohlcv_frame[OHLCV_COLUMNS].apply(pd.to_numeric, errors="coerce")
                if not _frame_is_usable(ohlcv_frame, start, as_of, stale_after_days, allow_stale=allow_stale):
                    continue
                out[str(ticker)] = {
                    "frame": ohlcv_frame.loc[ohlcv_frame.index >= start, OHLCV_COLUMNS].copy(),
                    "provider": provider,
                    "updated_at": (
                        pd.Timestamp(updated_at.max()).isoformat()
                        if not updated_at.empty
                        else ""
                    ),
                }
            except Exception:
                continue
    finally:
        conn.close()
    return out
