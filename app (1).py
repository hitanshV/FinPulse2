"""FinPulse - Streamlit dashboard."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import database as db

st.set_page_config(page_title="FinPulse", page_icon="📈", layout="wide")

db.init_db()


@st.cache_data(ttl=900)
def load_stocks():
    return pd.DataFrame(db.fetch_all_stocks())


@st.cache_data(ttl=900)
def load_history(ticker):
    return pd.DataFrame(db.fetch_history(ticker, 500))


# ---------- Sidebar ----------
st.sidebar.title("📈 FinPulse")
st.sidebar.caption("Indian Stock Market Monitor")

if st.sidebar.button("🔄 Refresh Market Data", use_container_width=True):
    bar = st.sidebar.progress(0.0, text="Fetching...")
    db.refresh_all(progress_cb=lambda p, t: bar.progress(p, text=f"Fetching {t}"))
    st.cache_data.clear()
    bar.empty()
    st.rerun()

stocks_df = load_stocks()

if stocks_df.empty:
    st.warning("Database is empty. Click **Refresh Market Data** in the sidebar to load stocks.")
    st.stop()

st.sidebar.caption(f"Last updated: {stocks_df['updated_at'].max()}")

# ---------- Header metrics ----------
summary = db.market_summary()
st.title("FinPulse — Market Dashboard")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Companies Tracked", summary["total_stocks"])
c2.metric("Total Market Cap", f"₹{summary['total_market_cap']/1e12:,.2f} Lakh Cr")
c3.metric("Average P/E", summary["average_pe"])
c4.metric("Advancing / Declining", f"{summary['advancing']} / {summary['declining']}")

tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 Overview", "📊 Price Charts", "⚖️ Compare", "🏭 Sectors"]
)

# ---------- Tab 1: Overview ----------
with tab1:
    st.subheader("All Tracked Companies")
    sectors = ["All"] + sorted(stocks_df["sector"].dropna().unique().tolist())
    pick = st.selectbox("Filter by sector", sectors)
    view = stocks_df if pick == "All" else stocks_df[stocks_df["sector"] == pick]

    table = view[["ticker", "company_name", "sector", "price", "change_pct",
                  "market_cap", "pe_ratio", "eps", "week52_high", "week52_low"]].copy()
    table["market_cap"] = (table["market_cap"] / 1e7).round(0)  # to ₹ Cr
    table.columns = ["Ticker", "Company", "Sector", "Price ₹", "Chg %",
                     "Mkt Cap (₹ Cr)", "P/E", "EPS ₹", "52W High", "52W Low"]

    st.dataframe(
        table.style.background_gradient(subset=["Chg %"], cmap="RdYlGn"),
        use_container_width=True, hide_index=True,
    )
    st.download_button("⬇️ Download CSV", table.to_csv(index=False),
                       "finpulse_stocks.csv", "text/csv")

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("**Top 5 Gainers**")
        st.dataframe(pd.DataFrame(summary["top_gainers"]), hide_index=True,
                     use_container_width=True)
    with g2:
        st.markdown("**Top 5 Losers**")
        st.dataframe(pd.DataFrame(summary["top_losers"]), hide_index=True,
                     use_container_width=True)

# ---------- Tab 2: Charts ----------
with tab2:
    left, right = st.columns([2, 1])
    ticker = left.selectbox("Select company", stocks_df["ticker"].tolist(),
                            format_func=lambda t: f"{t} — {db.STOCKS.get(t, (t,))[0]}")
    window = right.selectbox("Window", [30, 90, 180, 365, 500], index=2,
                             format_func=lambda d: f"Last {d} days")

    hist = load_history(ticker).tail(window)
    row = stocks_df[stocks_df["ticker"] == ticker].iloc[0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Price", f"₹{row['price']:,.2f}", f"{row['change_pct']}%")
    m2.metric("Market Cap", f"₹{(row['market_cap'] or 0)/1e7:,.0f} Cr")
    m3.metric("P/E Ratio", f"{row['pe_ratio']:.2f}" if row["pe_ratio"] else "—")
    m4.metric("EPS", f"₹{row['eps']:.2f}" if row["eps"] else "—")

    fig = go.Figure(go.Candlestick(
        x=hist["date"], open=hist["open"], high=hist["high"],
        low=hist["low"], close=hist["close"], name="OHLC"))
    hist["MA20"] = hist["close"].rolling(20).mean()
    hist["MA50"] = hist["close"].rolling(50).mean()
    fig.add_trace(go.Scatter(x=hist["date"], y=hist["MA20"], name="MA20"))
    fig.add_trace(go.Scatter(x=hist["date"], y=hist["MA50"], name="MA50"))
    fig.update_layout(height=520, xaxis_rangeslider_visible=False,
                      title=f"{ticker} — Candlestick with Moving Averages")
    st.plotly_chart(fig, use_container_width=True)

    vol = go.Figure(go.Bar(x=hist["date"], y=hist["volume"], name="Volume"))
    vol.update_layout(height=220, title="Traded Volume", margin=dict(t=40, b=20))
    st.plotly_chart(vol, use_container_width=True)

# ---------- Tab 3: Compare ----------
with tab3:
    picks = st.multiselect("Select 2–5 companies",
                           stocks_df["ticker"].tolist(),
                           default=stocks_df["ticker"].tolist()[:3])
    if len(picks) >= 2:
        norm = go.Figure()
        for t in picks:
            h = load_history(t).tail(250)
            if h.empty:
                continue
            base = h["close"].iloc[0]
            norm.add_trace(go.Scatter(x=h["date"], y=(h["close"] / base - 1) * 100, name=t))
        norm.update_layout(height=450, title="Normalised Return Comparison (%)",
                           yaxis_title="Return since start (%)")
        st.plotly_chart(norm, use_container_width=True)

        comp = stocks_df[stocks_df["ticker"].isin(picks)][
            ["ticker", "price", "pe_ratio", "eps", "market_cap", "book_value", "change_pct"]
        ].copy()
        comp["market_cap"] = (comp["market_cap"] / 1e7).round(0)
        comp.columns = ["Ticker", "Price ₹", "P/E", "EPS ₹", "Mkt Cap (₹ Cr)",
                        "Book Value", "Chg %"]
        st.dataframe(comp, use_container_width=True, hide_index=True)

        bar = go.Figure(go.Bar(x=comp["Ticker"], y=comp["P/E"], text=comp["P/E"].round(1)))
        bar.update_layout(title="P/E Ratio Comparison", height=350)
        st.plotly_chart(bar, use_container_width=True)
    else:
        st.info("Pick at least two companies to compare.")

# ---------- Tab 4: Sectors ----------
with tab4:
    agg = stocks_df.groupby("sector").agg(
        Companies=("ticker", "count"),
        Avg_PE=("pe_ratio", "mean"),
        Avg_Change=("change_pct", "mean"),
        Market_Cap=("market_cap", "sum"),
    ).reset_index()
    agg["Market_Cap"] = (agg["Market_Cap"] / 1e7).round(0)
    agg = agg.round(2)
    st.dataframe(agg, use_container_width=True, hide_index=True)

    pie = go.Figure(go.Pie(labels=agg["sector"], values=agg["Market_Cap"], hole=0.4))
    pie.update_layout(title="Market Cap Distribution by Sector", height=450)
    st.plotly_chart(pie, use_container_width=True)