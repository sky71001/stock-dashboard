import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
import os

# --- 設定頁面 (手機友善模式) ---
st.set_page_config(page_title="Invest dashboard", layout="wide", initial_sidebar_state="collapsed")
st.title("🛡️ 質押指揮中心")

# --- 檔案處理 (交易紀錄) ---
FILE_PATH = 'trade_log.csv'
if not os.path.exists(FILE_PATH):
    df = pd.DataFrame(columns=["Date", "Ticker", "Action", "Price", "Amount", "Total_Val", "Note"])
    df.to_csv(FILE_PATH, index=False)

# --- 側邊欄：全域設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    cboe_low = st.number_input("CBOE 減碼 (<)", 0.50, step=0.01)
    cboe_panic = st.number_input("CBOE 恐慌 (<)", 0.62, step=0.01)
    vix_alert_val = st.number_input("VIX 警戒 (>)", 20.0, step=0.1)
    
    st.divider()
    st.header("💰 質押總帳")
    # 這裡輸入你的總借款金額
    total_loan = st.number_input("目前總借款 (TWD)", value=1000000, step=10000)
    maint_limit = st.number_input("維持率警戒線 (%)", value=140)

# --- 功能區塊 ---
tab1, tab2, tab3 = st.tabs(["早安決策", "維持率監控", "交易紀錄"])

# === TAB 1: 晨間決策 (手機開啟通常是為了看這個) ===
with tab1:
    st.info(f"🕒 台北時間 07:00 檢核")
    
    # 1. VIX (自動)
    try:
        vix = yf.Ticker("^VIX")
        vix_data = vix.history(period="1d")
        curr_vix = vix_data['Close'].iloc[-1]
    except:
        curr_vix = 0.0
        st.error("VIX 抓取失敗")

    col_v1, col_v2 = st.columns(2)
    col_v1.metric("VIX Index", f"{curr_vix:.2f}", delta=None)
    
    if curr_vix > vix_alert_val:
        col_v1.error("🔴 市場恐慌")
    else:
        col_v1.success("🟢 情緒穩定")

    # 2. 手動輸入 P/C Ratio
    st.markdown("---")
    cboe_val = st.number_input("輸入 CBOE Equity P/C", value=0.60, step=0.01)
    cnn_val = st.number_input("輸入 CNN P/C (非指數)", value=0.70, step=0.01)
    
    # 3. 策略輸出
    st.subheader("🤖 操作指令")
    if curr_vix > vix_alert_val:
        st.warning(f"🛑 **暫停加碼**：VIX > {vix_alert_val}。優先檢查維持率。")
    elif cboe_val < cboe_low:
        if cnn_val < cboe_panic:
            st.error(f"⚠️ **強力減碼**：CBOE & CNN 雙低。減碼原始部位 10%。")
        else:
            st.warning(f"⚠️ **減碼訊號**：CBOE < {cboe_low}。減碼當日市值 10%。")
    else:
        st.success(f"✅ **維持現狀**：無減碼訊號，依計畫執行。")

# === TAB 2: 整體維持率監控 (核心功能) ===
with tab2:
    st.header("📉 整戶維持率試算")
    
    # 定義持倉 (預設值，可直接在網頁修改)
    # 你可以把你的主力 ETF 預設寫在這裡
    default_data = pd.DataFrame([
        {"Ticker": "00981.TW", "Shares": 10000},
        {"Ticker": "0050.TW", "Shares": 0},
        {"Ticker": "006208.TW", "Shares": 0}
    ])
    
    st.caption("👇 在此修改你的持股 (雙擊單元格編輯)")
    edited_df = st.data_editor(default_data, num_rows="dynamic")
    
    if st.button("🔄 計算即時維持率"):
        total_market_value = 0
        progress_text = st.empty()
        
        with st.spinner('正在抓取最新股價...'):
            details = []
            for index, row in edited_df.iterrows():
                ticker = row['Ticker']
                shares = row['Shares']
                
                if shares > 0 and ticker:
                    try:
                        stock = yf.Ticker(ticker)
                        # 嘗試抓取即時價格，若盤後則抓收盤價
                        hist = stock.history(period="1d")
                        if not hist.empty:
                            price = hist['Close'].iloc[-1]
                            val = price * shares
                            total_market_value += val
                            details.append(f"{ticker}: ${price:.2f} x {shares} = ${val:,.0f}")
                    except Exception as e:
                        st.error(f"{ticker} 抓取失敗")
        
        # 顯示個別明細
        with st.expander("查看個股明細"):
            for d in details:
                st.text(d)
        
        # 計算維持率
        st.divider()
        st.metric("目前擔保品總市值", f"${total_market_value:,.0f}")
        
        if total_loan > 0:
            m_ratio = (total_market_value / total_loan) * 100
            
            st.metric("整戶維持率", f"{m_ratio:.2f}%")
            
            if m_ratio < maint_limit:
                st.error(f"🚨 **DANGER**：低於 {maint_limit}% 警戒線！")
                shortfall = total_loan * (maint_limit/100) - total_market_value
                st.markdown(f"**建議補繳金額/增加擔保品： ${shortfall:,.0f}**")
            elif m_ratio < maint_limit + 10:
                st.warning(f"⚠️ **注意**：接近警戒線 ({maint_limit}%)")
            else:
                st.success("✅ 安全範圍")
        else:
            st.info("目前無借款")

# === TAB 3: 簡易記帳 ===
with tab3:
    st.header("📝 快速記帳")
    with st.form("mobile_trade_form"):
        d_date = st.date_input("日期", date.today())
        d_ticker = st.text_input("代號", "009814") 
        col_f1, col_f2 = st.columns(2)
        d_action = col_f1.selectbox("動作", ["Buy", "Sell", "Pledge+"])
        d_total = col_f2.number_input("總金額", step=1000)
        
        if st.form_submit_button("送出"):
            new_row = pd.DataFrame({"Date":[d_date], "Ticker":[d_ticker], "Action":[d_action], "Total_Val":[d_total]})
            old_df = pd.read_csv(FILE_PATH)
            pd.concat([old_df, new_row]).to_csv(FILE_PATH, index=False)
            st.success("已記錄")
            
    if os.path.exists(FILE_PATH):
        st.dataframe(pd.read_csv(FILE_PATH).tail(5), use_container_width=True)