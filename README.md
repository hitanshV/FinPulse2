# FinPulse — Stock Market Monitoring Platform

A full-stack dashboard that tracks **24 NSE-listed Indian companies**, stores their
market data in a database, exposes it via a REST API, and visualises it through an
interactive dashboard.

**Live Dashboard:** <paste your Streamlit link here>  
**Live API Docs:** <paste your Render link here>/docs

---

## Architecture

```
yFinance API
     |
     v
database.py  ->  SQLite (stocks + prices tables)
     |                    |
     v                    v
api.py (FastAPI)     app.py (Streamlit)
  REST endpoints        Dashboard UI
```

- `database.py` — data ingestion + SQLite schema + query helpers
- `api.py` — FastAPI REST layer
- `app.py` — Streamlit frontend

---

## Database Design

**`stocks`** — one row per company (latest snapshot)

| Column | Type | Description |
|---|---|---|
| ticker (PK) | TEXT | NSE symbol |
| company_name | TEXT | Company name |
| sector | TEXT | Sector classification |
| price, prev_close, change_pct | REAL | Latest pricing |
| market_cap, pe_ratio, eps, book_value | REAL | Fundamentals |
| week52_high, week52_low, volume | REAL | Trading stats |
| updated_at | TEXT | Last refresh timestamp |

**`prices`** — historical OHLCV, composite PK `(ticker, date)` so re-running the
fetcher upserts instead of duplicating. Indexed on `ticker` for fast lookups.

---

## REST API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/stocks` | All stocks (optional `?sector=IT`) |
| GET | `/stocks/{ticker}` | Single stock detail |
| GET | `/stocks/{ticker}/history` | Historical OHLCV |
| GET | `/market-summary` | Aggregates, advancers/decliners, top movers |
| GET | `/sectors` | Sector-wise aggregation |
| POST | `/refresh` | Re-pull data from yFinance |

Interactive Swagger docs available at `/docs`.

---

## Features

- 24 NSE companies tracked with live + 1 year of historical data
- Price, market cap, P/E, EPS, book value, 52-week range, volume
- Candlestick charts with MA20 / MA50 overlays
- Volume bar chart
- Normalised multi-stock return comparison
- Side-by-side fundamentals comparison + P/E bar chart
- Sector-wise aggregation with market cap pie chart
- Colour-graded gainers/losers table
- CSV export
- One-click data refresh from the UI

---

## Setup

```bash
git clone https://github.com/<your-username>/FinPulse.git
cd FinPulse
pip install -r requirements.txt

python database.py        # populate the database (run once)
streamlit run app.py      # dashboard  -> http://localhost:8501
uvicorn api:app --reload  # API        -> http://localhost:8000/docs
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Data source | yFinance |
| Backend API | FastAPI + Uvicorn |
| Database | SQLite |
| Frontend | Streamlit + Plotly |
| Deployment | Streamlit Cloud (UI), Render (API) |

---

## Challenges Faced

- **yFinance `.info` is slow and occasionally returns empty dicts** — added
  fallbacks that derive price/previous close from the history dataframe.
- **Duplicate rows on re-fetch** — solved with a composite primary key and
  `INSERT OR REPLACE`.
- **Slow reloads** — used Streamlit's `@st.cache_data` with a 15-minute TTL.
- **Ephemeral filesystem on free hosting** — the app auto-populates the DB on
  first startup if empty.

---

## Future Improvements

- Migrate SQLite → Supabase/Postgres for persistent hosted storage
- Scheduled auto-refresh (cron / GitHub Actions) instead of manual
- Portfolio watchlist with user authentication
- Technical indicators (RSI, MACD, Bollinger Bands)
- Telegram/email price alerts
- PDF report export

---

## Credits

Built for **SoFI AlgoLabs Assignment 1**. Data from Yahoo Finance via `yfinance`.
Libraries used: FastAPI, Streamlit, Plotly, pandas, yfinance.