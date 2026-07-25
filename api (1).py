"""FinPulse - REST API (FastAPI)."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import database as db

app = FastAPI(
    title="FinPulse API",
    description="REST API for Indian stock market data",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.on_event("startup")
def startup():
    db.init_db()
    if not db.fetch_all_stocks():
        db.refresh_all()


@app.get("/")
def root():
    return {
        "name": "FinPulse API",
        "endpoints": ["/stocks", "/stocks/{ticker}", "/stocks/{ticker}/history",
                      "/market-summary", "/sectors", "/docs"],
    }


@app.get("/stocks")
def get_stocks(sector: str | None = None):
    """All tracked stocks with latest fundamentals."""
    data = db.fetch_all_stocks()
    if sector:
        data = [s for s in data if (s["sector"] or "").lower() == sector.lower()]
    return {"count": len(data), "data": data}


@app.get("/stocks/{ticker}")
def get_stock(ticker: str):
    """Single stock detail."""
    stock = db.fetch_stock(ticker.upper())
    if not stock:
        raise HTTPException(status_code=404, detail=f"{ticker} not tracked")
    return stock


@app.get("/stocks/{ticker}/history")
def get_history(ticker: str, limit: int = 250):
    """Historical OHLCV candles."""
    rows = db.fetch_history(ticker.upper(), limit)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No history for {ticker}")
    return {"ticker": ticker.upper(), "count": len(rows), "data": rows}


@app.get("/market-summary")
def get_summary():
    """Aggregate market stats, advancers/decliners, top movers."""
    return db.market_summary()


@app.get("/sectors")
def get_sectors():
    """Sector-wise aggregation."""
    out = {}
    for s in db.fetch_all_stocks():
        sec = s["sector"] or "Unknown"
        out.setdefault(sec, {"count": 0, "market_cap": 0, "avg_change": []})
        out[sec]["count"] += 1
        out[sec]["market_cap"] += s["market_cap"] or 0
        out[sec]["avg_change"].append(s["change_pct"] or 0)
    for sec in out:
        ch = out[sec].pop("avg_change")
        out[sec]["avg_change_pct"] = round(sum(ch) / len(ch), 2)
    return out


@app.post("/refresh")
def refresh():
    """Re-pull data from yfinance into the database."""
    return {"refreshed": db.refresh_all()}