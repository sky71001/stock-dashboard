import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
import os

# --- 頁面設定 ---
st.set_page_config(page_title="Invest Command", layout="wide", initial_sidebar_state="expanded")
st.title("🛡️ 投資決策與資產指揮中心 v5.0")

# --- 初始化 Session State ---
if 'total_market_val' not in st.session_state:
    st.session_state['total_market_val'] = 0.0
if 'total_loan_amount' not in st.session_state:
    st.session_state['total_loan_amount'] = 0.0

# --- 檔案處理 (資料庫) ---
TRADE_FILE = 'trade_log.csv'
if not os.path.exists(TRADE_FILE):
    pd.DataFrame(columns=["Date", "Ticker", "Action", "Price", "Units", "Total_Amt", "Note"]).to_csv(TRADE_FILE, index=False)

CAPITAL_FILE = 'capital_log.csv'
if not os.path.exists(CAPITAL_FILE):
    pd.DataFrame(columns=["Date", "Type", "Amount", "Note"]).to_csv(CAPITAL_FILE, index=False)

# VIX 規則檔
VIX_RULE_FILE = 'vix_rules.csv'
if not os.path.exists(VIX_RULE_FILE):
    # 預設規則
    pd.DataFrame([
        {"Threshold": 20.0, "Action": "暫停加碼，檢查維持率"},
        {"Threshold": 30.0, "Action": "準備現金，若跌破支撐執行減碼"},
        {"Threshold": 45.0, "Action": "市場極度恐慌，分批抄底或變現救維持率"}
    ]).to_csv(VIX_RULE_FILE, index=False)

# --- A. 側邊介面 (VIX 多層次設定) ---
with st.sidebar:
    st.header("⚙️ 警戒與策略設定")
    
    # 1. VIX 設定 (動態表格)
    st.subheader("1. VIX 恐慌對策矩陣")
    st.caption("設定不同 VIX 數值對應的 SOP (數值越大優先級越高)")
    
    vix_rules_df = pd.read_csv(VIX_RULE_FILE)
    edited_vix_rules = st.data_editor(vix_rules_df, num_rows="dynamic", hide_index=True, key="vix_editor")
    
    # 自動儲存 VIX 規則
    if not vix_rules_df.equals(edited_vix_rules):
        edited_vix_rules.to_csv(VIX_RULE_FILE, index=False)
        st.success("VIX 規則已更新")
    
    st.divider()
    
    # 2. 質押設定
    st.subheader("2. 質押風控")
    maint_alert_val = st.number_input("維持率警戒線 (%)", value=140)
    
    st.divider()
    st.info("💡 提示：若修改了 VIX 規則或交易紀錄，請確認資料已儲存。")

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

    # VIX 策略判定邏輯 (取觸發的最高值)
    st.subheader("🛡️ VIX 防禦指令")
    
    # 讀取規則並排序 (由大到小)
    rules = pd.read_csv(VIX_RULE_FILE).sort_values(by="Threshold", ascending=False)
    triggered_rule = None
    
    for index, row in rules.iterrows():
        if curr_vix >= row['Threshold']:
            triggered_rule = row
            break # 找到最高滿足條件就停止
    
    if triggered_rule is not None:
        st.error(f"🚨 **警報觸發 (VIX > {triggered_rule['Threshold']})**")
        st.markdown(f"### 執行 SOP：\n> **{triggered_rule['Action']}**")
    else:
        st.success("✅ VIX 數值在安全範圍內，依正常計畫執行。")

    st.divider()

    # CBOE & CNN (保持原樣)
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
    st.session_state['total_loan_amount'] = loan_input
    
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

# === D. 交易紀錄 (邏輯修正版) ===
with tab3:
    st.header("📝 交易資料庫管理")
    
    # 邏輯修正：為了防止「刪除後新增」導致資料回溯，我們明確分開「新增區」與「編輯區」
    # 並且強制在操作後 Rerun 讀取最新 CSV
    
    # --- 新增區塊 ---
    with st.expander("➕ 新增單筆交易 (請自行輸入總金額)", expanded=False):
        with st.form("trade_form"):
            col_d1, col_d2 = st.columns(2)
            d_date = col_d1.date_input("日期", date.today())
            d_ticker = col_d2.text_input("代號", "009814")
            
            col_d3, col_d4, col_d5 = st.columns(3)
            d_action = col_d3.selectbox("動作", ["Buy", "Sell", "Pledge"])
            d_price = col_d4.number_input("成交單價", step=0.1)
            d_units = col_d5.number_input("股數/單位", step=1000)
            
            # 使用者要求：手動輸入總金額
            d_total_amt = st.number_input("交易總金額 (含手續費/稅)", step=1000, help="買入請填正數，賣出請填正數，系統會自動判斷")
            d_note = st.text_input("備註")
            
            if st.form_submit_button("寫入資料庫"):
                # 重新讀取最新的 CSV (確保包含剛才可能刪除的變更)
                current_df = pd.read_csv(TRADE_FILE)
                new_row = pd.DataFrame({
                    "Date": [d_date], "Ticker": [d_ticker], "Action": [d_action],
                    "Price": [d_price], "Units": [d_units], "Total_Amt": [d_total_amt],
                    "Note": [d_note]
                })
                pd.concat([current_df, new_row]).to_csv(TRADE_FILE, index=False)
                st.success("已新增！頁面將自動刷新。")
                st.rerun() # 強制刷新

    # --- 編輯與刪除區塊 ---
    st.subheader("📋 歷史紀錄總表 (可編輯/刪除)")
    
    if os.path.exists(TRADE_FILE):
        # 這裡一定要讀取最新的
        df_log = pd.read_csv(TRADE_FILE)
        
        # Data Editor
        edited_log = st.data_editor(
            df_log,
            num_rows="dynamic",
            use_container_width=True,
            key="log_editor"
        )
        
        # 偵測是否有變動
        if not df_log.equals(edited_log):
            if st.button("💾 偵測到變動 - 點此確認儲存 (Save)"):
                edited_log.to_csv(TRADE_FILE, index=False)
                st.success("資料庫已同步更新！")
                st.rerun() # 強制刷新以確保一致性

# === E. 資產變化 (現金流修正版) ===
with tab4:
    st.header("📈 資產績效總覽 (淨值法)")
    
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

    # E.2 報酬率計算 (邏輯重構)
    with col_e2:
        st.subheader("📊 績效儀表板")
        
        # 1. 取得股票市值 (來自 Tab 2)
        live_market_val = st.session_state['total_market_val']
        
        # 2. 取得負債 (來自 Tab 2)
        live_loan = st.session_state['total_loan_amount']

        # 3. 計算「現金餘額」(Cash Balance)
        # 邏輯：現金餘額 = 總本金 + (賣出總額 - 買入總額)
        # 假設 Pledge 動作不影響現金流(除非你定義為借款入金)，這裡先只算 Buy/Sell
        trade_df = pd.read_csv(TRADE_FILE)
        
        total_buy = trade_df[trade_df['Action'] == 'Buy']['Total_Amt'].sum()
        total_sell = trade_df[trade_df['Action'] == 'Sell']['Total_Amt'].sum()
        
        # 試算現金餘額 (假設本金全部先變現金)
        # 意義：還留在帳戶裡的現金 (包含未投入的本金 + 賣股回來的錢 - 買股花掉的錢)
        cash_balance = total_principal + total_sell - total_buy
        
        # 4. 計算總權益 (Net Equity)
        # 總權益 = 股票市值 + 現金餘額 - 質押負債
        net_equity = live_market_val + cash_balance - live_loan
        
        # 5. ROI 計算
        roi = 0.0
        if total_principal > 0:
            roi = ((net_equity - total_principal) / total_principal) * 100
            
        # --- 顯示 ---
        if live_market_val == 0 and total_buy > 0:
            st.warning("⚠️ 警告：股票市值為 0。請先至「Tab 2」更新股價，否則績效不準確。")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("1. 股票市值", f"${live_market_val:,.0f}")
        c2.metric("2. 帳上現金 (推估)", f"${cash_balance:,.0f}", help="總本金 - 買入 + 賣出")
        c3.metric("3. 質押負債", f"-${live_loan:,.0f}")
        
        st.divider()
        
        final_c1, final_c2 = st.columns(2)
        final_c1.metric("淨資產總值 (Net Equity)", f"${net_equity:,.0f}", help="市值 + 現金 - 負債")
        final_c2.metric("總報酬率 (ROI)", f"{roi:.2f}%", delta_color="normal")

        st.caption(f"計算公式：(淨資產 {net_equity:,.0f} - 總本金 {total_principal:,.0f}) / 總本金")
