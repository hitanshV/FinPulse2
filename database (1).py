"""FinPulse - Database layer (SQLite + yfinance data fetching)."""

import os
import sqlite3
from datetime import datetime

import yfinance as yf

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finpulse.db")

# 24 NSE-listed companies tracked by FinPulse
STOCKS = {
    "RELIANCE.NS":   ("Reliance Industries", "Energy"),
    "TCS.NS":        ("Tata Consultancy Services", "IT"),
    "HDFCBANK.NS":   ("HDFC Bank", "Banking"),
    "ICICIBANK.NS":  ("ICICI Bank", "Banking"),
    "INFY.NS":       ("Infosys", "IT"),
    "HINDUNILVR.NS": ("Hindustan Unilever", "FMCG"),
    "ITC.NS":        ("ITC Limited", "FMCG"),
    "SBIN.NS":       ("State Bank of India", "Banking"),
    "BHARTIARTL.NS": ("Bharti Airtel", "Telecom"),
    "BAJFINANCE.NS": ("Bajaj Finance", "NBFC"),
    "LT.NS":         ("Larsen & Toubro", "Infrastructure"),
    "KOTAKBANK.NS":  ("Kotak Mahindra Bank", "Banking"),
    "ASIANPAINT.NS": ("Asian Paints", "Consumer"),
    "MARUTI.NS":     ("Maruti Suzuki", "Auto"),
    "AXISBANK.NS":   ("Axis Bank", "Banking"),
    "SUNPHARMA.NS":  ("Sun Pharmaceutical", "Pharma"),
    "TITAN.NS":      ("Titan Company", "Consumer"),
    "WIPRO.NS":      ("Wipro", "IT"),
    "NESTLEIND.NS":  ("Nestle India", "FMCG"),
    "ULTRACEMCO.NS": ("UltraTech Cement", "Cement"),
    "TATAMOTORS.NS": ("Tata Motors", "Auto"),
    "POWERGRID.NS":  ("Power Grid Corp", "Power"),
    "JSWSTEEL.NS":   ("JSW Steel", "Metals"),
    "NTPC.NS":       ("NTPC Limited", "Power"),
}


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            ticker       TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            sector       TEXT,
            price        REAL,
            prev_close   REAL,
            change_pct   REAL,
            market_cap   REAL,
            pe_ratio     REAL,
            eps          REAL,
            book_value   REAL,
            dividend_yld REAL,
            week52_high  REAL,
            week52_low   REAL,
            volume       REAL,
            updated_at   TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            ticker TEXT NOT NULL,
            date   TEXT NOT NULL,
            open   REAL, high REAL, low REAL, close REAL, volume REAL,
            PRIMARY KEY (ticker, date)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker)")
    conn.commit()
    conn.close()


def _safe(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def refresh_stock(ticker, period="1y"):
    """Fetch fundamentals + history for one ticker and upsert into SQLite."""
    name, sector = STOCKS.get(ticker, (ticker, "Unknown"))
    t = yf.Ticker(ticker)

    try:
        info = t.info or {}
    except Exception:
        info = {}

    hist = t.history(period=period)
    if hist.empty:
        return False

    price = _safe(info.get("currentPrice")) or float(hist["Close"].iloc[-1])
    prev = _safe(info.get("previousClose")) or (
        float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
    )
    change_pct = ((price - prev) / prev * 100) if prev else 0.0

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO stocks (ticker, company_name, sector, price, prev_close, change_pct,
                            market_cap, pe_ratio, eps, book_value, dividend_yld,
                            week52_high, week52_low, volume, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(ticker) DO UPDATE SET
            price=excluded.price, prev_close=excluded.prev_close,
            change_pct=excluded.change_pct, market_cap=excluded.market_cap,
            pe_ratio=excluded.pe_ratio, eps=excluded.eps,
            book_value=excluded.book_value, dividend_yld=excluded.dividend_yld,
            week52_high=excluded.week52_high, week52_low=excluded.week52_low,
            volume=excluded.volume, updated_at=excluded.updated_at
    """, (
        ticker, name, sector, price, prev, round(change_pct, 2),
        _safe(info.get("marketCap")), _safe(info.get("trailingPE")),
        _safe(info.get("trailingEps")), _safe(info.get("bookValue")),
        _safe(info.get("dividendYield")), _safe(info.get("fiftyTwoWeekHigh")),
        _safe(info.get("fiftyTwoWeekLow")), _safe(info.get("volume")),
        datetime.now().isoformat(timespec="seconds"),
    ))

    rows = [
        (ticker, idx.strftime("%Y-%m-%d"), float(r["Open"]), float(r["High"]),
         float(r["Low"]), float(r["Close"]), float(r["Volume"]))
        for idx, r in hist.iterrows()
    ]
    cur.executemany(
        "INSERT OR REPLACE INTO prices (ticker,date,open,high,low,close,volume) "
        "VALUES (?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    conn.close()
    return True


def refresh_all(period="1y", progress_cb=None):
    """Refresh every tracked stock. Returns count of successes."""
    init_db()
    ok = 0
    total = len(STOCKS)
    for i, ticker in enumerate(STOCKS, start=1):
        try:
            if refresh_stock(ticker, period):
                ok += 1
        except Exception as e:
            print(f"[warn] {ticker}: {e}")
        if progress_cb:
            progress_cb(i / total, ticker)
    return ok


def fetch_all_stocks():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM stocks ORDER BY market_cap DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def fetch_stock(ticker):
    conn = get_conn()
    row = conn.execute("SELECT * FROM stocks WHERE ticker = ?", (ticker,)).fetchone()
    conn.close()
    return dict(row) if row else None


def fetch_history(ticker, limit=250):
    conn = get_conn()
    rows = conn.execute(
        "SELECT date, open, high, low, close, volume FROM prices "
        "WHERE ticker = ? ORDER BY date DESC LIMIT ?", (ticker, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def market_summary():
    stocks = fetch_all_stocks()
    if not stocks:
        return {"total_stocks": 0}
    pes = [s["pe_ratio"] for s in stocks if s["pe_ratio"]]
    gainers = sorted(stocks, key=lambda s: s["change_pct"] or 0, reverse=True)[:5]
    losers = sorted(stocks, key=lambda s: s["change_pct"] or 0)[:5]
    return {
        "total_stocks": len(stocks),
        "total_market_cap": sum(s["market_cap"] or 0 for s in stocks),
        "average_pe": round(sum(pes) / len(pes), 2) if pes else None,
        "advancing": sum(1 for s in stocks if (s["change_pct"] or 0) > 0),
        "declining": sum(1 for s in stocks if (s["change_pct"] or 0) < 0),
        "top_gainers": [{"ticker": s["ticker"], "change_pct": s["change_pct"]} for s in gainers],
        "top_losers": [{"ticker": s["ticker"], "change_pct": s["change_pct"]} for s in losers],
        "last_updated": max((s["updated_at"] or "") for s in stocks),
    }


if __name__ == "__main__":
    init_db()
    print(f"Refreshed {refresh_all()} / {len(STOCKS)} stocks into {DB_PATH}")