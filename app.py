import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# 국내 주식 10개 (yfinance 티커: 종목코드.KS 또는 .KQ)
STOCKS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차": "005380.KS",
    "POSCO홀딩스": "005490.KS",
    "카카오": "035720.KS",
    "네이버": "035420.KS",
    "셀트리온": "068270.KS",
    "기아": "000270.KS",
}

st.set_page_config(
    page_title="국내 주식 대시보드",
    page_icon="📈",
    layout="wide",
)

st.title("📈 국내 주식 10종목 대시보드")
st.markdown("---")

# 사이드바 설정
st.sidebar.header("⚙️ 설정")
period_options = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo", "1년": "1y", "2년": "2y"}
selected_period_label = st.sidebar.selectbox("조회 기간", list(period_options.keys()), index=2)
selected_period = period_options[selected_period_label]

selected_stocks = st.sidebar.multiselect(
    "종목 선택",
    list(STOCKS.keys()),
    default=list(STOCKS.keys()),
)

@st.cache_data(ttl=300)
def load_stock_data(tickers: dict, period: str):
    data = {}
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, period=period, progress=False, auto_adjust=True)
            if not df.empty:
                data[name] = df
        except Exception:
            pass
    return data

@st.cache_data(ttl=300)
def load_current_info(tickers: dict):
    rows = []
    for name, ticker in tickers.items():
        try:
            info = yf.Ticker(ticker).fast_info
            rows.append({
                "종목명": name,
                "티커": ticker,
                "현재가 (원)": int(info.last_price) if info.last_price else None,
                "52주 최고 (원)": int(info.year_high) if info.year_high else None,
                "52주 최저 (원)": int(info.year_low) if info.year_low else None,
                "시가총액 (억)": int(info.market_cap / 1e8) if info.market_cap else None,
            })
        except Exception:
            rows.append({"종목명": name, "티커": ticker})
    return pd.DataFrame(rows)

if not selected_stocks:
    st.warning("사이드바에서 최소 1개 종목을 선택하세요.")
    st.stop()

selected_tickers = {k: STOCKS[k] for k in selected_stocks}

with st.spinner("주식 데이터를 불러오는 중..."):
    stock_data = load_stock_data(selected_tickers, selected_period)
    info_df = load_current_info(selected_tickers)

# ── 현재가 요약 카드 ──────────────────────────────────────────
st.subheader("📊 현재가 요약")
cols = st.columns(min(5, len(selected_stocks)))
for i, name in enumerate(selected_stocks):
    col = cols[i % 5]
    row = info_df[info_df["종목명"] == name]
    if not row.empty and pd.notna(row.iloc[0].get("현재가 (원)")):
        price = int(row.iloc[0]["현재가 (원)"])
        col.metric(label=name, value=f"{price:,}원")
    else:
        col.metric(label=name, value="N/A")

st.markdown("---")

# ── 종목 상세 정보 테이블 ─────────────────────────────────────
st.subheader("📋 종목 상세 정보")
display_df = info_df[info_df["종목명"].isin(selected_stocks)].reset_index(drop=True)
for col in ["현재가 (원)", "52주 최고 (원)", "52주 최저 (원)", "시가총액 (억)"]:
    if col in display_df.columns:
        display_df[col] = display_df[col].apply(
            lambda x: f"{int(x):,}" if pd.notna(x) else "N/A"
        )
st.dataframe(display_df, use_container_width=True, hide_index=True)

st.markdown("---")

# ── 주가 추이 차트 ────────────────────────────────────────────
st.subheader(f"📉 주가 추이 ({selected_period_label})")

tab1, tab2 = st.tabs(["개별 차트", "정규화 비교 차트"])

with tab1:
    for name in selected_stocks:
        if name not in stock_data:
            st.warning(f"{name} 데이터를 불러올 수 없습니다.")
            continue
        df = stock_data[name]
        close = df["Close"].squeeze()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=close.index, y=close.values,
            mode="lines", name=name,
            line=dict(width=2),
            fill="tozeroy", fillcolor="rgba(99,110,250,0.1)",
        ))
        fig.update_layout(
            title=f"{name} 주가",
            xaxis_title="날짜",
            yaxis_title="종가 (원)",
            height=300,
            margin=dict(l=40, r=20, t=40, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    fig2 = go.Figure()
    for name in selected_stocks:
        if name not in stock_data:
            continue
        df = stock_data[name]
        close = df["Close"].squeeze().dropna()
        if close.empty:
            continue
        normalized = close / close.iloc[0] * 100
        fig2.add_trace(go.Scatter(
            x=normalized.index, y=normalized.values,
            mode="lines", name=name, line=dict(width=2),
        ))
    fig2.update_layout(
        title="기준일 대비 수익률 (%) — 시작일=100",
        xaxis_title="날짜",
        yaxis_title="지수 (시작=100)",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ── 거래량 차트 ───────────────────────────────────────────────
st.subheader("📦 거래량 추이")
vol_name = st.selectbox("종목 선택 (거래량)", selected_stocks)
if vol_name in stock_data:
    df_vol = stock_data[vol_name]
    volume = df_vol["Volume"].squeeze()
    fig_vol = px.bar(
        x=volume.index, y=volume.values,
        labels={"x": "날짜", "y": "거래량"},
        title=f"{vol_name} 거래량",
        color_discrete_sequence=["#636EFA"],
    )
    fig_vol.update_layout(height=350)
    st.plotly_chart(fig_vol, use_container_width=True)

st.caption(f"데이터 출처: Yahoo Finance (yfinance) | 마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
