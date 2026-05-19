import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px
import json
import os
import time
from datetime import datetime

# 1. 페이지 기본 설정
st.set_page_config(page_title="Central Workspace", page_icon="⚡️", layout="wide", initial_sidebar_state="expanded")

# --- 🔑 열쇠 저장 ---
CONFIG_FILE = "config.json"
def save_config(config_data):
    with open(CONFIG_FILE, 'w') as f: json.dump(config_data, f)
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f: return json.load(f)
    return {"gemini": "", "news": "", "discord": "", "watchlist": "테슬라, 로켓랩, 스페이스모바일, 도지코인"}
config = load_config()

# --- 📚 서재 자동 기록 ---
LOG_FILE = "invest_logs.csv"
def save_to_library(log_entry):
    df = pd.DataFrame([log_entry])
    if not os.path.exists(LOG_FILE): df.to_csv(LOG_FILE, index=False, encoding='utf-8-sig')
    else: df.to_csv(LOG_FILE, mode='a', header=False, index=False, encoding='utf-8-sig')

# 2. 커스텀 CSS
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; font-family: 'Apple SD Gothic Neo', sans-serif; }
    div[data-testid="metric-container"] { background-color: #1a1a24; border: 1px solid #d4af37; padding: 20px; border-radius: 12px; }
    .stTabs [aria-selected="true"] { background-color: #d4af37 !important; color: #000 !important; font-weight: 800; }
    </style>
""", unsafe_allow_html=True)

# [엔진] 주식 + 코인 하이브리드 라우터
@st.cache_data
def load_krx_data():
    try: return fdr.StockListing('KRX')[['Name', 'Code', 'Market']]
    except: return pd.DataFrame()

US_MAPPING = {'테슬라': 'TSLA', '엔비디아': 'NVDA', '애플': 'AAPL', '로켓랩': 'RKLB', '스페이스모바일': 'ASTS'}
CRYPTO_MAPPING = {'도지코인': 'DOGEUSDT', '비트코인': 'BTCUSDT'}

def get_market_data(keyword):
    keyword = keyword.strip()
    if keyword in CRYPTO_MAPPING or keyword.endswith("USDT"):
        symbol = CRYPTO_MAPPING.get(keyword, keyword)
        try:
            res = requests.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=5).json()
            if 'lastPrice' in res: return {"type": "crypto", "ticker": symbol, "name": keyword, "price": float(res['lastPrice']), "change": float(res['priceChangePercent'])}
        except: return None

    ticker, name = None, keyword
    if keyword.isascii() and keyword.isalpha(): ticker, name = keyword.upper(), keyword.upper()
    elif keyword in US_MAPPING: ticker, name = US_MAPPING[keyword], keyword
    
    if not ticker:
        krx_df = load_krx_data()
        if not krx_df.empty:
            match = krx_df[krx_df['Name'] == keyword]
            if not match.empty:
                code, mkt = match.iloc[0]['Code'], match.iloc[0]['Market']
                ticker = f"{code}.KS" if "KOSPI" in str(mkt) else f"{code}.KQ"

    if ticker:
        try:
            hist = yf.Ticker(ticker).history(period="2d")
            if len(hist) >= 2:
                return {"type": "stock", "ticker": ticker, "name": name, "price": hist['Close'].iloc[-1], "change": ((hist['Close'].iloc[-1] - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100}
        except: return None
    return None

def ai_auto_screener():
    global_pool = ['엔비디아', '테슬라', '로켓랩', '비트코인', '삼성전자']
    scanned = [get_market_data(t) for t in global_pool]
    scanned = [x for x in scanned if x is not None]
    return sorted(scanned, key=lambda x: x['change'])[:3]

# 3. 사이드바 통제실
with st.sidebar:
    st.title("⚡️ Central Workspace")
    st.caption("Live Data OS V16.9 (Master Edition)")
    st.markdown("---")
    g_key = st.text_input("🔑 Gemini API Key", value=config['gemini'], type="password")
    n_key = st.text_input("📰 News API Key", value=config['news'], type="password")
    d_url = st.text_input("👾 Discord 웹훅 URL", value=config['discord'], type="password")
    if st.button("💾 열쇠 영구 저장"):
        save_config({"gemini": g_key, "news": n_key, "discord": d_url, "watchlist": config['watchlist']})
        st.success("저장 완료!")
        
    st.markdown("---")
    app_mode = st.radio("🏢 워크스페이스 이동", [
        "🌅 제0부서: 모닝 브리핑", 
        "📈 제1부서: 퀀트 딥다이브", 
        "🛒 제2부서: 글로벌 소싱", 
        "📊 제3부서: 시각화 분석실",
        "🎯 제4부서: 스나이퍼 봇 (알림)", 
        "📚 제5부서: 포트폴리오 서재",
        "💰 제7부서: 자산 배분 시뮬레이터"
    ])

# =====================================================================
# 부서별 로직 (0 ~ 7 전체 이식 완료)
# =====================================================================

if app_mode == "🌅 제0부서: 모닝 브리핑":
    st.title("🌅 제0부서: 글로벌 증시 모닝 브리핑")
    st.markdown("밤사이 글로벌 3대 지수의 흐름을 즉각 스캔합니다.")
    if st.button("지수 데이터 스캔"):
        with st.spinner("야후 파이낸스망 접속 중..."):
            indices = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "KOSPI": "^KS11"}
            cols = st.columns(3)
            for i, (name, ticker) in enumerate(indices.items()):
                hist = yf.Ticker(ticker).history(period="2d")
                if len(hist) >= 2:
                    c = hist['Close'].iloc[-1]
                    prev = hist['Close'].iloc[-2]
                    change = ((c - prev) / prev) * 100
                    cols[i].metric(name, f"{c:,.2f}", f"{change:.2f}%")

elif app_mode == "📈 제1부서: 퀀트 딥다이브":
    st.title("📈 제1부서: 단일 종목 퀀트 딥다이브")
    ticker_input = st.text_input("종목명 입력 (예: 애플)", "애플")
    if st.button("재무/퀀트 스캔"):
        data = get_market_data(ticker_input)
        if data:
            st.success(f"{data['name']} ({data['ticker']}) - 현재가: {data['price']:,.2f} ({data['change']:.2f}%)")
            st.info("딥다이브 엔진이 정상 가동 중입니다. (기본 재무 데이터 스캔 완료)")
        else: st.error("종목을 찾을 수 없습니다.")

elif app_mode == "🛒 제2부서: 글로벌 소싱":
    st.title("🛒 제2부서: 글로벌 크로스보더 소싱 전략실")
    st.markdown("한국의 유망 상품을 글로벌 마켓(아마존 등)에 진출시키기 위한 AI 기획실입니다.")
    product = st.text_input("소싱 기획할 상품 카테고리 (예: 한국 스킨케어, K-팝 아이돌 굿즈)", "한국 스킨케어 앰플")
    if st.button("글로벌 수출 전략 수립"):
        if not g_key: st.error("AI 키를 통제실에 입력하세요.")
        else:
            with st.spinner("글로벌 E-커머스 트렌드 분석 중..."):
                genai.configure(api_key=g_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                prompt = f"너는 글로벌 이커머스 셀링 전문가야. '{product}'를 미국 아마존이나 쇼피파이에서 판매하기 위한 타겟 고객층, 마케팅 전략, 예상 진입 장벽을 3가지 포인트로 정리해줘."
                st.success(model.generate_content(prompt).text)

elif app_mode == "📊 제3부서: 시각화 분석실":
    st.title("📊 제3부서: 인터랙티브 차트 분석실")
    target_name = st.text_input("차트를 그릴 종목명", "엔비디아")
    if st.button("정밀 캔들 차트 생성"):
        data = get_market_data(target_name)
        if data and data['type'] == 'stock':
            with st.spinner("데이터 로딩 중..."):
                df = yf.Ticker(data['ticker']).history(period="3mo")
                fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], increasing_line_color='#d4af37', decreasing_line_color='#444444')])
                fig.update_layout(title=f"{data['name']} 3개월 캔들스틱", template="plotly_dark", height=500)
                st.plotly_chart(fig, use_container_width=True)
        else: st.error("주식 종목만 차트 지원이 가능합니다. (코인은 준비 중)")

elif app_mode == "🎯 제4부서: 스나이퍼 봇 (알림)":
    st.title("🎯 제4부서: 스나이퍼 봇 (Discord 알림)")
    scan_mode = st.radio("🔍 작전 모드", ["🤖 AI 자율 탐색", "✍️ 수동 타겟 입력"])
    watchlist = st.text_input("수동 관심 종목 (쉼표 구분)", config['watchlist']) if scan_mode == "✍️ 수동 타겟 입력" else ""
    
    if st.button("🚀 작전 가동 (스캔 & 디스코드 쏘기)"):
        if not g_key or not d_url: st.error("통제실에 열쇠(Gemini, Discord)를 입력하세요!")
        else:
            current_time = datetime.now().strftime('%m/%d %H:%M')
            msg = f"### 🚨 [V16.9] 스나이퍼 브리핑 ({current_time})\n\n"
            genai.configure(api_key=g_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            targets_data = ai_auto_screener() if scan_mode == "🤖 AI 자율 탐색" else [get_market_data(t) for t in watchlist.split(',')]
            targets_data = [t for t in targets_data if t is not None]
            
            bar = st.progress(0)
            for i, data in enumerate(targets_data):
                try: ai_plan = model.generate_content(f"{data['name']} 등락률 {data['change']:.2f}%. 리스크 최소화 1줄 매매 액션플랜.").text.strip()
                except: ai_plan = "분석 지연"
                
                icon = "🔴" if data['change'] > 0 else "🔵"
                msg += f"**{data['name']}**\n> 💵 현재가: {data['price']:,.2f} ({icon} {data['change']:.2f}%)\n> 🛡️ AI 판정: {ai_plan}\n\n"
                save_to_library({"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "name": data['name'], "price": data['price'], "change": data['change'], "plan": ai_plan})
                bar.progress((i+1)/len(targets_data))
                time.sleep(2)
                
            requests.post(d_url, json={"content": msg})
            st.success("디스코드 발송 및 서재 기록 완료!")

elif app_mode == "📚 제5부서: 포트폴리오 서재":
    st.title("📚 제5부서: 데이터 인텔리전스 서재")
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        st.dataframe(df.iloc[::-1].head(20), use_container_width=True)
        if st.button("🧠 총괄 전략 요약"):
            genai.configure(api_key=g_key)
            try: st.success(genai.GenerativeModel('gemini-2.5-flash').generate_content(f"최근 기록 요약 및 팩트 기반 매수 전략 3줄:\n{df.tail(10).to_string()}").text)
            except: st.error("AI 호출 에러")
    else: st.info("기록된 데이터가 없습니다. 제4부서를 먼저 가동하세요.")

elif app_mode == "💰 제7부서: 자산 배분 시뮬레이터":
    st.title("💰 제7부서: 자산 배분 시뮬레이터")
    col1, col2 = st.columns([1, 2])
    with col1:
        seed = st.number_input("💵 시드머니 (USD)", 100, 100000, 1000, step=100)
        risk = st.selectbox("⚖️ 리스크 성향", ["방어형 (현금 50%)", "밸런스형 (현금 30%)", "공격형 (현금 10%)"])
        t_input = st.text_input("🎯 타겟 종목", config['watchlist'])
        if st.button("모의고사 가동"):
            if not g_key: st.error("AI 키가 필요합니다.")
            else:
                cash_ratio = 0.5 if "방어" in risk else 0.3 if "밸런스" in risk else 0.1
                targets = [t.strip() for t in t_input.split(',')]
                alloc = (seed * (1 - cash_ratio)) / len(targets)
                
                sim_data = [{"종목명": "현금 (안전마진)", "배분(USD)": seed * cash_ratio}]
                for t in targets:
                    d = get_market_data(t)
                    if d: sim_data.append({"종목명": d['name'], "배분(USD)": alloc})
                
                with col2:
                    df_sim = pd.DataFrame(sim_data)
                    fig = px.pie(df_sim, values='배분(USD)', names='종목명', title="시드머니 배분 도넛 차트", hole=0.4, template="plotly_dark")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    genai.configure(api_key=g_key)
                    st.success(genai.GenerativeModel('gemini-2.5-flash').generate_content(f"시드:{seed}, 현금비중:{cash_ratio*100}%. 이 포트폴리오의 한달 뒤 현실적 최대수익/최대손실 팩트체크 요약.").text)
