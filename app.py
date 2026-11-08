import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

st.set_page_config(
    page_title="Chandru AI Trading",
    page_icon="📈",
    layout="wide"
)

st.title("🚀 CHANDRU AI TRADING")
st.subheader("Smart Indian Market Analysis")

# ---------- Sidebar ----------
st.sidebar.header("⚙️ Settings")

stocks = {
    "NIFTY 50": "^NSEI",
    "BANK NIFTY": "^NSEBANK",
    "RELIANCE": "RELIANCE.NS",
    "TCS": "TCS.NS",
    "INFOSYS": "INFY.NS",
    "HDFC BANK": "HDFCBANK.NS",
    "SBI": "SBIN.NS",
}

name = st.sidebar.selectbox("Stock / Index chuno", list(stocks.keys()))
period = st.sidebar.selectbox("Period", ["6mo", "1y", "2y"], index=1)
symbol = stocks[name]


# ---------- Data ----------
@st.cache_data(ttl=300)
def load_data(symbol, period):
    df = yf.download(symbol, period=period, interval="1d",
                     progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna()


df = load_data(symbol, period)

if df.empty:
    st.error("Data nahi mila. Internet check karo ya thodi der baad try karo.")
    st.stop()

df["MA20"] = df["Close"].rolling(20).mean()
df["MA50"] = df["Close"].rolling(50).mean()

# RSI
delta = df["Close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
df["RSI"] = 100 - 100 / (1 + gain / loss)

price = float(df["Close"].iloc[-1])
prev = float(df["Close"].iloc[-2])
change = price - prev
change_pct = change / prev * 100

st.success("Trading Dashboard Started")

# ---------- Price ----------
m1, m2, m3 = st.columns(3)
m1.metric(name, f"₹ {price:,.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
m2.metric("MA 20", f"{df['MA20'].iloc[-1]:,.2f}")
m3.metric("MA 50", f"{df['MA50'].iloc[-1]:,.2f}")

# ---------- Signals ----------
st.markdown("### 📊 Trading Signals")

ma20 = df["MA20"].iloc[-1]
ma50 = df["MA50"].iloc[-1]

col1, col2, col3 = st.columns(3)

if pd.isna(ma50):
    st.warning("MA50 ke liye kam data hai. Period bada karo (1y).")
else:
    if price > ma20 > ma50:
        signal = "BUY"
        target, stop = price * 1.04, price * 0.98
        with col1:
            st.success("🟢 BUY SIGNAL (Price > MA20 > MA50)")
    elif price < ma20 < ma50:
        signal = "SELL"
        target, stop = price * 0.96, price * 1.02
        with col1:
            st.error("🔴 SELL SIGNAL (Price < MA20 < MA50)")
    else:
        signal = "WAIT"
        with col1:
            st.info("🟡 WAIT: Trend clear nahi hai")

    if signal != "WAIT":
        with col2:
            st.warning(f"🎯 TARGET: ₹ {target:,.2f}")
        with col3:
            st.error(f"🛑 STOP LOSS: ₹ {stop:,.2f}")

# ---------- Chart ----------
st.markdown("### 📈 Price Chart")
fig = go.Figure()
fig.add_trace(go.Candlestick(
    x=df.index, open=df["Open"], high=df["High"],
    low=df["Low"], close=df["Close"], name="Price"))
fig.add_trace(go.Scatter(x=df.index, y=df["MA20"], name="MA20"))
fig.add_trace(go.Scatter(x=df.index, y=df["MA50"], name="MA50"))
fig.update_layout(height=550, xaxis_rangeslider_visible=False)
st.plotly_chart(fig, use_container_width=True)

# ---------- RSI ----------
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

# ---------- News ----------
st.markdown("### 📰 Market News")
try:
    news = yf.Ticker(symbol).news
    if not news:
        st.write("Abhi koi news nahi mili.")
    for item in news[:6]:
        content = item.get("content", item)
        title = content.get("title", "No title")
        link = content.get("link", "")
        canon = content.get("canonicalUrl")
        if isinstance(canon, dict):
            link = canon.get("url", link)
        if link:
            st.markdown(f"- [{title}]({link})")
        else:
            st.markdown(f"- {title}")
except Exception:
    st.write("News load nahi hui, thodi der baad try karo.")

st.caption("Demo dashboard. Seekhne ke liye hai, isse paisa mat lagao.")
# ---------- Scanner ----------
st.markdown("---")
st.markdown("### 🔍 Market Scanner (saare stocks ek saath)")


@st.cache_data(ttl=300)
def scan_all():
    rows = []
    for nm, sym in stocks.items():
        try:
            d = yf.download(sym, period="1y", interval="1d",
                            progress=False, auto_adjust=True)
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)
            d = d.dropna()
            if len(d) < 60:
                continue
            p = float(d["Close"].iloc[-1])
            pv = float(d["Close"].iloc[-2])
            m20 = d["Close"].rolling(20).mean().iloc[-1]
            m50 = d["Close"].rolling(50).mean().iloc[-1]
            dl = d["Close"].diff()
            g = dl.clip(lower=0).rolling(14).mean()
            l = (-dl.clip(upper=0)).rolling(14).mean()
            r = float((100 - 100 / (1 + g / l)).iloc[-1])
            if p > m20 > m50:
                sg = "🟢 BUY"
            elif p < m20 < m50:
                sg = "🔴 SELL"
            else:
                sg = "🟡 WAIT"
            if r > 70:
                rz = "Overbought"
            elif r < 30:
                rz = "Oversold"
            else:
                rz = "Normal"
            rows.append({
                "Stock": nm,
                "Price": round(p, 2),
                "Change %": round((p - pv) / pv * 100, 2),
                "RSI": round(r, 1),
                "RSI Zone": rz,
                "Signal": sg,
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


scan_df = scan_all()
if scan_df.empty:
    st.write("Scanner data load nahi hua.")
else:
    st.dataframe(scan_df, hide_index=True, use_container_width=True)