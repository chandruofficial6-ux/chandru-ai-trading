import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import streamlit.components.v1 as components

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
    "ITC": "ITC.NS",
    "ICICI BANK": "ICICIBANK.NS",
    "WIPRO": "WIPRO.NS",
    "L&T": "LT.NS",
}

# Watchlist: apne stocks add karo
default_w = st.query_params.get("w", "")
extra = st.sidebar.text_input(
    "➕ Apne stocks (NSE symbol, comma se)",
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

name = st.sidebar.selectbox("Stock / Index chuno", list(stocks.keys()))
period = st.sidebar.selectbox("Period", ["6mo", "1y", "2y"], index=1)
auto = st.sidebar.checkbox("🔄 Auto-refresh (har 5 min)")
if auto:
    components.html(
        "<script>setTimeout(function(){window.parent.location.reload();},300000);</script>",
        height=0,
    )
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
    st.error("Data nahi mila. Symbol check karo ya thodi der baad try karo.")
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

# ---------- Scanner ----------
st.markdown("---")
st.markdown("### 🔍 Market Scanner (saare stocks ek saath)")


@st.cache_data(ttl=300)
def scan_all(items):
    rows = []
    for nm, sym in items:
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
                rz = "🔥 Overbought"
            elif r < 30:
                rz = "🧊 Oversold"
            else:
                rz = "Normal"
            rows.append({
                "Stock": nm,
                "Signal": sg,
                "Price": round(p, 2),
                "Change %": round((p - pv) / pv * 100, 2),
                "RSI": round(r, 1),
                "RSI Zone": rz,
            })
        except Exception:
            continue
    return pd.DataFrame(rows)


scan_df = scan_all(tuple(stocks.items()))
if scan_df.empty:
    st.write("Scanner data load nahi hua.")
else:
    st.dataframe(
        scan_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Price": st.column_config.NumberColumn("Price (₹)", format="%.2f"),
            "Change %": st.column_config.NumberColumn("Change %", format="%+.2f%%"),
            "RSI": st.column_config.ProgressColumn(
                "RSI", format="%.1f", min_value=0, max_value=100),
        },
    )

# ---------- Alerts ----------
if not scan_df.empty:
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

# ---------- Comparison ----------
st.markdown("---")
st.markdown("### ⚖️ Stock Comparison")
names = list(stocks.keys())
c1, c2 = st.columns(2)
a_name = c1.selectbox("Pehla stock", names, index=2, key="cmp_a")
b_name = c2.selectbox("Doosra stock", names, index=3, key="cmp_b")

if a_name == b_name:
    st.warning("Do alag stocks chuno.")
else:
    da = load_data(stocks[a_name], period)["Close"]
    db = load_data(stocks[b_name], period)["Close"]
    both = pd.concat([da.rename(a_name), db.rename(b_name)], axis=1).dropna()
    if both.empty:
        st.write("Comparison data nahi mila.")
    else:
        norm = both / both.iloc[0] * 100
        cfig = go.Figure()
        for c in norm.columns:
            cfig.add_trace(go.Scatter(x=norm.index, y=norm[c], name=c))
        cfig.update_layout(height=400, yaxis_title="Growth (start = 100)")
        st.plotly_chart(cfig, use_container_width=True)
        ra = norm[a_name].iloc[-1] - 100
        rb = norm[b_name].iloc[-1] - 100
        k1, k2 = st.columns(2)
        k1.metric(a_name, f"{ra:+.1f}%", help=f"{period} ka return")
        k2.metric(b_name, f"{rb:+.1f}%", help=f"{period} ka return")

# ---------- Backtest ----------
st.markdown("---")
st.markdown("### 🧪 Backtest: MA signal pichle 2 saal mein kitna chala?")
st.caption(f"Stock: {name}. Rule: Price > MA20 > MA50 ho to kharido, warna cash. Brokerage/tax shamil nahi.")


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


bt_df = load_data(symbol, "2y")
if len(bt_df) < 120:
    st.write("Backtest ke liye kam data hai.")
else:
    eq, bh, trades = run_backtest(bt_df)
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
    if eq.iloc[-1] < bh.iloc[-1]:
        st.info("Is stock mein sirf kharid ke rakhna signal se behtar raha. Signal par andha bharosa mat karo.")
    else:
        st.success("Is stock mein signal ne kharid ke rakhne se behtar kaam kiya, par bhavishya mein aisa hona zaroori nahi.")

st.caption("Demo dashboard. Sirf seekhne ke liye, paisa mat lagao.")