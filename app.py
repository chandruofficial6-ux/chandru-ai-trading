import math
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Chandru AI Trading",
    page_icon="📈",
    layout="wide",
)

IST = timezone(timedelta(hours=5, minutes=30))

# =====================================================================
# Stocks list
# =====================================================================
stocks = {
    "NIFTY 50": "^NSEI",
    "BANK NIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFOSYS": "INFY.NS",
    "HDFC BANK": "HDFCBANK.NS",
    "SBI": "SBIN.NS",
    "ITC": "ITC.NS",
    "ICICI BANK": "ICICIBANK.NS",
    "WIPRO": "WIPRO.NS",
    "L&T": "LT.NS",
}
INDICES = ["NIFTY 50", "BANK NIFTY", "SENSEX"]

NIFTY50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BEL", "BHARTIARTL",
    "CIPLA", "COALINDIA", "DRREDDY", "EICHERMOT", "ETERNAL",
    "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HINDALCO",
    "HINDUNILVR", "ICICIBANK", "ITC", "INFY", "INDIGO",
    "JSWSTEEL", "JIOFIN", "KOTAKBANK", "LT", "M&M",
    "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID",
    "RELIANCE", "SBILIFE", "SHRIRAMFIN", "SBIN", "SUNPHARMA",
    "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM",
    "TITAN", "TRENT", "ULTRACEMCO", "WIPRO", "MAXHEALTH",
]

# =====================================================================
# Sidebar: page chuno + watchlist
# =====================================================================
st.sidebar.title("🚀 CHANDRU AI TRADING")
st.sidebar.caption("Smart Indian Market Analysis")

PAGES = [
    "🔴 Live Market",
    "📰 Taaza News",
    "📈 Stock Analysis",
    "🔍 Scanners & Alerts",
    "⚖️ Compare",
    "🧪 Backtest & Strategy Lab",
    "💼 Paper Portfolio",
    "🎯 Option Chain (Seekhne ke liye)",
]
page = st.sidebar.radio("Page chuno", PAGES)

with st.sidebar.expander("➕ Apne stocks (watchlist)"):
    default_w = st.query_params.get("w", "")
    extra = st.text_input(
        "NSE symbol, comma se",
        value=default_w,
        placeholder="ZOMATO, TATAMOTORS",
    )
if extra:
    st.query_params["w"] = extra
elif "w" in st.query_params:
    del st.query_params["w"]
for sym_in in extra.split(","):
    sym_in = sym_in.strip().upper()
    if sym_in and sym_in.replace("&", "").replace("-", "").isalnum():
        stocks[sym_in] = sym_in + ".NS"

st.sidebar.markdown("---")
st.sidebar.caption("Sirf seekhne ke liye. Isse real paise ka faisla mat lo.")


# =====================================================================
# Data helpers
# =====================================================================
@st.cache_data(ttl=300)
def load_data(symbol, period):
    df = yf.download(symbol, period=period, interval="1d",
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


@st.cache_data(ttl=60)
def load_intraday(symbol, period, interval):
    df = yf.download(symbol, period=period, interval=interval,
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    if df.empty:
        return df
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df.index = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
    return df


def rsi_series(c, n=14):
    dl = c.diff()
    g = dl.clip(lower=0).rolling(n).mean()
    ls = (-dl.clip(upper=0)).rolling(n).mean()
    return 100 - 100 / (1 + g / ls)


def add_indicators(df):
    df = df.copy()
    df["MA20"] = df["Close"].rolling(20).mean()
    df["MA50"] = df["Close"].rolling(50).mean()
    df["RSI"] = rsi_series(df["Close"])
    return df


def swing_levels(w, p, win=7):
    hi = w["High"]
    lo = w["Low"]
    sh = hi[hi == hi.rolling(win, center=True, min_periods=1).max()]
    sl = lo[lo == lo.rolling(win, center=True, min_periods=1).min()]
    below = sl[sl < p]
    above = sh[sh > p]
    sup = float(below.max()) if len(below) else float(lo.min())
    res_ = float(above.min()) if len(above) else float(hi.max())
    return sup, res_


# =====================================================================
# News helpers (Google News RSS, taaza khabrein)
# =====================================================================
@st.cache_data(ttl=300)
def fetch_news(query, limit=12):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode({
        "q": query + " when:3d",
        "hl": "en-IN",
        "gl": "IN",
        "ceid": "IN:en",
    })
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = r.read()
        root = ET.fromstring(data)
    except Exception:
        return []
    items = []
    for it in root.iter("item"):
        title = it.findtext("title") or ""
        link = it.findtext("link") or ""
        pub = it.findtext("pubDate")
        src_el = it.find("source")
        src = src_el.text if src_el is not None and src_el.text else ""
        try:
            dt = parsedate_to_datetime(pub).astimezone(IST)
        except Exception:
            dt = None
        items.append((dt, title, link, src))
    items.sort(key=lambda x: x[0] or datetime(2000, 1, 1, tzinfo=IST), reverse=True)
    return items[:limit]


def ago(dt):
    if dt is None:
        return ""
    mins = int((datetime.now(IST) - dt).total_seconds() // 60)
    if mins < 1:
        return "abhi"
    if mins < 60:
        return f"{mins} min pehle"
    if mins < 1440:
        return f"{mins // 60} ghante pehle"
    return f"{mins // 1440} din pehle"


def yahoo_news(symbol, limit=8):
    out = []
    try:
        for item in (yf.Ticker(symbol).news or [])[:limit]:
            content = item.get("content", item)
            title = content.get("title", "No title")
            link = content.get("link", "")
            canon = content.get("canonicalUrl")
            if isinstance(canon, dict):
                link = canon.get("url", link)
            out.append((None, title, link, "Yahoo Finance"))
    except Exception:
        pass
    return out


def show_news(query, symbol=None, limit=10):
    items = fetch_news(query, limit)
    if not items and symbol:
        items = yahoo_news(symbol, limit)
    if not items:
        st.write("Abhi koi news nahi mili. Thodi der baad refresh karo.")
        return
    for dt, title, link, src in items:
        meta = " · ".join(x for x in [src, ago(dt)] if x)
        if link:
            st.markdown(f"- [{title}]({link})  \n  <small>{meta}</small>",
                        unsafe_allow_html=True)
        else:
            st.markdown(f"- {title}  \n  <small>{meta}</small>",
                        unsafe_allow_html=True)


# =====================================================================
# PAGE 1: Live Market
# =====================================================================
def compute_live(d, span):
    """5-minute (ya chune hue) candles pe BUY/SELL signal, support, resistance."""
    d = d.copy()
    d["EMA9"] = d["Close"].ewm(span=9, adjust=False).mean()
    d["EMA21"] = d["Close"].ewm(span=21, adjust=False).mean()
    warm = pd.Series(range(len(d)), index=d.index) >= 21
    up = (d["EMA9"] > d["EMA21"]) & (d["EMA9"].shift() <= d["EMA21"].shift()) & warm
    dn = (d["EMA9"] < d["EMA21"]) & (d["EMA9"].shift() >= d["EMA21"].shift()) & warm

    last_day = d.index[-1].date()
    day_mask = pd.Series(d.index.date == last_day, index=d.index)
    today = d[day_mask]
    prev = d[~day_mask]
    view = today if span == "Aaj" else d

    ltp = float(today["Close"].iloc[-1])
    if len(prev):
        pdays = prev[prev.index.date == prev.index[-1].date()]
        prev_close = float(pdays["Close"].iloc[-1])
        prev_high = float(pdays["High"].max())
        prev_low = float(pdays["Low"].min())
    else:
        prev_close = float(today["Open"].iloc[0])
        prev_high = prev_low = None

    lows = [float(today["Low"].min())]
    highs = [float(today["High"].max())]
    if prev_low is not None:
        lows.append(prev_low)
        highs.append(prev_high)
    if len(today) >= 9:
        lo = today["Low"]
        hi = today["High"]
        lows += list(lo[lo == lo.rolling(9, center=True, min_periods=9).min()])
        highs += list(hi[hi == hi.rolling(9, center=True, min_periods=9).max()])
    below = [x for x in lows if x < ltp]
    above = [x for x in highs if x > ltp]
    sup = max(below) if below else float(today["Low"].min())
    res_ = min(above) if above else float(today["High"].max())

    up_v = up[view.index]
    dn_v = dn[view.index]
    events = []
    for t in view.index[up_v.values]:
        events.append((t, "🟢 BUY", float(view.loc[t, "Close"])))
    for t in view.index[dn_v.values]:
        events.append((t, "🔴 SELL", float(view.loc[t, "Close"])))
    events.sort(key=lambda x: x[0], reverse=True)

    return {
        "d": d, "view": view, "today": today, "ltp": ltp,
        "prev_close": prev_close, "sup": sup, "res": res_,
        "up_v": up_v, "dn_v": dn_v, "events": events,
        "buys": int(up_v.sum()), "sells": int(dn_v.sum()),
        "day_high": float(today["High"].max()),
        "day_low": float(today["Low"].min()),
    }


def live_panel(name, iv, span):
    sym = stocks[name]
    try:
        raw = load_intraday(sym, "5d", iv)
    except Exception:
        raw = None
    if raw is None or raw.empty or len(raw) < 10:
        st.warning("Intraday data nahi mila. Market band ho sakta hai, ya thodi der baad try karo.")
        return

    r = compute_live(raw, span)
    view = r["view"]
    ltp = r["ltp"]
    chg = ltp - r["prev_close"]

    now_txt = datetime.now(IST).strftime("%d %b %H:%M:%S")
    st.caption(f"Last candle: {raw.index[-1]:%d %b %H:%M} IST  |  Page update: {now_txt} IST")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(f"{name} (abhi)", f"{ltp:,.2f}", f"{chg:+.2f} ({chg / r['prev_close'] * 100:+.2f}%)")
    k2.metric("Aaj ka High / Low", f"{r['day_high']:,.0f} / {r['day_low']:,.0f}")
    k3.metric("🛡️ Support", f"{r['sup']:,.2f}", f"{(r['sup'] - ltp) / ltp * 100:+.2f}% door")
    k4.metric("🚧 Resistance", f"{r['res']:,.2f}", f"{(r['res'] - ltp) / ltp * 100:+.2f}% door")

    s1, s2, s3 = st.columns(3)
    s1.metric("🟢 BUY signal", r["buys"], help="EMA9 ne EMA21 ko neeche se upar kaata")
    s2.metric("🔴 SELL signal", r["sells"], help="EMA9 ne EMA21 ko upar se neeche kaata")
    last_row = view.iloc[-1]
    if last_row["EMA9"] > last_row["EMA21"]:
        s3.metric("Abhi ka trend", "🟢 Upar (BUY zone)")
    else:
        s3.metric("Abhi ka trend", "🔴 Neeche (SELL zone)")

    if r["events"]:
        t, sg, p = r["events"][0]
        st.info(f"Sabse naya signal: {sg} @ ₹{p:,.2f} ({t:%d %b %H:%M})")
    else:
        st.info("Abhi tak koi naya BUY/SELL signal nahi aaya.")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=view.index, open=view["Open"], high=view["High"],
        low=view["Low"], close=view["Close"], name="Price"))
    fig.add_trace(go.Scatter(x=view.index, y=view["EMA9"], name="EMA9",
                             line=dict(width=1.2, color="orange")))
    fig.add_trace(go.Scatter(x=view.index, y=view["EMA21"], name="EMA21",
                             line=dict(width=1.2, color="purple")))
    bx = view.index[r["up_v"].values]
    sx = view.index[r["dn_v"].values]
    if len(bx):
        fig.add_trace(go.Scatter(
            x=bx, y=view.loc[bx, "Low"] * 0.9995, mode="markers", name="BUY",
            marker=dict(symbol="triangle-up", size=14, color="green")))
    if len(sx):
        fig.add_trace(go.Scatter(
            x=sx, y=view.loc[sx, "High"] * 1.0005, mode="markers", name="SELL",
            marker=dict(symbol="triangle-down", size=14, color="red")))
    fig.add_hline(y=r["sup"], line_dash="dash", line_color="green",
                  annotation_text="Support")
    fig.add_hline(y=r["res"], line_dash="dash", line_color="red",
                  annotation_text="Resistance")
    fig.add_hline(y=r["prev_close"], line_dash="dot", line_color="gray",
                  annotation_text="Pichla close")
    fig.update_xaxes(rangebreaks=[
        dict(bounds=["sat", "mon"]),
        dict(bounds=[15.5, 9.25], pattern="hour"),
    ])
    fig.update_layout(height=620, xaxis_rangeslider_visible=False,
                      margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.caption("BUY = EMA9 upar cross hua, SELL = EMA9 neeche cross hua. "
               "Ye sirf ek simple rule hai, guarantee nahi.")

    with st.expander(f"📋 Signal list ({len(r['events'])})"):
        if r["events"]:
            ev = pd.DataFrame(
                [{"Time": f"{t:%d %b %H:%M}", "Signal": s, "Price": round(p, 2)}
                 for t, s, p in r["events"]])
            st.dataframe(ev, hide_index=True, use_container_width=True)
        else:
            st.write("Abhi koi signal nahi.")


def page_live():
    st.title("🔴 Live Market")

    cols = st.columns(3)
    for col, nm in zip(cols, INDICES):
        try:
            d = load_data(stocks[nm], "5d")
            p = float(d["Close"].iloc[-1])
            pv = float(d["Close"].iloc[-2])
            col.metric(nm, f"{p:,.2f}", f"{p - pv:+.2f} ({(p - pv) / pv * 100:+.2f}%)")
        except Exception:
            col.metric(nm, "NA")

    pick = st.radio("Market chuno", INDICES + ["Aur stock"], horizontal=True,
                    key="live_pick")
    if pick == "Aur stock":
        others = [n for n in stocks if n not in INDICES]
        lname = st.selectbox("Stock", others, key="live_stock")
    else:
        lname = pick

    c1, c2, c3 = st.columns(3)
    iv = c1.selectbox("Candle", ["1m", "5m", "15m"], index=1, key="live_iv")
    span = c2.selectbox("Data", ["Aaj", "Pichle 5 din"], key="live_span")
    auto = c3.checkbox("🔄 Auto-refresh (har 60 sec)", value=True, key="live_auto")

    panel = st.fragment(run_every=60 if auto else None)(live_panel)
    panel(lname, iv, span)

    st.markdown(f"### 📰 {lname}: taaza khabrein")
    show_news(f"{lname} market" if lname in INDICES else f"{lname} share NSE",
              symbol=stocks[lname], limit=6)


# =====================================================================
# PAGE 2: News
# =====================================================================
def page_news():
    st.title("📰 Taaza News (pichle 3 din)")
    if st.button("🔄 Refresh news"):
        fetch_news.clear()
    tabs = st.tabs(["🇮🇳 Poora Market", "NIFTY 50", "BANK NIFTY", "SENSEX", "Stock"])
    with tabs[0]:
        show_news("Indian stock market Sensex Nifty", limit=15)
    with tabs[1]:
        show_news("Nifty 50", symbol=stocks["NIFTY 50"], limit=12)
    with tabs[2]:
        show_news("Bank Nifty", symbol=stocks["BANK NIFTY"], limit=12)
    with tabs[3]:
        show_news("Sensex", symbol=stocks["SENSEX"], limit=12)
    with tabs[4]:
        others = [n for n in stocks if n not in INDICES]
        pick = st.selectbox("Stock chuno", others, key="news_stock")
        show_news(f"{pick} share NSE", symbol=stocks[pick], limit=12)


# =====================================================================
# PAGE 3: Stock Analysis
# =====================================================================
def page_stock():
    st.title("📈 Stock Analysis")
    c1, c2 = st.columns(2)
    name = c1.selectbox("Stock / Index", list(stocks.keys()), key="an_name")
    period = c2.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="an_period")
    symbol = stocks[name]

    df = load_data(symbol, period)
    if df.empty or len(df) < 3:
        st.error("Data nahi mila. Symbol check karo ya thodi der baad try karo.")
        return
    df = add_indicators(df)

    price = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2])
    change = price - prev
    m1, m2, m3 = st.columns(3)
    m1.metric(name, f"₹ {price:,.2f}", f"{change:+.2f} ({change / prev * 100:+.2f}%)")
    m2.metric("MA 20", f"{df['MA20'].iloc[-1]:,.2f}")
    m3.metric("MA 50", f"{df['MA50'].iloc[-1]:,.2f}")

    st.markdown("### 📊 Trading Signal")
    ma20 = df["MA20"].iloc[-1]
    ma50 = df["MA50"].iloc[-1]
    col1, col2, col3 = st.columns(3)
    if pd.isna(ma50):
        st.warning("MA50 ke liye kam data hai. Period bada karo (1y).")
    else:
        if price > ma20 > ma50:
            signal = "BUY"
            target, stop = price * 1.04, price * 0.98
            col1.success("🟢 BUY SIGNAL (Price > MA20 > MA50)")
        elif price < ma20 < ma50:
            signal = "SELL"
            target, stop = price * 0.96, price * 1.02
            col1.error("🔴 SELL SIGNAL (Price < MA20 < MA50)")
        else:
            signal = "WAIT"
            col1.info("🟡 WAIT: Trend clear nahi hai")
        if signal != "WAIT":
            col2.warning(f"🎯 TARGET: ₹ {target:,.2f}")
            col3.error(f"🛑 STOP LOSS: ₹ {stop:,.2f}")

    # BUY / SELL nishaan chart ke liye
    buy_state = (df["Close"] > df["MA20"]) & (df["MA20"] > df["MA50"])
    sell_state = (df["Close"] < df["MA20"]) & (df["MA20"] < df["MA50"])
    buy_pts = df[buy_state & ~buy_state.shift(fill_value=False)]
    sell_pts = df[sell_state & ~sell_state.shift(fill_value=False)]
    n1, n2 = st.columns(2)
    n1.metric("🟢 BUY signal (is period mein)", len(buy_pts))
    n2.metric("🔴 SELL signal (is period mein)", len(sell_pts))

    sup, res_ = swing_levels(df.tail(66), price)

    st.markdown("### 📈 Price Chart (BUY/SELL nishaan + Support/Resistance)")
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="Price"))
    fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA20"))
    fig.add_trace(go.Scatter(x=df.index, y=df["MA50"], name="MA50"))
    if len(buy_pts):
        fig.add_trace(go.Scatter(
            x=buy_pts.index, y=buy_pts["Low"] * 0.995, mode="markers", name="BUY",
            marker=dict(symbol="triangle-up", size=12, color="green")))
    if len(sell_pts):
        fig.add_trace(go.Scatter(
            x=sell_pts.index, y=sell_pts["High"] * 1.005, mode="markers", name="SELL",
            marker=dict(symbol="triangle-down", size=12, color="red")))
    fig.add_hline(y=sup, line_dash="dash", line_color="green", annotation_text="Support")
    fig.add_hline(y=res_, line_dash="dash", line_color="red", annotation_text="Resistance")
    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

    q1, q2 = st.columns(2)
    q1.metric("🛡️ Support (pichle 3 mahine)", f"₹ {sup:,.2f}", f"{(sup - price) / price * 100:+.1f}% door")
    q2.metric("🚧 Resistance (pichle 3 mahine)", f"₹ {res_:,.2f}", f"{(res_ - price) / price * 100:+.1f}% door")

    st.markdown("### 📉 RSI (14)")
    rsi = df["RSI"].iloc[-1]
    if rsi > 70:
        st.error(f"RSI {rsi:.1f}: Overbought, girne ka chance")
    elif rsi < 30:
        st.success(f"RSI {rsi:.1f}: Oversold, bounce ka chance")
    else:
        st.info(f"RSI {rsi:.1f}: Normal zone")
    rfig = go.Figure(go.Scatter(x=df.index, y=df["RSI"], name="RSI"))
    rfig.add_hline(y=70, line_dash="dash", line_color="red")
    rfig.add_hline(y=30, line_dash="dash", line_color="green")
    rfig.update_layout(height=250, yaxis_range=[0, 100])
    st.plotly_chart(rfig, use_container_width=True)

    st.markdown(f"### 📰 {name}: taaza khabrein")
    show_news(f"{name} market" if name in INDICES else f"{name} share NSE",
              symbol=symbol, limit=8)


# =====================================================================
# PAGE 4: Scanners & Alerts
# =====================================================================
@st.cache_data(ttl=300)
def scan_all(items):
    rows = []
    for nm, sym in items:
        try:
            d = load_data(sym, "1y")
            res = analyse_one(d)
            if res:
                rows.append({"Stock": nm, **res})
        except Exception:
            continue
    return pd.DataFrame(rows)


def analyse_one(d):
    d = d.dropna()
    if len(d) < 60:
        return None
    c = d["Close"]
    p = float(c.iloc[-1])
    pv = float(c.iloc[-2])
    m20 = c.rolling(20).mean().iloc[-1]
    m50 = c.rolling(50).mean().iloc[-1]
    r = float(rsi_series(c).iloc[-1])
    if p > m20 > m50:
        sg = "🟢 BUY"
    elif p < m20 < m50:
        sg = "🔴 SELL"
    else:
        sg = "🟡 WAIT"
    if r > 70:
        rz = "🔥 Overbought"
    elif r < 30:
        rz = "🧊 Oversold"
    else:
        rz = "Normal"
    return {
        "Signal": sg,
        "Price": round(p, 2),
        "Change %": round((p - pv) / pv * 100, 2),
        "RSI": round(r, 1),
        "RSI Zone": rz,
    }


@st.cache_data(ttl=600)
def scan_nifty50(tickers):
    syms = [t + ".NS" for t in tickers]
    raw = yf.download(syms, period="1y", interval="1d", group_by="ticker",
                      progress=False, auto_adjust=True, threads=True)
    rows = []
    for t, s in zip(tickers, syms):
        try:
            res = analyse_one(raw[s])
            if res:
                rows.append({"Stock": t, **res})
        except Exception:
            continue
    return pd.DataFrame(rows)


SCAN_CONFIG = {
    "Price": st.column_config.NumberColumn("Price (₹)", format="%.2f"),
    "Change %": st.column_config.NumberColumn("Change %", format="%+.2f%%"),
    "RSI": st.column_config.ProgressColumn("RSI", format="%.1f", min_value=0, max_value=100),
}


def page_scanners():
    st.title("🔍 Scanners & Alerts")
    tab1, tab2 = st.tabs(["Mere stocks + indices", "Nifty 50 (saare 50)"])

    with tab1:
        scan_df = scan_all(tuple(stocks.items()))
        if scan_df.empty:
            st.write("Scanner data load nahi hua.")
        else:
            st.dataframe(scan_df, hide_index=True, use_container_width=True,
                         column_config=SCAN_CONFIG)
            st.markdown("### 🚨 Alerts")
            hot = scan_df[scan_df["RSI"] > 70]
            cold = scan_df[scan_df["RSI"] < 30]
            buys = scan_df[scan_df["Signal"].str.contains("BUY")]
            sells = scan_df[scan_df["Signal"].str.contains("SELL")]
            if not hot.empty:
                st.error("🔥 Overbought (girne ka risk): " + ", ".join(hot["Stock"]))
            if not cold.empty:
                st.success("🧊 Oversold (bounce ka chance): " + ", ".join(cold["Stock"]))
            if not buys.empty:
                st.info("🟢 BUY signal: " + ", ".join(buys["Stock"]))
            if not sells.empty:
                st.warning("🔴 SELL signal: " + ", ".join(sells["Stock"]))
            if hot.empty and cold.empty and buys.empty and sells.empty:
                st.write("Abhi koi khaas alert nahi hai.")

    with tab2:
        if st.button("🔎 Nifty 50 scan karo (20-40 second lagte hain)"):
            with st.spinner("Saare 50 stocks check ho rahe hain..."):
                st.session_state["n50"] = scan_nifty50(tuple(NIFTY50))
        n50 = st.session_state.get("n50")
        if n50 is not None:
            if n50.empty:
                st.warning("Data nahi aaya. Thodi der baad dobara try karo.")
            else:
                f1, f2 = st.columns(2)
                sig_pick = f1.selectbox("Signal filter", ["Sab", "🟢 BUY", "🔴 SELL", "🟡 WAIT"])
                rsi_pick = f2.selectbox("RSI filter", ["Sab", "Overbought (70+)", "Oversold (30-)", "Normal"])
                view = n50.copy()
                if sig_pick != "Sab":
                    view = view[view["Signal"] == sig_pick]
                if rsi_pick == "Overbought (70+)":
                    view = view[view["RSI"] > 70]
                elif rsi_pick == "Oversold (30-)":
                    view = view[view["RSI"] < 30]
                elif rsi_pick == "Normal":
                    view = view[(view["RSI"] >= 30) & (view["RSI"] <= 70)]
                nb = int((n50["Signal"] == "🟢 BUY").sum())
                ns = int((n50["Signal"] == "🔴 SELL").sum())
                st.caption(f"Kul {len(n50)} scan hue: 🟢 BUY {nb}, 🔴 SELL {ns}. "
                           f"Filter ke baad {len(view)} dikh rahe hain.")
                st.dataframe(view, hide_index=True, use_container_width=True,
                             column_config=SCAN_CONFIG)
                t1, t2 = st.columns(2)
                top = n50.sort_values("Change %", ascending=False).head(5)
                bot = n50.sort_values("Change %").head(5)
                t1.markdown("**🚀 Top 5 gainers**")
                t1.dataframe(top[["Stock", "Change %"]], hide_index=True, use_container_width=True)
                t2.markdown("**📉 Top 5 losers**")
                t2.dataframe(bot[["Stock", "Change %"]], hide_index=True, use_container_width=True)


# =====================================================================
# PAGE 5: Compare
# =====================================================================
def page_compare():
    st.title("⚖️ Stock Comparison")
    names = list(stocks.keys())
    c0, c1, c2 = st.columns(3)
    period = c0.selectbox("Period", ["6mo", "1y", "2y"], index=1, key="cmp_period")
    a_name = c1.selectbox("Pehla", names, index=3, key="cmp_a")
    b_name = c2.selectbox("Doosra", names, index=4, key="cmp_b")
    if a_name == b_name:
        st.warning("Do alag stocks chuno.")
        return
    da = load_data(stocks[a_name], period)["Close"]
    db = load_data(stocks[b_name], period)["Close"]
    both = pd.concat([da.rename(a_name), db.rename(b_name)], axis=1).dropna()
    if both.empty:
        st.write("Comparison data nahi mila.")
        return
    norm = both / both.iloc[0] * 100
    cfig = go.Figure()
    for c in norm.columns:
        cfig.add_trace(go.Scatter(x=norm.index, y=norm[c], name=c))
    cfig.update_layout(height=450, yaxis_title="Growth (start = 100)")
    st.plotly_chart(cfig, use_container_width=True)
    k1, k2 = st.columns(2)
    k1.metric(a_name, f"{norm[a_name].iloc[-1] - 100:+.1f}%", help=f"{period} ka return")
    k2.metric(b_name, f"{norm[b_name].iloc[-1] - 100:+.1f}%", help=f"{period} ka return")


# =====================================================================
# PAGE 6: Backtest & Strategy Lab
# =====================================================================
def run_backtest(d):
    c = d["Close"]
    ma20_ = c.rolling(20).mean()
    ma50_ = c.rolling(50).mean()
    pos = ((c > ma20_) & (ma20_ > ma50_)).astype(int)
    ret = c.pct_change().fillna(0)
    held = pos.shift(1).fillna(0)
    strat = held * ret
    eq = (1 + strat).cumprod() * 100
    bh = (1 + ret).cumprod() * 100
    grp = (held != held.shift()).cumsum()
    trades = []
    for g in grp[held == 1].unique():
        seg = strat[(grp == g) & (held == 1)]
        trades.append((1 + seg).prod() - 1)
    return eq, bh, trades


def equity_from_pos(c, pos):
    ret = c.pct_change().fillna(0)
    held = pos.shift(1).fillna(0)
    return (1 + held * ret).cumprod() * 100


def lab_run(d):
    c = d["Close"]
    m20 = c.rolling(20).mean()
    m50 = c.rolling(50).mean()
    rs = rsi_series(c)
    base = (c > m20) & (m20 > m50)
    pos_ma = base.astype(int)
    pos_rsi = (base & (rs < 70)).astype(int)
    vals = []
    in_trade = False
    entry = 0.0
    blocked = False
    for price_, ok in zip(c.values, base.values):
        if not ok:
            blocked = False
        if in_trade:
            if (not ok) or price_ < entry * 0.98:
                if ok:
                    blocked = True
                in_trade = False
        elif ok and not blocked:
            in_trade = True
            entry = price_
        vals.append(1 if in_trade else 0)
    pos_sl = pd.Series(vals, index=c.index)
    return pd.DataFrame({
        "Sirf MA": equity_from_pos(c, pos_ma),
        "MA + RSI filter": equity_from_pos(c, pos_rsi),
        "MA + 2% stop loss": equity_from_pos(c, pos_sl),
        "Seedha kharid ke rakho": c / c.iloc[0] * 100,
    })


def page_backtest():
    st.title("🧪 Backtest & Strategy Lab")
    name = st.selectbox("Stock / Index", list(stocks.keys()), key="bt_name")
    d = load_data(stocks[name], "2y")
    st.caption(f"Stock: {name}. Pichle 2 saal. Brokerage/tax shamil nahi. Sirf seekhne ke liye.")
    if len(d) < 120:
        st.write("Backtest ke liye kam data hai.")
        return

    st.markdown("### Backtest: Price > MA20 > MA50 ho to kharido")
    eq, bh, trades = run_backtest(d)
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Signal strategy", f"{eq.iloc[-1] - 100:+.1f}%")
    b2.metric("Seedha kharid ke rakho", f"{bh.iloc[-1] - 100:+.1f}%")
    b3.metric("Total trades", len(trades))
    if trades:
        wins = sum(1 for t in trades if t > 0)
        b4.metric("Jeetne wale trades", f"{wins / len(trades) * 100:.0f}%")
    else:
        b4.metric("Jeetne wale trades", "NA")
    bfig = go.Figure()
    bfig.add_trace(go.Scatter(x=eq.index, y=eq, name="Signal strategy"))
    bfig.add_trace(go.Scatter(x=bh.index, y=bh, name="Buy & Hold"))
    bfig.update_layout(height=380, yaxis_title="Growth (start = 100)")
    st.plotly_chart(bfig, use_container_width=True)

    st.markdown("### 🔬 Strategy Lab: kaun sa tareeka behtar?")
    lab = lab_run(d)
    lfig = go.Figure()
    for col_name in lab.columns:
        lfig.add_trace(go.Scatter(x=lab.index, y=lab[col_name], name=col_name))
    lfig.update_layout(height=420, yaxis_title="Growth (start = 100)")
    st.plotly_chart(lfig, use_container_width=True)
    res = pd.DataFrame({
        "Tareeka": lab.columns,
        "Return %": [round(lab[x].iloc[-1] - 100, 1) for x in lab.columns],
    }).sort_values("Return %", ascending=False)
    st.dataframe(res, hide_index=True, use_container_width=True)
    best = res.iloc[0]
    st.info(f"Sabse achha tareeka: {best['Tareeka']} ({best['Return %']:+.1f}%). "
            "Ye purana data hai, guarantee nahi.")


# =====================================================================
# PAGE 7: Paper Portfolio
# =====================================================================
def parse_portfolio(text):
    rows = []
    for line in text.splitlines():
        parts = [x.strip() for x in line.split(",")]
        if len(parts) != 3:
            continue
        try:
            rows.append((parts[0].upper(), float(parts[1]), float(parts[2])))
        except ValueError:
            continue
    return rows


def page_portfolio():
    st.title("💼 Paper Portfolio (virtual, practice ke liye)")
    st.caption("Har line mein: SYMBOL, quantity, kharid bhav. Jaise: RELIANCE, 10, 1300")
    pf_default = st.query_params.get("pf", "RELIANCE, 10, 1300\nTCS, 5, 2400")
    pf_text = st.text_area("Apne stocks", value=pf_default, height=120)
    if pf_text.strip():
        st.query_params["pf"] = pf_text
    elif "pf" in st.query_params:
        del st.query_params["pf"]

    pf_rows = parse_portfolio(pf_text)
    if not pf_rows:
        st.write("Koi sahi line nahi mili. Format: SYMBOL, quantity, kharid bhav")
        return
    table = []
    for sym_, qty_, buy_ in pf_rows:
        try:
            ticker_ = stocks.get(sym_, sym_ + ".NS")
            d_ = load_data(ticker_, "6mo")
            now_ = float(d_["Close"].iloc[-1])
        except Exception:
            continue
        inv_ = qty_ * buy_
        val_ = qty_ * now_
        table.append({
            "Stock": sym_,
            "Qty": qty_,
            "Kharid": round(buy_, 2),
            "Abhi": round(now_, 2),
            "Lagaya (₹)": round(inv_, 0),
            "Abhi value (₹)": round(val_, 0),
            "Profit/Loss (₹)": round(val_ - inv_, 0),
            "P/L %": round((val_ - inv_) / inv_ * 100, 2) if inv_ else 0.0,
        })
    if not table:
        st.warning("Kisi symbol ka data nahi mila. Symbol check karo (jaise RELIANCE, TCS).")
        return
    pf = pd.DataFrame(table)
    tot_inv = pf["Lagaya (₹)"].sum()
    tot_val = pf["Abhi value (₹)"].sum()
    tot_pl = tot_val - tot_inv
    p1, p2, p3 = st.columns(3)
    p1.metric("Kul lagaya", f"₹ {tot_inv:,.0f}")
    p2.metric("Abhi ki value", f"₹ {tot_val:,.0f}")
    p3.metric("Kul profit/loss", f"₹ {tot_pl:,.0f}",
              f"{tot_pl / tot_inv * 100:+.2f}%" if tot_inv else None)
    st.dataframe(
        pf, hide_index=True, use_container_width=True,
        column_config={"P/L %": st.column_config.NumberColumn("P/L %", format="%+.2f%%")},
    )
    pie = go.Figure(go.Pie(labels=pf["Stock"], values=pf["Abhi value (₹)"], hole=0.45))
    pie.update_layout(height=320, title="Kis stock mein kitna hissa")
    st.plotly_chart(pie, use_container_width=True)
    biggest = pf.sort_values("Abhi value (₹)", ascending=False).iloc[0]
    share = biggest["Abhi value (₹)"] / tot_val * 100 if tot_val else 0
    if share > 50:
        st.warning(f"{biggest['Stock']} tere portfolio ka {share:.0f}% hai. "
                   "Ek hi stock mein zyada paisa risky hota hai.")


# =====================================================================
# PAGE 8: Option Chain (estimate, sirf seekhne ke liye)
# =====================================================================
def _ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(spot, strike, t, vol, kind, r=0.065):
    """Black-Scholes premium + delta (estimate)."""
    t = max(t, 1e-4)
    vol = max(vol, 0.01)
    d1 = (math.log(spot / strike) + (r + vol * vol / 2) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    if kind == "CE":
        p = spot * _ncdf(d1) - strike * math.exp(-r * t) * _ncdf(d2)
        delta = _ncdf(d1)
    else:
        p = strike * math.exp(-r * t) * _ncdf(-d2) - spot * _ncdf(-d1)
        delta = _ncdf(d1) - 1
    return max(p, 0.05), delta


@st.cache_data(ttl=300)
def load_vix():
    try:
        v = load_data("^INDIAVIX", "5d")
        return float(v["Close"].iloc[-1])
    except Exception:
        return 14.0


def page_option():
    st.title("🎯 Option Chain (Seekhne ke liye)")
    st.warning(
        "⚠️ Ye **LIVE option chain nahi hai**. Premium **Black-Scholes se andaza** "
        "(estimate) hai, spot price + India VIX se. Asli bhav broker app mein dekho. "
        "Ye page sirf seekhne ke liye hai, real paise ke decision ke liye nahi."
    )

    c1, c2, c3 = st.columns(3)
    nm = c1.selectbox("Index", INDICES, key="opt_idx")
    dte = c2.selectbox("Expiry me kitne din bache?", [1, 2, 3, 5, 7, 10, 14, 21, 30],
                       index=3, key="opt_dte")
    step_default = {"NIFTY 50": 50, "BANK NIFTY": 100, "SENSEX": 100}[nm]
    lot_default = {"NIFTY 50": 65, "BANK NIFTY": 30, "SENSEX": 20}[nm]
    vix = load_vix()
    iv_pct = c3.number_input("IV % (VIX se liya, badal sakte ho)", 5.0, 80.0,
                             round(vix, 1), 0.5, key="opt_iv")
    lot = st.number_input("Lot size (broker se confirm karo)", 1, 5000, lot_default,
                          key="opt_lot")

    try:
        raw = load_intraday(stocks[nm], "5d", "5m")
        r = compute_live(raw, "Aaj")
    except Exception as e:
        st.error(f"Data nahi aaya: {e}")
        return

    d = r["d"]
    spot = r["ltp"]
    sup, res_ = r["sup"], r["res"]
    e9 = float(d["EMA9"].iloc[-1])
    e21 = float(d["EMA21"].iloc[-1])
    bull = e9 > e21

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Spot (5m close)", f"{spot:,.2f}")
    m2.metric("Support", f"{sup:,.0f}")
    m3.metric("Resistance", f"{res_:,.0f}")
    m4.metric("India VIX", f"{vix:.1f}")

    step = step_default
    atm = round(spot / step) * step
    t = dte / 365.0
    vol = iv_pct / 100.0

    rows = []
    for k in range(-5, 6):
        stk = atm + k * step
        ce, cd = bs_price(spot, stk, t, vol, "CE")
        pe, pdl = bs_price(spot, stk, t, vol, "PE")
        rows.append({
            "Strike": int(stk),
            "CE premium": round(ce, 1),
            "CE delta": round(cd, 2),
            "PE premium": round(pe, 1),
            "PE delta": round(pdl, 2),
            "Type": "ATM" if k == 0 else ("CE ITM" if k < 0 else "PE ITM"),
        })
    chain = pd.DataFrame(rows)

    st.subheader("🧭 Signal ke hisab se idea (seekhne ke liye)")
    last_ev = r["events"][0] if r["events"] else None
    if last_ev:
        st.caption(f"Aakhri cross: {last_ev[1]} @ {last_ev[2]:,.1f} "
                   f"({last_ev[0].strftime('%d %b %H:%M')})")

    near_res = (res_ - spot) / spot < 0.0015
    near_sup = (spot - sup) / spot < 0.0015
    if bull and not near_res:
        kind, why = "CE", "EMA9 > EMA21 (tezi), price resistance se thoda door"
    elif (not bull) and not near_sup:
        kind, why = "PE", "EMA9 < EMA21 (mandi), price support se thoda door"
    else:
        kind, why = None, "Price support/resistance ke bahut paas hai. Wait karna behtar."

    if kind is None:
        st.info(f"⏸️ **Abhi wait**: {why}")
    else:
        stk = atm
        prem, dl = bs_price(spot, stk, t, vol, kind)
        sl_p = prem * 0.75
        tg_p = prem * 1.40
        icon = "🟢" if kind == "CE" else "🔴"
        st.success(f"{icon} **{nm} {int(stk)} {kind}** (ATM) ke baare mein seekho: {why}")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Andaza premium", f"₹{prem:,.1f}")
        a2.metric("Stop-loss (-25%)", f"₹{sl_p:,.1f}")
        a3.metric("Target (+40%)", f"₹{tg_p:,.1f}")
        a4.metric("1 lot ka paisa", f"₹{prem * lot:,.0f}")
        max_loss = (prem - sl_p) * lot
        brk = stk + prem if kind == "CE" else stk - prem
        st.write(f"- Breakeven (expiry pe): **{brk:,.0f}**")
        st.write(f"- SL pe ek lot ka nuksaan: **₹{max_loss:,.0f}**. "
                 "Ye capital ke 1-2% se zyada nahi hona chahiye.")
        if kind == "CE":
            st.write(f"- Index {sup:,.0f} (support) ke neeche band ho to idea galat.")
        else:
            st.write(f"- Index {res_:,.0f} (resistance) ke upar band ho to idea galat.")
        if dte <= 1:
            st.error("Expiry bahut paas hai. Premium bahut tezi se girta hai, zyada risky.")

    st.subheader("📋 Option chain (andaza)")
    def hl(row):
        return ["background-color: #fff3cd; color: #000" if row["Type"] == "ATM" else ""
                for _ in row]
    st.dataframe(chain.style.apply(hl, axis=1), hide_index=True,
                 use_container_width=True)
    st.caption("CE = Call (tezi pe), PE = Put (mandi pe). Delta = index 1 point badle to "
               "premium kitna badlega. Asli premium bid-ask, demand aur IV ki wajah se "
               "alag hoga.")
    st.info("📚 Yaad rakho: SEBI data ke hisab se 90% se zyada retail F&O trader "
            "paisa ganwate hain. Pehle Paper Portfolio pe practice karo.")


# =====================================================================
# Page router
# =====================================================================
PAGE_FUNCS = {
    PAGES[0]: page_live,
    PAGES[1]: page_news,
    PAGES[2]: page_stock,
    PAGES[3]: page_scanners,
    PAGES[4]: page_compare,
    PAGES[5]: page_backtest,
    PAGES[6]: page_portfolio,
    PAGES[7]: page_option,
}
PAGE_FUNCS[page]()