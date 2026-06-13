# B-170 Retirement Readiness — All Gates Pass

**Date:** 2026-06-13  
**Branch:** backlog-stepwise-qa  
**Verified by:** `python scripts/check_b170_retirement_readiness.py`

## Gate Results

| Gate | Result | Detail |
|---|---|---|
| `feature_parity` | ✅ ok=true | next_status=200, row_count=83, selected_ticker=XLK present |
| `data_parity` | ✅ ok=true | health=ok, data_health=ok, provider_health=ok, snapshot=ok; XLK state=WARNING, quadrant=Weakening, S_score=1.27 |
| `visual_parity` | ✅ ok=true | All 9 screens pass across A/B/C profiles (no missing_text, all nonblank) |
| `operational_parity` | ✅ ok=true | api_health_ok=True, next_status=200, streamlit_status=200 |
| `rollback` | ✅ ok=true | streamlit_status=200 |

## Services at time of check (local dev)

- **FastAPI** — `uvicorn src.api_server:create_app --factory --host 127.0.0.1 --port 8000`
- **Next.js** — `npm run dev` on port 3000
- **Streamlit** — `python -m streamlit run app.py --server.port 8501 --server.headless true`

## QA Reports location

`docs/browser-qa/next-handoff/latest/` — three JSON reports + screenshots:
- `next_handoff_qa_report_a.json` (profile A, generated 2026-06-09)
- `next_handoff_qa_report_b.json` (profile B, generated 2026-06-10)
- `next_handoff_qa_report.json` (profile C, generated 2026-06-10)

## Similarity scores

| Screen | Profile | Similarity |
|---|---|---|
| overview | A | 0.87 |
| deepdive | A | 0.87 |
| rotation | A | 0.89 |
| overview | B | 0.84 |
| deepdive | B | 0.81 |
| rotation | B | 0.85 |
| overview | C | 0.82 |
| deepdive | C | 0.84 |
| rotation | C | 0.86 |

## Next steps for Pi production deployment

When Pi is reachable at `ahad@sector-pi.local`:

```bash
cd /home/ahad/SECTOR_MOMENTUM_AND_ROTATION
git pull origin backlog-stepwise-qa
.venv/bin/pip install -r requirements.txt
npm --prefix web ci
npm --prefix web run build

sudo cp systemd/sector-api.service /etc/systemd/system/
sudo cp systemd/sector-next.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sector-api sector-next

# Re-run QA against live Next.js on Pi (port 3000) then verify gates
python scripts/check_b170_retirement_readiness.py \
  --api-base-url http://127.0.0.1:8000 \
  --next-url http://127.0.0.1:3000/?presentation=c \
  --streamlit-url http://127.0.0.1:8501/?ticker=XLK
```

## Outstanding IOC items (lower priority, not blocking retirement)

- `ETF_PRIMARY_FLOW_STUB_MODE` still `True` — stub mode for ETF primary flow
- No file lock on `state.json` write path (race condition under concurrent refreshes)
- yfinance fallback not wired when Massive OHLCV fails
- `MANSFIELD_RS` raw value dominance in S-score calibration
