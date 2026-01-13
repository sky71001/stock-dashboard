import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
import os

# --- 頁面設定 ---
st.set_page_config(page_title="Invest Command", layout="wide", initial_sidebar_state="expanded")
st.title("🛡️ 投資決策與資產指揮中心 v6.0")

# --- 初始化 Session State ---
if 'total_market_val' not in st.session_state:
    st.session_state['total_market_val'] = 0.0

# --- 檔案處理 (確保檔案存在) ---
TRADE_FILE = 'trade_log.csv'
if not os.path.exists(TRADE_FILE):
    pd.DataFrame(columns=["Date", "Ticker", "Action", "Price", "Units", "Total_Amt", "Note"]).to_csv(TRADE_FILE, index=False)

CAPITAL_FILE = 'capital_log.csv'
if not os.path.exists(CAPITAL_FILE):
    pd.DataFrame(columns=["Date", "Type", "Amount", "Note"]).to_csv(CAPITAL_FILE, index=False)

VIX_RULE_FILE = 'vix_rules.csv'
if not os.path.exists(VIX_RULE_FILE):
    # 預設多層級策略
    pd.DataFrame([
        {"Threshold": 20.0, "Action": "暫停加碼，檢查維持率"},
        {"Threshold": 30.0, "Action": "觸發恐慌：準備現金，若跌破支撐執行減碼"},
        {"Threshold": 40.0, "Action": "極度恐慌：優先保命，變現還款提升維持率至 160%"}
    ]).to_csv(VIX_RULE_FILE, index=False)

# --- A. 側邊介面 (VIX 多層次策略) ---
with st.sidebar:
    st.header("⚙️ 警戒與策略設定")
    
    # 1. VIX 設定 (多層級)
    st.subheader("1. VIX 恐慌對策矩陣")
    st.caption("👇 系統將執行「已觸發」中數值最高的策略")
    
    # 讀取並讓使用者編輯
    vix_rules_df = pd.read_csv(VIX_RULE_FILE)
    edited_vix_rules = st.data_editor(vix_rules_df, num_rows="dynamic", hide_index=True, key="vix_editor")
    
    # 即時儲存
    if not vix_rules_df.equals(edited_vix_rules):
        edited_vix_rules.to_csv(VIX_RULE_FILE, index=False)
        st.success("策略已更新！")
        st.rerun()
    
    st.divider()
    
    # 2. 質押設定
    st.subheader("2. 質押風控")
    maint_alert_val = st.number_input("維持率警戒線 (%)", value=140)

# --- 功能分頁 ---
tab1, tab2, tab3, tab4 = st.tabs(["早安決策", "維持率監控", "交易紀錄(管理)", "資產變化(ROI)"])

# === B. 早安決策介面 ===
with tab1:
    st.header("🌅 晨間操作指引")
    
    col_k1, col_k2 = st.columns(2)
    
    # VIX 自動抓取
    try:
        vix = yf.Ticker("^VIX")
        curr_vix = vix.history(period="1d")['Close'].iloc[-1]
        col_k1.metric("VIX Index", f"{curr_vix:.2f}")
    except:
        curr_vix = 0.0
        col_k1.error("VIX 連線失敗")

    # VIX 策略判定 (Bubble Sort Logic)
    st.subheader("🛡️ VIX 防禦指令")
    
    # 讀取最新規則並由大到小排序
    rules = pd.read_csv(VIX_RULE_FILE).sort_values(by="Threshold", ascending=False)
    triggered_rule = None
    
    # 尋找符合條件的最高閾值
    for index, row in rules.iterrows():
        if curr_vix >= row['Threshold']:
            triggered_rule = row
            break 
    
    if triggered_rule is not None:
        st.error(f"🚨 **警報觸發 (VIX > {triggered_rule['Threshold']})**")
        st.markdown(f"### 執行 SOP：\n> **{triggered_rule['Action']}**")
    else:
        st.success("✅ VIX 數值在安全範圍內 (未觸發任何策略)。")

    st.divider()

    # CBOE & CNN
    st.subheader("📉 加減碼訊號判定")
    col_i1, col_i2 = st.columns(2)
    cboe_val = col_i1.number_input("CBOE Equity P/C Ratio", value=0.60, step=0.01)
    cnn_val = col_i2.number_input("CNN Fear & Greed (P/C)", value=0.70, step=0.01)
    
    signal_triggered = False
    if cnn_val <= 0.62:
        st.error(f"⚠️ **觸發主動防禦 (CNN ≦ 0.62)**：減碼總本金 10% (主策略)。")
        signal_triggered = True
    elif cboe_val <= 0.50:
        st.warning(f"⚠️ **觸發戰術調整 (CBOE ≦ 0.50)**：減碼當日市值 5%。")
        signal_triggered = True
    
    if not signal_triggered:
        st.info("✅ 無觸發減碼訊號。")

# === C. 維持率介面 ===
with tab2:
    st.header("📊 質押與市值監控")
    
    # 1. 負債
    st.subheader("1. 借貸負債")
    loan_input = st.number_input("目前總質押借款金額 (TWD)", value=1000000, step=10000)
    
    # 2. 資產
    st.subheader("2. 抵押資產")
    
    if 'portfolio_df' not in st.session_state:
        st.session_state['portfolio_df'] = pd.DataFrame([
            {"Ticker": "00981.TW", "Units": 10000},
            {"Ticker": "0050.TW", "Units": 0}
        ])

    st.caption("👇 直接修改持倉 (標的, 股數)")
    edited_df = st.data_editor(st.session_state['portfolio_df'], num_rows="dynamic")
    st.session_state['portfolio_df'] = edited_df

    if st.button("🔄 更新股價 & 計算市值 (13:45)"):
        total_val = 0.0
        display_data = []
        
        with st.spinner("連線報價中..."):
            for idx, row in edited_df.iterrows():
                tk = row['Ticker']
                units = row['Units']
                if units > 0 and tk:
                    try:
                        stock = yf.Ticker(tk)
                        price = stock.history(period='1d')['Close'].iloc[-1]
                        val = price * units
                        total_val += val
                        display_data.append({
                            "標的": tk,
                            "現價": round(price, 2),
                            "股數": units,
                            "總市值": round(val, 0)
                        })
                    except:
                        st.error(f"{tk} 抓取失敗")
        
        if display_data:
            st.table(pd.DataFrame(display_data))
            st.session_state['total_market_val'] = total_val
            
            st.divider()
            
            if loan_input > 0:
                m_ratio = (total_val / loan_input) * 100
                st.metric("整戶維持率", f"{m_ratio:.2f}%")
                if m_ratio < maint_alert_val:
                    st.error(f"🚨 維持率過低！需補繳金額： ${(loan_input * maint_alert_val/100 - total_val):,.0f}")
                else:
                    st.success("✅ 維持率安全")
            else:
                st.info("無借款")

# === D. 交易紀錄 (邏輯與 Bug 修復) ===
with tab3:
    st.header("📝 交易資料庫管理")
    
    # 區塊 1: 新增 (Input Form)
    with st.expander("➕ 新增單筆交易", expanded=False):
        with st.form("trade_form"):
            col_d1, col_d2 = st.columns(2)
            d_date = col_d1.date_input("日期", date.today())
            d_ticker = col_d2.text_input("代號", "009814")
            
            col_d3, col_d4, col_d5 = st.columns(3)
            d_action = col_d3.selectbox("動作", ["Buy", "Sell", "Pledge"])
            d_price = col_d4.number_input("成交單價", step=0.1)
            d_units = col_d5.number_input("股數/單位", step=1000)
            
            # 使用者要求：手動輸入總金額 (含手續費等)
            d_total_amt = st.number_input("交易總金額 (台幣)", step=1000, help="請直接填入交割金額，買入或賣出皆填正數即可")
            d_note = st.text_input("備註")
            
            if st.form_submit_button("寫入資料庫"):
                # 重新讀取最新的 CSV (避免覆蓋到編輯過的舊資料)
                current_df = pd.read_csv(TRADE_FILE)
                new_row = pd.DataFrame({
                    "Date": [d_date], "Ticker": [d_ticker], "Action": [d_action],
                    "Price": [d_price], "Units": [d_units], "Total_Amt": [d_total_amt],
                    "Note": [d_note]
                })
                pd.concat([current_df, new_row]).to_csv(TRADE_FILE, index=False)
                st.success("已新增！正在重整頁面...")
                st.rerun() # 強制刷新，解決資料回溯問題

    # 區塊 2: 編輯與刪除 (Data Editor)
    st.subheader("📋 歷史紀錄總表 (可編輯/刪除)")
    
    if os.path.exists(TRADE_FILE):
        # 務必每次重讀
        df_log = pd.read_csv(TRADE_FILE)
        
        edited_log = st.data_editor(
            df_log,
            num_rows="dynamic",
            use_container_width=True,
            key="log_editor_v6" # 更改 Key 以防快取衝突
        )
        
        # 儲存邏輯：只要檢測到 DataFrame 不一樣，就顯示儲存按鈕
        if not df_log.equals(edited_log):
            if st.button("💾 偵測到變動 - 點此確認儲存"):
                edited_log.to_csv(TRADE_FILE, index=False)
                st.success("資料庫已同步更新！")
                st.rerun() # 強制刷新

# === E. 資產變化 (邏輯修正) ===
with tab4:
    st.header("📈 資產績效總覽 (損益法)")
    
    col_e1, col_e2 = st.columns([1, 2])
    
    # E.1 本金管理
    with col_e1:
        st.subheader("💰 本金注入紀錄")
        if os.path.exists(CAPITAL_FILE):
            df_cap = pd.read_csv(CAPITAL_FILE)
            edited_cap = st.data_editor(df_cap, num_rows="dynamic", key="cap_editor")
            if not df_cap.equals(edited_cap):
                edited_cap.to_csv(CAPITAL_FILE, index=False)
                st.rerun()
            
            total_principal = edited_cap['Amount'].sum()
        else:
            total_principal = 0
            
        st.metric("累積總投入本金", f"${total_principal:,.0f}")

    # E.2 報酬率計算 (User Algorithm)
    with col_e2:
        st.subheader("📊 績效儀表板")
        
        # 1. 取得股票市值 (來自 Tab 2)
        live_market_val = st.session_state['total_market_val']
        
        # 2. 計算交易現金流 (Realized Cash Flow)
        trade_df = pd.read_csv(TRADE_FILE)
        # Buy 金額
        total_buy = trade_df[trade_df['Action'] == 'Buy']['Total_Amt'].sum()
        # Sell 金額
        total_sell = trade_df[trade_df['Action'] == 'Sell']['Total_Amt'].sum()
        
        # 淨交易現金流 (通常為負值，代表資金還在股市裡)
        net_trade_flow = total_sell - total_buy
        
        # 3. 計算總獲利金額 (Total Profit)
        # 公式：目前的股票值多少錢 + 已經放口袋的錢(賣出) - 當初投入買股的錢(買入)
        # 這樣就不用管「本金」是不是在股票裡，因為「買入」已經扣掉了成本。
        total_profit = live_market_val + net_trade_flow
        
        # 4. ROI 計算
        roi = 0.0
        if total_principal > 0:
            roi = (total_profit / total_principal) * 100
            
        # --- 顯示 ---
        if live_market_val == 0 and total_buy > 0:
            st.warning("⚠️ 警告：股票市值為 0。請先至「Tab 2」更新股價，否則績效將嚴重低估。")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("1. 股票現值", f"${live_market_val:,.0f}")
        c2.metric("2. 交易淨流 (賣-買)", f"${net_trade_flow:,.0f}", help="賣出總額 - 買入總額")
        c3.metric("3. 總獲利金額", f"${total_profit:,.0f}", delta=None)
        
        st.divider()
        
        final_c1, final_c2 = st.columns(2)
        final_c1.metric("總報酬率 (ROI)", f"{roi:.2f}%", help="總獲利金額 / 累積本金")
        
        # 進度條視覺化 (-100% to +100%)
        progress_val = (roi + 100) / 200
        st.progress(min(max(progress_val, 0.0), 1.0))
        
        st.caption(f"計算邏輯：(股票現值 {live_market_val:,.0f} + 交易淨流 {net_trade_flow:,.0f}) / 總本金 {total_principal:,.0f}")
