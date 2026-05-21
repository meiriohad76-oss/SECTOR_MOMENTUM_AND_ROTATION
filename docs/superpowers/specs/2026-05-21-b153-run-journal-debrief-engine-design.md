# B-153 Run Journal And Debrief Engine Design

## Goal

Persist every methodology run and its decisions so a later debrief engine can measure which recommendations worked, which failed, and which thresholds deserve review.

## Scope

B-153 is split into small slices:

1. B-153.1 creates an append-only local run journal with pure Python helpers and deterministic tests.
2. B-153.2 wires the Streamlit scoring path to save one run snapshot after scoring and state-machine decisions.
3. B-153.3 adds a debrief engine that joins saved decisions to forward returns at 1w, 4w, 13w, and 26w.
4. B-153.4 surfaces debrief summaries in the dashboard and leaves richer exported reports as future polish.

## Architecture

Use a local SQLite database at `data/run_journal/runs.sqlite`. The database is gitignored and owned by the deployed machine, similar to `state.json`. The first slice keeps all code in `src/run_journal.py` and avoids Streamlit, network calls, provider fetches, and app imports. The second slice adds pure conversion helpers plus a small Streamlit call after BLUF/state-machine scoring so dashboard runs are journaled without changing scoring behavior. The third slice adds a pure debrief engine in `src/run_debrief.py` that accepts already-loaded OHLCV and computes forward outcomes without fetching data or importing Streamlit. The fourth slice adds a dashboard Debrief lab that reads the local journal and already-loaded OHLCV to show hit-rate summaries and threshold-review candidates.

The journal stores:

- run metadata: run id, timestamp, git SHA, app version, provider, universe count, and metadata JSON
- scored snapshots: ticker, class, state, score columns, pillar score JSON, and a payload JSON escape hatch
- decisions/recommendations: decision type, ticker, action, rationale, and payload JSON

The debrief engine will later read the journal, fetch or reuse historical prices, and compute hit rate, forward returns, drawdown avoidance, pillar attribution, and threshold-review candidates.

## Safety

The journal is append-only by `run_id`; duplicate run ids are rejected. It never stores API keys. It should not delete `state.json`, mutate the state machine, or block dashboard rendering if the database write fails in a later Streamlit-wiring slice.

## Acceptance Criteria

- The default database path is under `data/run_journal/` and is ignored by git.
- Pure tests can create a temporary journal, append a run with scored rows and decisions, and read it back.
- Duplicate run ids fail instead of silently overwriting historical evidence.
- No Streamlit import is required to use the journal helpers.
- Scored dashboard frames can be converted into journal snapshot rows without losing pillar/payload evidence.
- BLUF action groups expand into per-ticker decision rows with action, rationale, label, ETA, and state.
- Streamlit records the scored snapshot and BLUF decisions after scoring, and journal write failures are captured without blocking the dashboard render.
- Debrief calculations join journal decisions to scored snapshots and compute 1w, 4w, 13w, and 26w forward outcomes from supplied OHLCV.
- Missing ticker, missing price, no baseline, and insufficient future data produce unavailable outcomes instead of crashing.
- Debrief summaries can report hit rate and average forward return by action and horizon, with failed recommendations exposed as threshold-review candidates.
- The dashboard surfaces debrief summaries without fetching new market data or blocking render when the local journal is empty or unavailable.
