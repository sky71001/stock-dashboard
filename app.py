import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
import os

# --- 頁面設定 ---
st.set_page_config(page_title="Invest Command", layout="wide", initial_sidebar_state="expanded")
st.title("🛡️ 投資決策與資產指揮中心 v4.0")

# --- 初始化 Session State ---
if 'total_market_val' not in st.session_state:
    st.session_state['total_market_val'] = 0.0
if 'total_loan_amount' not in st.session_state:
    st.session_state['total_loan_amount'] = 0.0

# --- 檔案處理 ---
TRADE_FILE = 'trade_log.csv'
# 確保欄位存在，若無則建立
if not os.path.exists(TRADE_FILE):
    pd.DataFrame(columns=["Date", "Ticker", "Action", "Price", "Units", "Total_Amt", "Note"]).to_csv(TRADE_FILE, index=False)

CAPITAL_FILE = 'capital_log.csv'
if not os.path.exists(CAPITAL_FILE):
    pd.DataFrame(columns=["Date", "Type", "Amount", "Note"]).to_csv(CAPITAL_FILE, index=False)

# --- A. 側邊介面 ---
with st.sidebar:
    st.header("⚙️ 警戒與策略設定")
    
    # 1. VIX 設定
    st.subheader("1. VIX 恐慌指標")
    vix_alert_val = st.number_input("VIX 警戒值 (>)", value=20.0, step=0.1)
    vix_strategy = st.text_area("VIX 觸發時的 SOP", value="1. 暫停加碼\n2. 檢查維持率\n3. 準備現金補繳", height=100)
    
    st.divider()
    
    # 2. 質押設定
    st.subheader("2. 質押風控")
    maint_alert_val = st.number_input("維持率警戒線 (%)", value=140)
    
    st.divider()
    st.info("💡 提示：資料修改後請務必點擊「儲存」按鈕")

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

    if curr_vix > vix_alert_val:
        st.error(f"🚨 **VIX 警報 ({curr_vix:.2f})**")
        st.markdown(f"**執行 SOP：**\n{vix_strategy}")
    else:
        st.success("VIX 情緒穩定")

    st.divider()

    # CBOE & CNN
    st.subheader("📉 加減碼訊號判定")
    col_i1, col_i2 = st.columns(2)
    cboe_val = col_i1.number_input("CBOE Equity P/C Ratio", value=0.60, step=0.01)
    cnn_val = col_i2.number_input("CNN Fear & Greed (P/C)", value=0.70, step=0.01)
    
    CBOE_LIMIT = 0.50
    CNN_LIMIT = 0.62
    
    st.markdown("---")
    st.markdown("### 🤖 系統指令：")
    
    signal_triggered = False
    
    if cnn_val <= CNN_LIMIT:
        st.error(f"⚠️ **觸發主動防禦 (CNN ≦ {CNN_LIMIT})**")
        st.markdown(f"### 執行：減碼「總本金」的 10%")
        st.caption("備註：CNN 與 CBOE 同時觸發時，以此策略為主。")
        signal_triggered = True
    elif cboe_val <= CBOE_LIMIT:
        st.warning(f"⚠️ **觸發戰術調整 (CBOE ≦ {CBOE_LIMIT})**")
        st.markdown(f"### 執行：減碼「當日持有市值」的 5%")
        signal_triggered = True
    
    if not signal_triggered:
        st.info("✅ **無觸發訊號**：維持既有策略與步調。")

# === C. 維持率介面 ===
with tab2:
    st.header("📊 質押與市值監控")
    
    # 1. 負債端
    st.subheader("1. 借貸負債端")
    loan_input = st.number_input("目前總質押借款金額 (TWD)", value=1000000, step=10000)
    st.session_state['total_loan_amount'] = loan_input
    
    # 2. 資產端
    st.subheader("2. 抵押資產端")
    
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
            st.metric("擔保品總市值", f"${total_val:,.0f}")
            
            if loan_input > 0:
                m_ratio = (total_val / loan_input) * 100
                st.metric("整戶維持率", f"{m_ratio:.2f}%")
                
                if m_ratio < maint_alert_val:
                    st.error(f"🚨 **DANGER**：低於警戒線 {maint_alert_val}%！")
                    shortfall = loan_input * (maint_alert_val/100) - total_val
                    st.markdown(f"**需補繳金額： ${shortfall:,.0f}**")
                else:
                    st.success("✅ 維持率安全")

# === D. 交易紀錄 (新增/編輯/刪除) ===
with tab3:
    st.header("📝 交易資料庫管理")
    
    # 區塊 1: 快速新增
    with st.expander("➕ 新增單筆交易", expanded=False):
        with st.form("trade_form"):
            col_d1, col_d2 = st.columns(2)
            d_date = col_d1.date_input("日期", date.today())
            d_ticker = col_d2.text_input("代號", "009814")
            
            col_d3, col_d4, col_d5 = st.columns(3)
            d_action = col_d3.selectbox("動作", ["Buy", "Sell", "Pledge"])
            d_price = col_d4.number_input("成交單價", step=0.1)
            d_units = col_d5.number_input("股數/單位", step=1000)
            
            d_total_amt = d_price * d_units
            st.markdown(f"**總金額： ${d_total_amt:,.0f}**")
            d_note = st.text_input("備註")
            
            if st.form_submit_button("寫入資料庫"):
                new_row = pd.DataFrame({
                    "Date": [d_date], "Ticker": [d_ticker], "Action": [d_action],
                    "Price": [d_price], "Units": [d_units], "Total_Amt": [d_total_amt],
                    "Note": [d_note]
                })
                old_df = pd.read_csv(TRADE_FILE)
                pd.concat([old_df, new_row]).to_csv(TRADE_FILE, index=False)
                st.success("已新增！請重新整理頁面或查看下方表格。")
                st.rerun()

    # 區塊 2: 完整編輯器 (Edit & Delete)
    st.subheader("📋 歷史紀錄總表 (可編輯/刪除)")
    st.info("操作說明：\n1. **編輯**：直接點擊表格內的數值進行修改。\n2. **刪除**：選取該列前面的方框，按鍵盤 `Del` 鍵 (或表格右上角垃圾桶)。\n3. **儲存**：操作完畢後，務必點擊下方「💾 儲存修改」按鈕。")
    
    if os.path.exists(TRADE_FILE):
        df_log = pd.read_csv(TRADE_FILE)
        
        # 使用 Data Editor 讓表格可互動
        edited_log = st.data_editor(
            df_log,
            num_rows="dynamic", # 允許新增與刪除列
            use_container_width=True,
            key="log_editor"
        )
        
        # 儲存按鈕
        if st.button("💾 儲存修改至資料庫"):
            edited_log.to_csv(TRADE_FILE, index=False)
            st.success("✅ 資料庫已更新！")
            st.rerun()

# === E. 資產變化 (ROI) ===
with tab4:
    st.header("📈 資產績效總覽")
    
    col_e1, col_e2 = st.columns([1, 2])
    
    # E.1 本金管理
    with col_e1:
        st.subheader("💰 本金注入紀錄")
        if os.path.exists(CAPITAL_FILE):
            df_cap = pd.read_csv(CAPITAL_FILE)
            # 同樣使用編輯器功能
            edited_cap = st.data_editor(df_cap, num_rows="dynamic", key="cap_editor")
            if st.button("💾 更新本金紀錄"):
                edited_cap.to_csv(CAPITAL_FILE, index=False)
                st.success("已更新")
                st.rerun()
            
            total_principal = edited_cap['Amount'].sum()
        else:
            total_principal = 0
            
        st.metric("累積總投入本金", f"${total_principal:,.0f}")

    # E.2 報酬率計算
    with col_e2:
        st.subheader("📊 績效儀表板")
        
        live_market_val = st.session_state['total_market_val']
        live_loan = st.session_state['total_loan_amount']
        
        if live_market_val == 0:
            st.warning("⚠️ 請先至「Tab 2」點擊更新股價，才能計算最新淨值。")
        else:
            net_equity = live_market_val - live_loan
            roi = 0.0
            if total_principal > 0:
                roi = ((net_equity - total_principal) / total_principal) * 100
            
            c1, c2, c3 = st.columns(3)
            c1.metric("股票總市值", f"${live_market_val:,.0f}")
            c2.metric("扣除負債後淨值", f"${net_equity:,.0f}")
            c3.metric("總報酬率 (ROI)", f"{roi:.2f}%", delta_color="normal")
            
            st.progress(min(max((roi + 50) / 100, 0.0), 1.0))
