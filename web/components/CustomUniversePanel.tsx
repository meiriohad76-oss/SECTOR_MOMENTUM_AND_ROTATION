// web/components/CustomUniversePanel.tsx
"use client";
import { useState } from "react";
import { stateColor, stateShortLabel } from "../lib/state-colors";

type UniverseRow = {
  ticker: string;
  custom_rank: number | null;
  state: string | null;
  asset_class: string | null;
  s_score: number | null;
  f_score: number | null;
  mom_12_1: number | null;
  cmf21: number | null;
  missing: boolean;
  missing_reason: string | null;
};

type UniverseResult = {
  rows: UniverseRow[];
  available_count: number;
  missing_count: number;
  class_counts: Record<string, number>;
  state_counts: Record<string, number>;
  action_tickers: { exit: string[]; warning: string[]; bullish: string[] };
};

function fmtScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return (v >= 0 ? "+" : "") + v.toFixed(2);
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%";
}

export default function CustomUniversePanel() {
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [result, setResult]     = useState<UniverseResult | null>(null);
  const [error, setError]       = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const tickers = input
      .split(/[\s,;]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);
    if (tickers.length === 0) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const res = await fetch("/api/v1/universe/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tickers }),
      });
      if (!res.ok) {
        setError(`Server error: HTTP ${res.status}`);
        return;
      }
      const data = (await res.json()) as UniverseResult;
      setResult(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <details className="custom-universe-panel">
      <summary className="cup-summary">Custom Universe Analyzer</summary>

      <form className="cup-form" onSubmit={handleSubmit}>
        <label className="cup-label" htmlFor="cup-input">
          Paste tickers (comma, space, or newline separated):
        </label>
        <textarea
          id="cup-input"
          className="cup-textarea"
          rows={3}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="XLK, XLE, NVDA, AAPL..."
          disabled={loading}
        />
        <button className="cup-submit" type="submit" disabled={loading || !input.trim()}>
          {loading ? "Analyzing…" : "Analyze"}
        </button>
      </form>

      {error && <p className="cup-error">{error}</p>}

      {result && (
        <div className="cup-results">
          <div className="cup-summary-row">
            <span>{result.available_count} matched</span>
            {result.missing_count > 0 && (
              <span className="cup-missing-badge">{result.missing_count} not found</span>
            )}
          </div>

          {result.action_tickers.bullish.length > 0 && (
            <div className="cup-bucket cup-bucket-bullish">
              <span className="cup-bucket-label">BULLISH</span>{" "}
              {result.action_tickers.bullish.join(", ")}
            </div>
          )}
          {result.action_tickers.warning.length > 0 && (
            <div className="cup-bucket cup-bucket-warning">
              <span className="cup-bucket-label">WARN</span>{" "}
              {result.action_tickers.warning.join(", ")}
            </div>
          )}
          {result.action_tickers.exit.length > 0 && (
            <div className="cup-bucket cup-bucket-exit">
              <span className="cup-bucket-label">EXIT</span>{" "}
              {result.action_tickers.exit.join(", ")}
            </div>
          )}

          <div className="cup-table-scroll">
            <table className="cup-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Ticker</th>
                  <th>State</th>
                  <th>Class</th>
                  <th>S</th>
                  <th>F</th>
                  <th>MOM</th>
                  <th>CMF</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={row.ticker} className={row.missing ? "cup-row-missing" : ""}>
                    <td>{row.custom_rank ?? "—"}</td>
                    <td className="cup-ticker">{row.ticker}</td>
                    <td>
                      {row.state ? (
                        <span
                          className="state-pill mono"
                          style={{
                            background: stateColor(row.state),
                            color: "#fff",
                            padding: "1px 6px",
                            borderRadius: "8px",
                            fontSize: "0.67rem",
                            fontWeight: 600,
                          }}
                        >
                          {stateShortLabel(row.state)}
                        </span>
                      ) : (
                        <span className="cup-not-found">not found</span>
                      )}
                    </td>
                    <td>{row.asset_class ?? "—"}</td>
                    <td className={row.s_score !== null ? (row.s_score >= 0 ? "cup-pos" : "cup-neg") : ""}>
                      {fmtScore(row.s_score)}
                    </td>
                    <td className={row.f_score !== null ? (row.f_score >= 0 ? "cup-pos" : "cup-neg") : ""}>
                      {fmtScore(row.f_score)}
                    </td>
                    <td>{fmtPct(row.mom_12_1)}</td>
                    <td>{fmtScore(row.cmf21)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </details>
  );
}
