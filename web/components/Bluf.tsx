// web/components/Bluf.tsx
import type { BlufPayload } from "../lib/api";

function pct(value: number | null | undefined): string {
  return value == null ? "n/a" : value.toFixed(2);
}

export default function Bluf({ bluf }: { bluf: BlufPayload }) {
  return (
    <section className="bluf" aria-label="Bottom line up front" style={{ padding: "16px 20px", borderBottom: "1px solid #e5e2dc" }}>
      <div className="mono" style={{ fontSize: 11, letterSpacing: "0.08em", opacity: 0.7 }}>
        BOTTOM LINE
        {bluf.degraded ? " · DEGRADED RUN" : ""}
        {bluf.flow_coverage != null ? ` · FLOW COVERAGE ${Math.round(bluf.flow_coverage * 100)}%` : ""}
      </div>

      <ul style={{ margin: "8px 0", paddingLeft: 18 }}>
        {bluf.conclusions.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>

      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
        <div>
          <strong className="mono">Recommended actions</strong>
          {bluf.actions.length > 0 ? (
            <ul style={{ paddingLeft: 18 }}>
              {bluf.actions.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          ) : (
            <p>No actions this run.</p>
          )}
        </div>

        <div>
          <strong className="mono">Top leading stocks</strong>
          {bluf.top_leading_stocks.length > 0 ? (
            <ol style={{ paddingLeft: 18 }}>
              {bluf.top_leading_stocks.map((item) => (
                <li key={item.ticker}>
                  {item.ticker} · {item.sector} · score {pct(item.s_score)}
                </li>
              ))}
            </ol>
          ) : (
            <p>None: no stock is eligible inside a leading sector.</p>
          )}
        </div>

        <div>
          <strong className="mono">Leading sectors</strong>
          {bluf.leading_sectors.length > 0 ? (
            <ul style={{ paddingLeft: 18 }}>
              {bluf.leading_sectors.map((item) => (
                <li key={item.ticker}>
                  {item.ticker} · score {pct(item.s_score)}
                </li>
              ))}
            </ul>
          ) : (
            <p>None this run.</p>
          )}
        </div>
      </div>

      {bluf.holdings.length > 0 ? (
        <div style={{ marginTop: 12 }}>
          <strong className="mono">My holdings</strong>
          <table style={{ width: "100%", fontSize: 13, marginTop: 4 }}>
            <thead>
              <tr><th align="left">Ticker</th><th align="left">Sector</th><th align="left">Sector leading</th><th align="left">State</th></tr>
            </thead>
            <tbody>
              {bluf.holdings.map((item) => (
                <tr key={item.ticker}>
                  <td>{item.ticker}</td>
                  <td>{item.sector ?? "unmapped"}{item.sector_note ? <span className="proxy-tag" title={item.sector_note}>proxy</span> : null}</td>
                  <td>{item.sector_leading == null ? "n/a" : item.sector_leading ? "yes" : "no"}</td>
                  <td>{item.scored ? item.state : "not scored"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {bluf.watchlist.length > 0 ? (
        <div style={{ marginTop: 12 }}>
          <strong className="mono">Watchlist</strong>
          <table style={{ width: "100%", fontSize: 13, marginTop: 4 }}>
            <thead>
              <tr><th align="left">Ticker</th><th align="left">Sector</th><th align="left">Sector leading</th><th align="left">State</th></tr>
            </thead>
            <tbody>
              {bluf.watchlist.map((item) => (
                <tr key={item.ticker}>
                  <td>{item.ticker}</td>
                  <td>{item.sector ?? "unmapped"}{item.sector_note ? <span className="proxy-tag" title={item.sector_note}>proxy</span> : null}</td>
                  <td>{item.sector_leading == null ? "n/a" : item.sector_leading ? "yes" : "no"}</td>
                  <td>{item.scored ? item.state : "not scored"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
