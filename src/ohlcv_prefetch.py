"""Best-effort background OHLCV cache warming."""
from __future__ import annotations

from collections.abc import Callable, Iterable
import concurrent.futures
from dataclasses import dataclass
import threading
import time
from typing import Any

from .data import OhlcvFetchResult, fetch_ohlcv_result, _select_ohlcv_provider
from .ohlcv_store import ohlcv_cache_enabled


PREFETCH_MIN_INTERVAL_SECONDS = 900


@dataclass(frozen=True)
class OhlcvPrefetchSummary:
    provider: str
    fetched_count: int
    fresh_cache_hit_count: int
    stale_cache_hit_count: int
    missing_count: int
    warning_count: int
    error_type: str | None = None


_LOCK = threading.Lock()
_INFLIGHT: dict[tuple[tuple[str, ...], str, str, str], concurrent.futures.Future] = {}
_LAST_SUBMITTED_AT: dict[tuple[tuple[str, ...], str, str, str], float] = {}


def warm_ohlcv_cache(
    tickers: Iterable[str],
    *,
    period: str = "3y",
    interval: str = "1d",
    provider: str | None = None,
    fetcher: Callable[..., OhlcvFetchResult] = fetch_ohlcv_result,
) -> OhlcvPrefetchSummary:
    """Warm the persistent OHLCV cache and return metadata only."""
    try:
        result = fetcher(
            list(dict.fromkeys(tickers)),
            period=period,
            interval=interval,
            provider=provider,
            use_cache=True,
        )
    except Exception as exc:
        return OhlcvPrefetchSummary(
            provider=str(provider or "unknown"),
            fetched_count=0,
            fresh_cache_hit_count=0,
            stale_cache_hit_count=0,
            missing_count=0,
            warning_count=0,
            error_type=type(exc).__name__,
        )
    return OhlcvPrefetchSummary(
        provider=str(result.provider or _safe_provider_name(provider)),
        fetched_count=len(result.fetched),
        fresh_cache_hit_count=len(result.fresh_cache_hits),
        stale_cache_hit_count=len(result.stale_cache_hits),
        missing_count=len(result.missing),
        warning_count=len(result.warnings),
    )


def submit_ohlcv_prefetch(
    tickers: Iterable[str],
    *,
    period: str = "3y",
    interval: str = "1d",
    provider: str | None = None,
    now: float | None = None,
    min_interval_seconds: int = PREFETCH_MIN_INTERVAL_SECONDS,
    fetcher: Callable[..., OhlcvFetchResult] = fetch_ohlcv_result,
) -> concurrent.futures.Future | None:
    """Submit a deduped daemon-thread cache warmup, if persistent cache is enabled."""
    if not ohlcv_cache_enabled():
        return None
    key = _prefetch_key(tickers, period=period, interval=interval, provider=provider)
    current_time = time.monotonic() if now is None else now
    with _LOCK:
        existing = _INFLIGHT.get(key)
        if existing is not None and not existing.done():
            return existing
        last_submitted_at = _LAST_SUBMITTED_AT.get(key)
        if existing is not None and last_submitted_at is not None:
            if current_time - last_submitted_at < min_interval_seconds:
                return existing
        future = _submit_future(
            warm_ohlcv_cache,
            list(key[0]),
            period=period,
            interval=interval,
            provider=provider,
            fetcher=fetcher,
        )
        _INFLIGHT[key] = future
        _LAST_SUBMITTED_AT[key] = current_time
        return future


def prefetch_status(future: concurrent.futures.Future | None) -> str:
    """Return a short operator-safe prefetch status string."""
    if future is None:
        return "disabled"
    if not future.done():
        return "running"
    try:
        summary = future.result()
    except Exception as exc:
        return f"failed: {type(exc).__name__}"
    if not isinstance(summary, OhlcvPrefetchSummary):
        return "ready"
    if summary.error_type:
        return f"failed: {summary.error_type}"
    cache_count = summary.fresh_cache_hit_count + summary.stale_cache_hit_count
    return (
        f"ready: {summary.provider} fetched={summary.fetched_count} "
        f"cache={cache_count} missing={summary.missing_count} warnings={summary.warning_count}"
    )


def reset_ohlcv_prefetch_state() -> None:
    """Clear module-level prefetch state for tests."""
    with _LOCK:
        _INFLIGHT.clear()
        _LAST_SUBMITTED_AT.clear()


def _submit_future(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> concurrent.futures.Future:
    future: concurrent.futures.Future = concurrent.futures.Future()

    def run() -> None:
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)

    thread = threading.Thread(target=run, name="ohlcv-prefetch", daemon=True)
    thread.start()
    return future


def _prefetch_key(
    tickers: Iterable[str],
    *,
    period: str,
    interval: str,
    provider: str | None,
) -> tuple[tuple[str, ...], str, str, str]:
    normalized_tickers = tuple(str(ticker).upper() for ticker in dict.fromkeys(tickers))
    return (
        normalized_tickers,
        str(period),
        str(interval),
        _safe_provider_name(provider),
    )


def _safe_provider_name(provider: str | None) -> str:
    if provider is None:
        try:
            return _select_ohlcv_provider(provider)
        except Exception:
            return "unknown"
    normalized = str(provider).strip().lower()
    if normalized in {"massive", "polygon"}:
        return "massive"
    if normalized == "yfinance":
        return "yfinance"
    return normalized or "unknown"
