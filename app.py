import datetime
import os
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# =========================================================
# 1. Google Sheets 串接設定與讀寫函式
# =========================================================
@st.cache_resource
def get_gsheet_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # 讀取 Secrets 設定
    creds_dict = dict(st.secrets["gcp_service_account"])
    
    # 強效修復私鑰格式問題（處理字面上的 \n 與實際換行）
    if "private_key" in creds_dict:
        pk = creds_dict["private_key"]
        pk = pk.replace("\\n", "\n")  # 處理轉義字元
        # 確保 key 有正確的頭尾標籤
        if not pk.startswith("-----BEGIN PRIVATE KEY-----"):
            pk = "-----BEGIN PRIVATE KEY-----\n" + pk
        if not pk.endswith("-----END PRIVATE KEY-----"):
            pk = pk + "\n-----END PRIVATE KEY-----"
        creds_dict["private_key"] = pk.strip()
        
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    return gspread.authorize(creds)

def load_attendance():
    """從 Google 試算表讀取所有簽到紀錄"""
    try:
        client = get_gsheet_client()
        sheet_name = st.secrets.get("spreadsheet_name", "Church_Attendance")
        sheet = client.open(sheet_name).sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        return pd.DataFrame(columns=["name", "week", "date", "status", "note"])

def save_attendance(name, week, date_str, status="已簽到", note=""):
    """寫入一筆簽到紀錄至 Google 試算表"""
    try:
        client = get_gsheet_client()
        sheet_name = st.secrets.get("spreadsheet_name", "Church_Attendance")
        sheet = client.open(sheet_name).sheet1
        sheet.append_row([name, week, date_str, status, note])
        return True
    except Exception as e:
        st.error(f"寫入 Google 試算表失敗: {e}")
        return False

# =========================================================
# 2. 頁面配置與基本設定
# =========================================================
st.set_page_config(
    page_title="教會4年讀經計畫簽到系統", 
    page_icon="📖", 
    layout="wide"
)

MEMBERS_FILE = "church_members.csv"
VERSES_FILE = "verses.csv"
SCHEDULE_RECORD_FILE = "schedule_records.csv"
SCHEDULE_DIR = "schedules_img"
ADMIN_PASSWORD = "biblecheckin"
PLAN_YEAR = 2

os.makedirs(SCHEDULE_DIR, exist_ok=True)

# 34 位真實名單底稿
INITIAL_MEMBERS = [
    "周寶燕", "曾笑", "黃然玉", "吳妃玉", "楊湯美麗",
    "翁淑美", "石美莎", "鄭麗蘭", "鄭富美", "李驚芳",
    "趙文崇", "李應昌", "賴健文", "林春妙", "邱文雀",
    "梁垠盤", "陳宜宏", "郭彩梅", "林春桃", "鳳姐",
    "黃敏生", "吳秀卉", "陳安俐", "程乃珍", "蕭慧麗",
    "蔡慧俐", "林雅谷", "李俊修", "林淑惠", "盧正亮",
    "林雅音", "劉淑珠", "葉雅雲", "趙文川"
]

# =========================================================
# 3. 主畫面 logic (打卡與即時紀錄)
# =========================================================
st.title("📖 教會 4 年讀經計畫簽到系統")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("✍️ 會友打卡")
    selected_member = st.selectbox("請選擇您的名字：", INITIAL_MEMBERS)
    current_week = st.number_input("請選擇週數：", min_value=1, max_value=208, value=1)
    today_str = datetime.date.today().strftime("%Y-%m-%d")

    if st.button("確認簽到", type="primary", use_container_width=True):
        if selected_member:
            success = save_attendance(
                name=selected_member, 
                week=current_week, 
                date_str=today_str,
                status="已簽到",
                note=""
            )
            if success:
                st.success(f"🎉 {selected_member} 第 {current_week} 週簽到成功！")
                st.rerun()

with col2:
    st.subheader("📊 最新簽到紀錄（Google 試算表同步）")
    # 直接從 Google Sheets 載入資料
    df_attendance = load_attendance()
    
    if not df_attendance.empty:
        st.dataframe(df_attendance, use_container_width=True, height=400)
    else:
        st.info("目前尚無簽到紀錄，或 Google 試算表為空。")
