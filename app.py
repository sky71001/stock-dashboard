import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
import os

# --- 頁面設定 ---
st.set_page_config(page_title="Invest Command", layout="wide", initial_sidebar_state="expanded")
st.title("🛡️ 投資決策與資產指揮中心 v1.0")

# --- 初始化 Session State ---
# 用來跨頁傳遞「負債」資訊，確保 ROI 計算有扣除質押借款
if 'total_loan_amount' not in st.session_state:
    st.session_state['total_loan_amount'] = 0.0

# --- 檔案處理 ---
TRADE_FILE = 'trade_log.csv'
if not os.path.exists(TRADE_FILE):
    pd.DataFrame(columns=["Date", "Ticker", "Action", "Price", "Units", "Total_Amt", "Note"]).to_csv(TRADE_FILE, index=False)

CAPITAL_FILE = 'capital_log.csv'
if not os.path.exists(CAPITAL_FILE):
    pd.DataFrame(columns=["Date", "Type", "Amount", "Note"]).to_csv(CAPITAL_FILE, index=False)

VIX_RULE_FILE = 'vix_rules.csv'
if not os.path.exists(VIX_RULE_FILE):
    pd.DataFrame([
        {"Threshold": 20.0, "Action": "暫停加碼，檢查維持率"},
        {"Threshold": 30.0, "Action": "觸發恐慌：準備現金，若跌破支撐執行減碼"},
        {"Threshold": 40.0, "Action": "極度恐慌：優先保命，變現還款提升維持率至 160%"}
    ]).to_csv(VIX_RULE_FILE, index=False)

# --- A. 側邊介面 ---
with st.sidebar:
    st.header("⚙️ 警戒與策略設定")
    
    # 1. VIX 設定
    st.subheader("1. VIX 恐慌對策")
    vix_rules_df = pd.read_csv(VIX_RULE_FILE)
    edited_vix_rules = st.data_editor(vix_rules_df, num_rows="dynamic", hide_index=True, key="vix_editor")
    if not vix_rules_df.equals(edited_vix_rules):
        edited_vix_rules.to_csv(VIX_RULE_FILE, index=False)
        st.success("已更新")
        st.rerun()
    
    st.divider()
    
    # 2. 質押設定
    st.subheader("2. 質押風控")
    maint_alert_val = st.number_input("維持率警戒線 (%)", value=140)

# --- 功能分頁 ---
tab1, tab2, tab3, tab4 = st.tabs(["早安決策", "維持率監控", "交易紀錄(管理)", "資產績效(手動)"])

# === B. 早安決策介面 ===
with tab1:
    st.header("🌅 晨間操作指引")
    col_k1, col_k2 = st.columns(2)
    try:
        vix = yf.Ticker("^VIX")
        curr_vix = vix.history(period="1d")['Close'].iloc[-1]
        col_k1.metric("VIX Index", f"{curr_vix:.2f}")
    except:
        curr_vix = 0.0
        col_k1.error("VIX 連線失敗")

    # VIX 策略判定
    rules = pd.read_csv(VIX_RULE_FILE).sort_values(by="Threshold", ascending=False)
    triggered_rule = None
    for index, row in rules.iterrows():
        if curr_vix >= row['Threshold']:
            triggered_rule = row
            break 
    
    if triggered_rule is not None:
        st.error(f"🚨 **警報觸發 (VIX > {triggered_rule['Threshold']})**\n> SOP: {triggered_rule['Action']}")
    else:
        st.success("✅ VIX 安全")

    st.divider()

    col_i1, col_i2 = st.columns(2)
    cboe_val = col_i1.number_input("CBOE Equity P/C Ratio", value=0.60, step=0.01)
    cnn_val = col_i2.number_input("CNN Fear & Greed (P/C)", value=0.70, step=0.01)
    
    signal_triggered = False
    if cnn_val <= 0.62:
        st.error("⚠️ **主動防禦 (CNN ≦ 0.62)**：減碼總本金 10%。")
        signal_triggered = True
    elif cboe_val <= 0.50:
        st.warning("⚠️ **戰術調整 (CBOE ≦ 0.50)**：減碼市值 5%。")
        signal_triggered = True
    
    if not signal_triggered:
        st.info("✅ 維持現狀")

# === C. 維持率介面 ===
with tab2:
    st.header("📊 質押與市值監控")
    
    loan_input = st.number_input("目前總質押借款金額 (TWD)", value=1000000, step=10000)
    st.session_state['total_loan_amount'] = loan_input
    
    if 'portfolio_df' not in st.session_state:
        st.session_state['portfolio_df'] = pd.DataFrame([{"Ticker": "00981.TW", "Units": 10000}, {"Ticker": "0050.TW", "Units": 0}])

    edited_df = st.data_editor(st.session_state['portfolio_df'], num_rows="dynamic")
    st.session_state['portfolio_df'] = edited_df

    if st.button("🔄 計算維持率 (13:45)"):
        total_val = 0.0
        with st.spinner("計算中..."):
            for idx, row in edited_df.iterrows():
                if row['Units'] > 0:
                    try:
                        price = yf.Ticker(row['Ticker']).history(period='1d')['Close'].iloc[-1]
                        total_val += price * row['Units']
                    except: pass
        
        st.metric("擔保品總市值", f"${total_val:,.0f}")
        if loan_input > 0:
            m_ratio = (total_val / loan_input) * 100
            st.metric("整戶維持率", f"{m_ratio:.2f}%", delta_color="inverse")
            if m_ratio < maint_alert_val:
                st.error(f"🚨 維持率低於 {maint_alert_val}%！")
            else:
                st.success("✅ 安全")

# === D. 交易紀錄 ===
with tab3:
    st.header("📝 交易資料庫")
    
    with st.expander("➕ 新增交易"):
        with st.form("trade_form"):
            col_d1, col_d2 = st.columns(2)
            d_date = col_d1.date_input("日期", date.today())
            d_ticker = col_d2.text_input("代號", "009814")
            col_d3, col_d4 = st.columns(2)
            d_action = col_d3.selectbox("動作", ["Buy", "Sell", "Pledge"])
            d_total_amt = col_d4.number_input("總金額 (含稅費)", step=1000)
            d_note = st.text_input("備註")
            
            if st.form_submit_button("新增"):
                new_row = pd.DataFrame([{"Date": d_date, "Ticker": d_ticker, "Action": d_action, "Total_Amt": d_total_amt, "Note": d_note}])
                pd.concat([pd.read_csv(TRADE_FILE), new_row]).to_csv(TRADE_FILE, index=False)
                st.rerun()

    if os.path.exists(TRADE_FILE):
        df_log = pd.read_csv(TRADE_FILE)
        edited_log = st.data_editor(df_log, num_rows="dynamic", use_container_width=True, key="log_ed")
        if not df_log.equals(edited_log):
            if st.button("💾 儲存變更"):
                edited_log.to_csv(TRADE_FILE, index=False)
                st.rerun()

# === E. 資產績效 (手動輸入版) ===
with tab4:
    st.header("📈 資產績效總覽 (手動結算)")
    
    col_main1, col_main2 = st.columns([1, 2])
    
    # 1. 總本金管理 (分母)
    with col_main1:
        st.subheader("💰 累積本金 (分母)")
        if os.path.exists(CAPITAL_FILE):
            df_cap = pd.read_csv(CAPITAL_FILE)
            edited_cap = st.data_editor(df_cap, num_rows="dynamic", key="cap_editor")
            if not df_cap.equals(edited_cap):
                edited_cap.to_csv(CAPITAL_FILE, index=False)
                st.rerun()
            total_principal = edited_cap['Amount'].sum()
        else:
            total_principal = 0
        st.info(f"目前總投入本金：\n# ${total_principal:,.0f}")

    # 2. 現值填報 (分子)
    with col_main2:
        st.subheader("📊 績效計算機")
        st.caption("請輸入當下 APP 顯示數值：")
        
        with st.container(border=True):
            c1, c2 = st.columns(2)
            # 輸入欄位
            manual_stock_val = c1.number_input("1. 股票現值 (Market Value)", value=0, step=10000, help="請輸入券商軟體上的證券市值總額")
            manual_cash = c2.number_input("2. 空閒資金 (Idle Cash)", value=0, step=1000, help="交割戶裡的現金餘額")
            
            # 自動帶入負債 (從 Tab 2)
            current_loan = st.session_state['total_loan_amount']
            st.markdown(f"**3. 質押負債 (From Tab 2):** :red[**-${current_loan:,.0f}**]")
            if current_loan == 0:
                st.caption("⚠️ 若有質押，請記得去 Tab 2 輸入借款金額，否則 ROI 會虛高。")

            st.divider()

            # 計算邏輯
            # 淨資產 = 股票 + 現金 - 負債
            net_equity = manual_stock_val + manual_cash - current_loan
            
            # 損益金額
            profit_loss = net_equity - total_principal
            
            # ROI
            roi = 0.0
            if total_principal > 0:
                roi = (profit_loss / total_principal) * 100

            # 顯示結果
            r1, r2, r3 = st.columns(3)
            r1.metric("淨資產總值", f"${net_equity:,.0f}")
            r2.metric("未實現損益", f"${profit_loss:,.0f}", delta_color="normal")
            r3.metric("總報酬率 (ROI)", f"{roi:.2f}%", delta=profit_loss)
            
            # 進度條
            st.progress(min(max((roi + 50) / 100, 0.0), 1.0))
