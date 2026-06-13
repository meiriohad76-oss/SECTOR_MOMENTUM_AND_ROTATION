"""Read-only portfolio analysis payloads for the B-170 API migration."""
from __future__ import annotations

import base64
from typing import Any, Mapping

import pandas as pd

from .api_dashboard_snapshot import build_latest_dashboard_snapshot_payload
from .portfolio import (
    HoldingInput,
    PortfolioInputResult,
    analyze_holdings,
    parse_holdings_csv,
    parse_holdings_excel,
    parse_single_ticker,
    normalize_ticker,
)


def build_portfolio_analysis_payload(
    request: Mapping[str, Any] | None,
    *,
    snapshot_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze user-supplied holdings against the latest persisted dashboard snapshot.

    This endpoint intentionally does not fetch market providers, recompute indicators,
    write saved portfolios, or mutate the state machine. It only maps supplied holdings
    onto already persisted snapshot rows.
    """

    body = dict(request or {})
    parsed = parse_portfolio_request(body)
    snapshot = dict(snapshot_payload or build_latest_dashboard_snapshot_payload())
    scored = _scored_frame_from_snapshot(snapshot)

    if parsed.errors:
        return _response(
            status="invalid",
            message="Portfolio input could not be parsed.",
            input_result=parsed,
            rows=[],
            state_exposure={},
            class_exposure={},
            action_tickers={"exit": [], "warning": [], "bullish": []},
        )

    if not parsed.holdings:
        return _response(
            status="invalid",
            message="No holdings were supplied.",
            input_result=parsed,
            rows=[],
            state_exposure={},
            class_exposure={},
            action_tickers={"exit": [], "warning": [], "bullish": []},
        )

    analysis = analyze_holdings(parsed.holdings, scored)
    return _response(
        status="ready",
        message="Portfolio analysis completed from the latest persisted dashboard snapshot.",
        input_result=parsed,
        rows=[_analysis_row_payload(row) for row in analysis.rows],
        state_exposure=analysis.state_exposure,
        class_exposure=analysis.class_exposure,
        action_tickers=analysis.action_tickers,
        missing_tickers=analysis.missing_tickers,
    )


def parse_portfolio_request(body: Mapping[str, Any]) -> PortfolioInputResult:
    """Parse the shared portfolio request shape without provider or state writes."""

    ticker = body.get("ticker")
    if isinstance(ticker, str) and ticker.strip():
        return parse_single_ticker(ticker)

    holdings = body.get("holdings")
    if isinstance(holdings, list):
        return PortfolioInputResult(holdings=_holdings_from_json(holdings), errors=[])

    csv_text = body.get("csv")
    if isinstance(csv_text, str):
        return parse_holdings_csv(csv_text)

    file_name = str(body.get("file_name") or "").strip().lower()
    encoded = body.get("content_base64")
    if isinstance(encoded, str) and encoded.strip():
        try:
            payload = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            return PortfolioInputResult([], [_error(f"file content is not valid base64: {exc}")])
        if file_name.endswith((".xlsx", ".xls")):
            return parse_holdings_excel(payload)
        return parse_holdings_csv(payload)

    return PortfolioInputResult([], [_error("ticker, holdings, csv, or content_base64 is required")])


def _parse_request(body: Mapping[str, Any]) -> PortfolioInputResult:
    return parse_portfolio_request(body)


def _holdings_from_json(rows: list[Any]) -> list[HoldingInput]:
    holdings: list[HoldingInput] = []
    for item in rows:
        if not isinstance(item, Mapping):
            continue
        ticker = normalize_ticker(item.get("ticker") or item.get("symbol"))
        if ticker is None:
            continue
        holdings.append(
            HoldingInput(
                ticker=ticker,
                shares=_optional_float(item.get("shares")),
                cost_basis=_optional_float(item.get("cost_basis")),
                market_value=_optional_float(item.get("market_value")),
                weight=_optional_float(item.get("weight")),
                sector=_optional_text(item.get("sector")),
                account=_optional_text(item.get("account")),
                notes=_optional_text(item.get("notes")),
            )
        )
    return holdings


def _scored_frame_from_snapshot(snapshot: Mapping[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in snapshot.get("rows", []) or []:
        if not isinstance(row, Mapping):
            continue
        payload = row.get("payload", {}) if isinstance(row.get("payload"), Mapping) else {}
        rows.append(
            {
                "ticker": str(row.get("ticker") or "").upper(),
                "state": row.get("state"),
                "class": row.get("asset_class"),
                "S_score": row.get("s_score"),
                "F_score": row.get("f_score"),
                "rank_in_class": payload.get("rank_in_class"),
                "selected": payload.get("selected"),
                "veto": payload.get("veto"),
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=["state", "class", "S_score", "F_score", "rank_in_class", "selected", "veto"],
            index=pd.Index([], name="ticker"),
        )
    frame = pd.DataFrame(rows).drop_duplicates(subset=["ticker"], keep="first")
    return frame.set_index("ticker")


def _response(
    *,
    status: str,
    message: str,
    input_result: PortfolioInputResult,
    rows: list[dict[str, Any]],
    state_exposure: dict[str, float],
    class_exposure: dict[str, float],
    action_tickers: dict[str, list[str]],
    missing_tickers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "api_version": "v1",
        "status": status,
        "message": message,
        "input": {
            "holding_count": len(input_result.holdings),
            "errors": [
                {"message": error.message, "row_number": error.row_number, "column": error.column}
                for error in input_result.errors
            ],
        },
        "summary": {
            "row_count": len(rows),
            "missing_tickers": missing_tickers or [],
            "state_exposure": state_exposure,
            "class_exposure": class_exposure,
            "action_tickers": action_tickers,
        },
        "rows": rows,
    }


def _analysis_row_payload(row: Any) -> dict[str, Any]:
    return {
        "ticker": row.ticker,
        "analysis_weight": row.analysis_weight,
        "input_weight": row.input_weight,
        "market_value": row.market_value,
        "state": row.state,
        "asset_class": row.asset_class,
        "s_score": row.s_score,
        "f_score": row.f_score,
        "rank_in_class": row.rank_in_class,
        "selected": row.selected,
        "veto": row.veto,
        "missing": row.missing,
        "missing_reason": row.missing_reason,
    }


def _error(message: str):
    from .portfolio import PortfolioInputError

    return PortfolioInputError(message)


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
