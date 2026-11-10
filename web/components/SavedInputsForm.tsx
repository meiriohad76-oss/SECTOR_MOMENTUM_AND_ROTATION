// web/components/SavedInputsForm.tsx
"use client";
import { useState } from "react";
import { deleteSavedWatchlist, postDashboardApi, saveWatchlist } from "../lib/api";

type Notice = { tone: "good" | "bad"; text: string } | null;
type JobResult = { ok: boolean; error: string };

export default function SavedInputsForm() {
  const [wlName, setWlName] = useState("");
  const [wlTickers, setWlTickers] = useState("");
  const [pfName, setPfName] = useState("");
  const [pfCsv, setPfCsv] = useState("");
  const [delName, setDelName] = useState("");
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState(false);

  async function run(label: string, job: () => Promise<JobResult>, onDone: () => void) {
    setBusy(true);
    setNotice(null);
    const result = await job();
    setBusy(false);
    if (result.ok) {
      setNotice({ tone: "good", text: `${label} updated. Scores pick it up on the next refresh.` });
      onDone();
    } else {
      setNotice({ tone: "bad", text: result.error || `${label} failed.` });
    }
  }

  const saveWl = () =>
    run(
      "Watchlist",
      async () => {
        const r = await saveWatchlist(wlName.trim(), wlTickers);
        return { ok: r.ok && r.data?.status !== "error", error: r.error || r.data?.message || "" };
      },
      () => {
        setWlName("");
        setWlTickers("");
      }
    );

  const savePf = () =>
    run(
      "Portfolio",
      async () => {
        const r = await postDashboardApi<{ status?: string; message?: string }>("/api/v1/portfolios", {
          name: pfName.trim(),
          csv: pfCsv,
        });
        return { ok: r.ok && r.data?.status !== "error", error: r.error || r.data?.message || "" };
      },
      () => {
        setPfName("");
        setPfCsv("");
      }
    );

  const removeWl = () =>
    run(
      "Watchlist",
      async () => {
        const r = await deleteSavedWatchlist(delName.trim());
        return { ok: r.ok && r.data?.status === "ready", error: r.error || "No watchlist with that name." };
      },
      () => setDelName("")
    );

  return (
    <section className="screen-section" aria-label="Saved watchlists and portfolios">
      <div className="section-heading">
        <h2>Watchlists and portfolios</h2>
        <span>Saved to the dashboard store</span>
      </div>
      <div className="saved-inputs-form">
        <fieldset>
          <legend>Watchlist</legend>
          <label>
            Name
            <input value={wlName} onChange={(e) => setWlName(e.target.value)} placeholder="Watchlist 2026-11-10" />
          </label>
          <label>
            Tickers (comma, space or new line separated)
            <textarea value={wlTickers} onChange={(e) => setWlTickers(e.target.value)} placeholder="AAOI, CRDO, TSM" />
          </label>
          <button type="button" disabled={busy || !wlName.trim() || !wlTickers.trim()} onClick={saveWl}>
            Save watchlist
          </button>
        </fieldset>

        <fieldset>
          <legend>Portfolio (CSV with ticker and shares or weight columns)</legend>
          <label>
            Name
            <input value={pfName} onChange={(e) => setPfName(e.target.value)} placeholder="Portfolio 2026-11-10" />
          </label>
          <label>
            CSV
            <textarea value={pfCsv} onChange={(e) => setPfCsv(e.target.value)} placeholder="ticker,shares&#10;AAPL,10" />
          </label>
          <button type="button" disabled={busy || !pfName.trim() || !pfCsv.trim()} onClick={savePf}>
            Save portfolio
          </button>
        </fieldset>

        <fieldset>
          <legend>Remove a watchlist</legend>
          <label>
            Name
            <input value={delName} onChange={(e) => setDelName(e.target.value)} />
          </label>
          <button type="button" disabled={busy || !delName.trim()} onClick={removeWl}>
            Remove watchlist
          </button>
        </fieldset>

        {busy ? <p className="subtle">Saving…</p> : null}
        {notice ? <p className={notice.tone === "good" ? "notice-good" : "notice-bad"}>{notice.text}</p> : null}
      </div>
    </section>
  );
}
