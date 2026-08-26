import datetime
import os
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# =========================================================
# 1. Google Sheets 串接與讀寫函式 (已自動修正私鑰格式)
# =========================================================
@st.cache_resource
def get_gsheet_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        pk = creds_dict["private_key"]
        pk = pk.replace("\\n", "\n")
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
# 2. 系統基礎設定與靜態檔案路徑
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

# 初始化名單檔案
if not os.path.exists(MEMBERS_FILE):
    pd.DataFrame({"name": INITIAL_MEMBERS}).to_csv(MEMBERS_FILE, index=False)

# 初始化週曆紀錄檔
if not os.path.exists(SCHEDULE_RECORD_FILE):
    pd.DataFrame(columns=["year", "week", "img_path"]).to_csv(SCHEDULE_RECORD_FILE, index=False)

def load_members():
    if os.path.exists(MEMBERS_FILE):
        return pd.read_csv(MEMBERS_FILE)["name"].tolist()
    return INITIAL_MEMBERS

def save_members(members_list):
    pd.DataFrame({"name": members_list}).to_csv(MEMBERS_FILE, index=False)

# =========================================================
# 3. 自訂 CSS 樣式與視覺包裝
# =========================================================
st.markdown("""
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 20px;
    }
    .stButton>button {
        background-color: #2563EB;
        color: white;
        border-radius: 8px;
        font-weight: bold;
    }
    .metric-card {
        background-color: #F3F4F6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 4. 側邊欄與頁面分頁導覽
# =========================================================
st.sidebar.title("📖 讀經計畫導覽")
page = st.sidebar.radio(
    "前往頁面：", 
    ["✍️ 會友打卡簽到", "📊 簽到紀錄與進度表", "📅 週曆與經文對照", "⚙️ 後台系統管理"]
)

members = load_members()

# ---------------------------------------------------------
# 頁面 1：會友打卡簽到
# ---------------------------------------------------------
if page == "✍️ 會友打卡簽到":
    st.markdown("<div class='main-header'>📖 教會 4 年讀經計畫 - 會友簽到</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("✍️ 打卡資料填寫")
        selected_member = st.selectbox("請選擇您的姓名：", members)
        current_week = st.number_input("請選擇讀經週數 (第 1 ~ 208 週)：", min_value=1, max_value=208, value=1)
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        note = st.text_input("備註（可不填）：", "")
        
        if st.button("🚀 確認簽到", use_container_width=True):
            if selected_member:
                success = save_attendance(
                    name=selected_member, 
                    week=current_week, 
                    date_str=today_str, 
                    status="已簽到", 
                    note=note
                )
                if success:
                    st.success(f"🎉 【{selected_member}】 第 {current_week} 週讀經簽到成功！")
                    st.balloons()
                    st.rerun()

    with col2:
        st.subheader("📋 最新簽到動態")
        df_att = load_attendance()
        if not df_att.empty:
            recent_df = df_att.tail(10).iloc[::-1]
            st.dataframe(recent_df, use_container_width=True)
        else:
            st.info("目前尚無簽到紀錄。")

# ---------------------------------------------------------
# 頁面 2：簽到紀錄與進度表
# ---------------------------------------------------------
elif page == "📊 簽到紀錄與進度表":
    st.markdown("<div class='main-header'>📊 個人與全體讀經進度總覽</div>", unsafe_allow_html=True)
    
    df_att = load_attendance()
    
    if df_att.empty:
        st.warning("目前尚無任何簽到紀錄，無法顯示統計報表。")
    else:
        st.subheader("📈 總覽指標")
        c1, c2, c3 = st.columns(3)
        c1.metric("已總簽到人次", len(df_att))
        c2.metric("參與會友總數", len(df_att["name"].unique()))
        c3.metric("目前最高簽到週數", df_att["week"].max())
        
        st.divider()
        
        st.subheader("🔍 會友個人歷程查詢")
        search_member = st.selectbox("選擇會友姓名：", members)
        member_df = df_att[df_att["name"] == search_member]
        
        if not member_df.empty:
            st.write(f"【{search_member}】的已簽到週數紀錄：")
            st.dataframe(member_df, use_container_width=True)
        else:
            st.info(f"【{search_member}】目前尚未有簽到紀錄。")
            
        st.divider()
        st.subheader("📄 完整雲端數據庫對照（Google Sheets）")
        st.dataframe(df_att, use_container_width=True, height=400)

# ---------------------------------------------------------
# 頁面 3：週曆與經文對照
# ---------------------------------------------------------
elif page == "📅 週曆與經文對照":
    st.markdown("<div class='main-header'>📅 讀經週曆與經文對照</div>", unsafe_allow_header=True if False else True)
    
    view_week = st.number_input("查看目標週數：", min_value=1, max_value=208, value=1)
    
    st.info(f"📖 第 {view_week} 週讀經進度規劃")
    
    if os.path.exists(SCHEDULE_RECORD_FILE):
        sch_df = pd.read_csv(SCHEDULE_RECORD_FILE)
        matched = sch_df[sch_df["week"] == view_week]
        if not matched.empty:
            img_path = matched.iloc[-1]["img_path"]
            if os.path.exists(img_path):
                st.image(img_path, caption=f"第 {view_week} 週對照圖表", use_container_width=True)
            else:
                st.warning("找不到對應的週曆圖檔。")
        else:
            st.info("管理員尚未上傳該週的週曆對照圖。")

# ---------------------------------------------------------
# 頁面 4：後台系統管理
# ---------------------------------------------------------
elif page == "⚙️ 後台系統管理":
    st.markdown("<div class='main-header'>⚙️ 後台管理系統</div>", unsafe_allow_html=True)
    
    pwd = st.text_input("請輸入管理員密碼：", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("身分驗證成功！")
        
        tab1, tab2, tab3 = st.tabs(["👥 會友名單管理", "🖼️ 上傳週曆圖檔", "📊 數據備份與清理"])
        
        with tab1:
            st.subheader("新增 / 刪除會友名單")
            curr_members = load_members()
            st.write("目前名單（共", len(curr_members), "位）：")
            st.write(", ".join(curr_members))
            
            new_m = st.text_input("新增會友姓名：")
            if st.button("新增會友"):
                if new_m and new_m not in curr_members:
                    curr_members.append(new_m)
                    save_members(curr_members)
                    st.success(f"已成功新增 {new_m}")
                    st.rerun()
                    
        with tab2:
            st.subheader("上傳該週進度對照圖")
            up_week = st.number_input("設定週數：", min_value=1, max_value=208, value=1)
            uploaded_file = st.file_uploader("選擇進度圖片：", type=["png", "jpg", "jpeg"])
            
            if uploaded_file and st.button("儲存圖片"):
                file_path = os.path.join(SCHEDULE_DIR, f"week_{up_week}.png")
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                sch_df = pd.read_csv(SCHEDULE_RECORD_FILE)
                sch_df = sch_df[sch_df["week"] != up_week]
                new_row = pd.DataFrame([{"year": PLAN_YEAR, "week": up_week, "img_path": file_path}])
                sch_df = pd.concat([sch_df, new_row], ignore_index=False)
                sch_df.to_csv(SCHEDULE_RECORD_FILE, index=False)
                st.success(f"第 {up_week} 週圖片已更新成功！")
                
        with tab3:
            st.subheader("雲端資料狀態")
            st.write("目前所有簽到數據已即時同步保存於 Google 試算表（`Church_Attendance`）。")
            df_curr = load_attendance()
            st.metric("雲端總筆數", len(df_curr))
            
    elif pwd != "":
        st.error("密碼錯誤，請重新輸入！")
