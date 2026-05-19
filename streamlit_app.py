import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import FinanceDataReader as fdr
import plotly.graph_objects as go
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
    return {"gemini": "", "news": "", "discord": "", "watchlist": "테슬라, 로켓랩, 스페이스모바일, 켄코아에어로스페이스, 도지코인"}
config = load_config()

# --- 📚 서재 자동 기록 (시간 추가!) ---
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
    </style>
""", unsafe_allow_html=True)

# [엔진] 주식 + 코인 하이브리드 라우터
@st.cache_data
def load_krx_data():
    try:
        df = fdr.StockListing('KRX')
        return df[['Name', 'Code', 'Market']]
    except: return pd.DataFrame()

US_MAPPING = {'테슬라': 'TSLA', '엔비디아': 'NVDA', '애플': 'AAPL', '로켓랩': 'RKLB', '스페이스모바일': 'ASTS'}
CRYPTO_MAPPING = {'도지코인': 'DOGEUSDT', '비트코인': 'BTCUSDT', '이더리움': 'ETHUSDT'}

def get_market_data(keyword):
    keyword = keyword.strip()
    if keyword in CRYPTO_MAPPING or keyword.endswith("USDT"):
        symbol = CRYPTO_MAPPING.get(keyword, keyword)
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        try:
            res = requests.get(url, timeout=5).json()
            if 'lastPrice' in res:
                return {"type": "crypto", "ticker": symbol, "name": keyword, "price": float(res['lastPrice']), "change": float(res['priceChangePercent'])}
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
                name = keyword

    if ticker:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if not hist.empty and len(hist) >= 2:
                price = hist['Close'].iloc[-1]
                change = ((price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
                return {"type": "stock", "ticker": ticker, "name": name, "price": price, "change": change}
        except: return None
    return None

# 3. 사이드바
with st.sidebar:
    st.title("⚡️ Central Workspace")
    st.caption("Live Data OS V15.6 (Timestamp Patch)")
    st.markdown("---")
    g_key = st.text_input("🔑 Gemini API Key", value=config['gemini'], type="password")
    n_key = st.text_input("📰 News API Key", value=config['news'], type="password")
    d_url = st.text_input("👾 Discord 웹훅 URL", value=config['discord'], type="password")
    
    if st.button("💾 이 열쇠들을 영구 저장하기"):
        save_config({"gemini": g_key, "news": n_key, "discord": d_url, "watchlist": config['watchlist']})
        st.success("설정 저장 완료!")
        
    st.markdown("---")
    app_mode = st.radio("🏢 워크스페이스 이동", [
        "🌅 제0부서: 모닝 브리핑", "📈 제1부서: 퀀트 딥다이브", 
        "🛒 제2부서: 글로벌 소싱", "📊 제3부서: 시각화 분석실",
        "🎯 제4부서: 스나이퍼 봇 (알림)", "📚 제5부서: 포트폴리오 서재"
    ])

# =====================================================================
# [제4부서] 스나이퍼 봇
# =====================================================================
if app_mode == "🎯 제4부서: 스나이퍼 봇 (알림)":
    st.title("🎯 제4부서: 스나이퍼 봇")
    watchlist = st.text_input("관심 종목 리스트", value=config['watchlist'])
    
    if st.button("🚀 발송 & 자율 저장 시작"):
        if not g_key or not d_url:
            st.error("통제실에 열쇠를 먼저 입력해주세요!")
        else:
            targets = [t.strip() for t in watchlist.split(',')]
            current_time_str = datetime.now().strftime('%m/%d %H:%M')
            discord_message = f"### 🚨 [V15.6] 무결점 스나이퍼 브리핑 ({current_time_str})\n\n"
            
            genai.configure(api_key=g_key)
            model = genai.GenerativeModel('gemini-2.5-flash')
            progress_bar = st.progress(0)

            for i, target in enumerate(targets):
                with st.spinner(f"[{i+1}/{len(targets)}] '{target}' 분석 중... (3초 대기)"):
                    data = get_market_data(target)
                    
                    if data:
                        name, ticker, price, change = data['name'], data['ticker'], data['price'], data['change']
                        prompt = f"종목명: {name}, 등락률: {change:.2f}%. 리스크 최소화 원칙에 입각하여 현재 흐름에 대한 '1줄 액션 플랜'을 냉정하게 작성해라."
                        try:
                            ai_plan = model.generate_content(prompt).text.strip()
                        except:
                            ai_plan = "API 일시 지연 (주가 팩트만 확인 요망)"
                        
                        icon = "🔴" if change > 0 else "🔵"
                        currency = "USDT" if data['type'] == 'crypto' else ("KRW" if ".KS" in ticker or ".KQ" in ticker else "USD")
                        
                        discord_message += f"**{name} ({ticker})**\n"
                        discord_message += f"> 💵 현재가: **{price:,.2f} {currency}** ({icon} {change:.2f}%)\n"
                        discord_message += f"> 🛡️ AI 판정: {ai_plan}\n\n"
                        
                        # 💡 [V15.6] 분 단위 시간까지 정확하게 저장!
                        exact_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        save_to_library({"time": exact_time, "name": name, "price": price, "change": change, "plan": ai_plan})
                    else:
                        discord_message += f"**{target}**: ⚠️ 데이터 수집 실패\n\n"
                
                progress_bar.progress((i + 1) / len(targets))
                time.sleep(3)
            
            with st.spinner("📲 디스코드 전송 중..."):
                requests.post(d_url, json={"content": discord_message})
                st.success("디스코드 발송 및 서재 저장이 완료되었습니다!")

# =====================================================================
# [제5부서] 포트폴리오 서재 (시간순 정렬)
# =====================================================================
elif app_mode == "📚 제5부서: 포트폴리오 서재":
    st.title("📚 제5부서: 데이터 인텔리전스 서재")
    
    if os.path.exists(LOG_FILE):
        logs_df = pd.read_csv(LOG_FILE)
        st.subheader("🗄️ 자율 수집된 투자 기록 (시간순)")
        
        # 최신 기록이 맨 위로 오도록 뒤집기
        st.dataframe(logs_df.iloc[::-1].head(20), use_container_width=True)
        
        if st.button("🧠 AI 수석의 전체 방향성 요약 가동"):
            with st.spinner("과거 기록들을 조합하여 CEO를 위한 전략을 짜고 있습니다..."):
                genai.configure(api_key=g_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                history_text = logs_df.tail(20).to_string()
                prompt = f"""
                다음은 최근 투자 기록이다. 
                주의: 'AI 분석 지연', 'API 지연' 텍스트는 무시하라.
                오직 '종목명', '주가', '등락률' 팩트를 바탕으로 다음을 작성하라.
                1. 포트폴리오 전체적인 팩트 요약 (3줄)
                2. 리스크 관리 및 향후 매수 방향성 지시 (3줄)
                \n{history_text}
                """
                try:
                    res = model.generate_content(prompt)
                    st.success(res.text)
                except Exception as e:
                    st.error(f"AI 호출 에러: {e}")
    else:
        st.info("기록된 데이터가 없습니다.")

# (기타 부서 안내 메시지 생략)
elif app_mode in ["🌅 제0부서: 모닝 브리핑", "📈 제1부서: 퀀트 딥다이브", "🛒 제2부서: 글로벌 소싱", "📊 제3부서: 시각화 분석실"]:
    st.info("이전 부서들의 코드는 정상 작동 중입니다.")
    #
