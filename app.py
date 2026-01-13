import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 頁面設定 ---
st.set_page_config(page_title="Invest Command Pro", layout="wide", initial_sidebar_state="expanded")
st.title("🛡️ 投資決策中心 V2.0(Cloud DB)")

# --- 連接 Google Sheets (核心函式) ---
# 使用 st.cache_resource 避免每次操作都重新連線
@st.cache_resource
def get_google_sheet_client():
    # 從 Streamlit Secrets 讀取憑證
    # 請確保 Secrets 裡的標題是 [gcp_service_account]
    creds_dict = st.secrets["gcp_service_account"]
    
    # 定義權限範圍
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client

# 這裡請輸入你的 Google Sheet 名稱
SHEET_NAME = "Investment_Database"

# --- 資料讀寫工具函式 ---
def load_data(tab_name, default_df):
    """從 Google Sheet 指定分頁讀取資料，若為空則回傳預設值"""
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_NAME)
        try:
            worksheet = sheet.worksheet(tab_name)
            data = worksheet.get_all_records()
            if data:
                return pd.DataFrame(data)
            else:
                return default_df
        except gspread.WorksheetNotFound:
            # 如果分頁不存在，創建它
            worksheet = sheet.add_worksheet(title=tab_name, rows=100, cols=20)
            worksheet.update([default_df.columns.values.tolist()] + default_df.values.tolist())
            return default_df
    except Exception as e:
        st.error(f"連線錯誤: {e}")
        return default_df

def save_data(tab_name, df):
    """將 DataFrame 寫入 Google Sheet 指定分頁 (覆蓋模式)"""
    try:
        client = get_google_sheet_client()
        sheet = client.open(SHEET_NAME)
        try:
            worksheet = sheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            worksheet = sheet.add_worksheet(title=tab_name, rows=100, cols=20)
        
        # 清空並寫入
        worksheet.clear()
        # gspread 需要將 header 和 values 分開寫入，且 NaN 要轉成空字串
        df_str = df.astype(str) # 轉字串避免 JSON 錯誤
        worksheet.update([df.columns.values.tolist()] + df_str.values.tolist())
        st.toast(f"✅ {tab_name} 已儲存至雲端")
    except Exception as e:
        st.error(f"儲存失敗: {e}")

# --- 初始化 Session State ---
if 'total_loan_amount' not in st.session_state:
    st.session_state['total_loan_amount'] = 0.0

# --- A. 側邊介面 (VIX 策略 - 讀取雲端) ---
with st.sidebar:
    st.header("⚙️ 警戒與策略設定")
    
    # 讀取 Vix Rules
    default_rules = pd.DataFrame([
        {"Threshold": 30.0, "Action": "20%買QQQ/938"},
        {"Threshold": 40.0, "Action": "40%買9815/52"},
        {"Threshold": 60.0, "Action": "50%全轉QLD/663l"}
    ])
    vix_rules_df = load_data("Vix_Rules", default_rules)
    
    st.subheader("1. VIX 恐慌對策")
    edited_vix_rules = st.data_editor(vix_rules_df, num_rows="dynamic", hide_index=True, key="vix_editor")
    
    if st.button("💾 更新策略"):
        save_data("Vix_Rules", edited_vix_rules)
        st.rerun()

    st.divider()
    
    st.subheader("2. 質押風控")
    maint_alert_val = st.number_input("維持率警戒線 (%)", value=140)

# --- 功能分頁 ---
tab1, tab2, tab3, tab4 = st.tabs(["今日決策", "維持率監控", "交易紀錄", "資產績效"])

# === B. 早安決策 ===
with tab1:
    st.header("🌅 今日操作指引")
    col_k1, col_k2 = st.columns(2)
    try:
        vix = yf.Ticker("^VIX")
        curr_vix = vix.history(period="1d")['Close'].iloc[-1]
        col_k1.metric("VIX Index", f"{curr_vix:.2f}")
    except:
        curr_vix = 0.0
        col_k1.error("VIX 連線失敗")

    # VIX 策略判定
    # 確保 Threshold 是數值型別
    vix_rules_df['Threshold'] = pd.to_numeric(vix_rules_df['Threshold'], errors='coerce')
    rules = vix_rules_df.sort_values(by="Threshold", ascending=False)
    
    triggered_rule = None
    for index, row in rules.iterrows():
        if curr_vix >= row['Threshold']:
            triggered_rule = row
            break 
    
    if triggered_rule is not None:
        st.error(f"🚨 **警報觸發 (VIX > {triggered_rule['Threshold']})**\n> SOP: {triggered_rule['Action']}")
    else:
        st.success("✅ VIX 放空發呆")

    st.divider()
    
    col_i1, col_i2 = st.columns(2)
    cboe_val = col_i1.number_input("CBOE Equity P/C Ratio", value=0.66, step=0.01)
    cnn_val = col_i2.number_input("CNN Fear & Greed (P/C)", value=0.71, step=0.01)
    
    signal_triggered = False
    if cnn_val <= 0.62:
        st.error("⚠️ **主動防禦 (CNN ≦ 0.62)**：減碼總本金 10%或清空質押部位。")
        signal_triggered = True
    elif cboe_val <= 0.50:
        st.warning("⚠️ **戰術調整 (CBOE ≦ 0.50)**：減碼市值 5%或質押部位10%。")
        signal_triggered = True
    
    if not signal_triggered:
        st.info("✅ 發呆續抱")

# === C. 維持率監控 (讀寫 Portfolio 分頁) ===
with tab2:
    st.header("📊 質押與市值監控")
    
    # 這裡的 Loan 不需要存雲端嗎？建議也存，這裡先用簡單做法：存在 Portfolio 的第一列或另外處理
    # 為了簡化，我們假設 Loan 每次都要填，或者你可以把 Loan 寫在 Portfolio 的一個特殊欄位
    # 這裡先維持手動輸入 Loan，重點是持倉要存
    
    loan_input = st.number_input("目前總質押借款金額 (TWD)", value=0, step=1000)
    st.session_state['total_loan_amount'] = loan_input
    
    # 讀取雲端持倉
    default_portfolio = pd.DataFrame([{"Ticker": "009814.TW", "Units": 0}, {"Ticker": "0052.TW", "Units": 0}])
    portfolio_df = load_data("Portfolio", default_portfolio)
    
    # 確保型別正確
    portfolio_df['Units'] = pd.to_numeric(portfolio_df['Units'], errors='coerce').fillna(0)
    
    st.caption("👇 修改後請點擊下方「儲存持倉」按鈕")
    edited_portfolio = st.data_editor(portfolio_df, num_rows="dynamic")
    
    col_btn1, col_btn2 = st.columns([1, 4])
    if col_btn1.button("💾 儲存持倉"):
        save_data("Portfolio", edited_portfolio)
        st.rerun()

    if col_btn2.button("🔄 計算維持率 (13:45)"):
        total_val = 0.0
        with st.spinner("計算中..."):
            for idx, row in edited_portfolio.iterrows():
                if float(row['Units']) > 0:
                    try:
                        price = yf.Ticker(row['Ticker']).history(period='1d')['Close'].iloc[-1]
                        total_val += price * float(row['Units'])
                    except: pass
        
        st.divider()
        st.metric("擔保品總市值", f"${total_val:,.0f}")
        if loan_input > 0:
            m_ratio = (total_val / loan_input) * 100
            st.metric("整戶維持率", f"{m_ratio:.2f}%", delta_color="inverse")
            if m_ratio < maint_alert_val:
                st.error(f"🚨 維持率低於 {maint_alert_val}%！")
            else:
                st.success("✅ 安全")

# === D. 交易紀錄 (讀寫 Trade_Log) ===
with tab3:
    st.header("📝 交易資料庫")
    
    # 讀取
    default_trade = pd.DataFrame(columns=["Date", "Ticker", "Action", "Total_Amt", "Note"])
    trade_df = load_data("Trade_Log", default_trade)
    
    # 新增交易區塊
    with st.expander("➕ 新增交易"):
        with st.form("trade_form"):
            col_d1, col_d2 = st.columns(2)
            d_date = col_d1.date_input("日期", date.today())
            d_ticker = col_d2.text_input("代號", "009814")
            col_d3, col_d4 = st.columns(2)
            d_action = col_d3.selectbox("動作", ["Buy", "Sell", "Pledge"])
            d_total_amt = col_d4.number_input("總金額", step=1000)
            d_note = st.text_input("備註")
            
            if st.form_submit_button("新增"):
                new_row = pd.DataFrame([{"Date": str(d_date), "Ticker": d_ticker, "Action": d_action, "Total_Amt": d_total_amt, "Note": d_note}])
                updated_df = pd.concat([trade_df, new_row], ignore_index=True)
                save_data("Trade_Log", updated_df)
                st.success("已上傳雲端")
                st.rerun()

    # 編輯區塊
    st.subheader("📋 歷史紀錄 (編輯後請按儲存)")
    edited_trade_log = st.data_editor(trade_df, num_rows="dynamic", use_container_width=True)
    
    if st.button("💾 儲存交易紀錄變更"):
        save_data("Trade_Log", edited_trade_log)
        st.success("資料庫已更新")
        st.rerun()

# === E. 資產績效 (讀寫 Capital_Log) ===
with tab4:
    st.header("📈 資產績效總覽")
    
    col_main1, col_main2 = st.columns([1, 2])
    
    # 1. 本金管理
    with col_main1:
        st.subheader("💰 累積本金")
        default_cap = pd.DataFrame(columns=["Date", "Type", "Amount", "Note"])
        cap_df = load_data("Capital_Log", default_cap)
        cap_df['Amount'] = pd.to_numeric(cap_df['Amount'], errors='coerce').fillna(0)
        
        edited_cap = st.data_editor(cap_df, num_rows="dynamic", key="cap_editor")
        if st.button("💾 更新本金"):
            save_data("Capital_Log", edited_cap)
            st.rerun()
            
        total_principal = edited_cap['Amount'].sum()
        st.info(f"總投入本金：\n# ${total_principal:,.0f}")

    # 2. 績效計算機 (手動)
    with col_main2:
        st.subheader("📊 績效計算")
        
        with st.container(border=True):
            c1, c2 = st.columns(2)
            manual_stock_val = c1.number_input("1. 股票現值", value=0, step=1000)
            manual_cash = c2.number_input("2. 空閒資金", value=0, step=1000)
            
            current_loan = st.session_state['total_loan_amount']
            st.markdown(f"**3. 質押負債 (From Tab 2):** :red[**-${current_loan:,.0f}**]")
            
            st.divider()

            net_equity = manual_stock_val + manual_cash - current_loan
            profit_loss = net_equity - total_principal
            
            roi = 0.0
            if total_principal > 0:
                roi = (profit_loss / total_principal) * 100

            r1, r2, r3 = st.columns(3)
            r1.metric("淨資產", f"${net_equity:,.0f}")
            r2.metric("未實現損益", f"${profit_loss:,.0f}")
            r3.metric("ROI", f"{roi:.2f}%", delta=profit_loss)
            
            st.progress(min(max((roi + 50) / 100, 0.0), 1.0))
