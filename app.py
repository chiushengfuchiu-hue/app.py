import datetime
import os
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# =========================================================
# 1. Google Sheets 串接與讀寫函式 (雲端永久儲存)
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

def load_members():
    if os.path.exists(MEMBERS_FILE):
        try:
            df = pd.read_csv(MEMBERS_FILE)
            if "name" in df.columns:
                return df["name"].dropna().tolist()
            elif not df.empty:
                return df.iloc[:, 0].dropna().tolist()
        except Exception:
            pass
    return INITIAL_MEMBERS

def save_members(members_list):
    pd.DataFrame({"name": members_list}).to_csv(MEMBERS_FILE, index=False)

# 初始化名單檔案
if not os.path.exists(MEMBERS_FILE):
    save_members(INITIAL_MEMBERS)

# 初始化週曆紀錄檔
if not os.path.exists(SCHEDULE_RECORD_FILE):
    pd.DataFrame(columns=["year", "week", "img_path"]).to_csv(SCHEDULE_RECORD_FILE, index=False)

# =========================================================
# 3. 自訂 CSS 樣式 (還原原始經典介面)
# =========================================================
st.markdown("""
    <style>
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1E3A8A;
        text-align: center;
        padding: 10px;
        background: linear-gradient(90deg, #E0E7FF 0%, #EEF2FF 100%);
        border-radius: 12px;
        margin-bottom: 25px;
    }
    .sub-card {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 4. 導覽列與分頁設定
# =========================================================
st.sidebar.image("https://img.icons8.com/isometric/512/open-book.png", width=80)
st.sidebar.title("📖 讀經計畫導覽")
page = st.sidebar.radio(
    "請選擇功能：", 
    ["✍️ 會友打卡簽到", "📊 簽到紀錄與進度表", "📅 週曆與經文對照", "⚙️ 後台系統管理"]
)

members = load_members()

# ---------------------------------------------------------
# 頁面 1：會友打卡簽到 (原始雙欄配置 + 即時預覽)
# ---------------------------------------------------------
if page == "✍️ 會友打卡簽到":
    st.markdown("<div class='main-title'>📖 教會 4 年讀經計畫 - 會友打卡</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("✍️ 填寫打卡資訊")
        selected_member = st.selectbox("請選擇您的名字：", members)
        current_week = st.number_input("請選擇週數 (第 1 ~ 208 週)：", min_value=1, max_value=208, value=1)
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        st.write(f"📅 打卡日期：**{today_str}**")
        note = st.text_input("備註說明（選填）：", "")
        
        if st.button("🚀 完成簽到", type="primary", use_container_width=True):
            if selected_member:
                success = save_attendance(
                    name=selected_member, 
                    week=current_week, 
                    date_str=today_str, 
                    status="已簽到", 
                    note=note
                )
                if success:
                    st.success(f"🎉 感謝上帝！【{selected_member}】 第 {current_week} 週讀經簽到成功！")
                    st.balloons()
                    st.rerun()

    with col2:
        st.subheader("📋 最新雲端簽到動態")
        df_att = load_attendance()
        if not df_att.empty:
            st.dataframe(df_att.tail(10).iloc[::-1], use_container_width=True, height=350)
        else:
            st.info("目前尚無簽到紀錄，或資料讀取中...")

# ---------------------------------------------------------
# 頁面 2：簽到紀錄與進度表 (原始多分頁報表)
# ---------------------------------------------------------
elif page == "📊 簽到紀錄與進度表":
    st.markdown("<div class='main-title'>📊 全體與個人讀經進度分析</div>", unsafe_allow_html=True)
    
    df_att = load_attendance()
    
    tab_summary, tab_personal, tab_matrix = st.tabs(["📈 總覽數據", "🔍 個人歷程", "🧩 全員打卡矩陣圖"])
    
    with tab_summary:
        if not df_att.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("總簽到人次", len(df_att))
            c2.metric("已參與人數", len(df_att["name"].unique()))
            c3.metric("最高讀經週數", df_att["week"].max())
            st.divider()
            st.dataframe(df_att, use_container_width=True)
        else:
            st.info("目前尚無簽到紀錄。")
            
    with tab_personal:
        s_member = st.selectbox("選擇要查詢的會友：", members)
        if not df_att.empty:
            p_df = df_att[df_att["name"] == s_member]
            if not p_df.empty:
                st.write(f"**{s_member}** 的讀經簽到總筆數：{len(p_df)} 筆")
                st.dataframe(p_df, use_container_width=True)
            else:
                st.warning(f"【{s_member}】目前尚未簽到。")
                
    with tab_matrix:
        st.subheader("🧩 34位會友打卡進度圖")
        if not df_att.empty:
            # 建立透視表
            matrix_df = df_att.pivot_table(index="name", columns="week", values="status", aggfunc="first").fillna("❌")
            st.dataframe(matrix_df, use_container_width=True)
        else:
            st.info("暫無數據可製作矩陣圖。")

# ---------------------------------------------------------
# 頁面 3：週曆與經文對照
# ---------------------------------------------------------
elif page == "📅 週曆與經文對照":
    st.markdown("<div class='main-title'>📅 讀經進度對照圖表</div>", unsafe_allow_html=True)
    
    v_week = st.number_input("輸入欲對照的週數：", min_value=1, max_value=208, value=1)
    
    if os.path.exists(SCHEDULE_RECORD_FILE):
        sch_df = pd.read_csv(SCHEDULE_RECORD_FILE)
        matched = sch_df[sch_df["week"] == v_week]
        if not matched.empty:
            img_path = matched.iloc[-1]["img_path"]
            if os.path.exists(img_path):
                st.image(img_path, caption=f"第 {v_week} 週進度圖表", use_container_width=True)
            else:
                st.warning("圖片檔案未找到。")
        else:
            st.info(f"第 {v_week} 週尚未上傳對照圖片。")

# ---------------------------------------------------------
# 頁面 4：後台系統管理
# ---------------------------------------------------------
elif page == "⚙️ 後台系統管理":
    st.markdown("<div class='main-title'>⚙️ 系統後台管理</div>", unsafe_allow_html=True)
    
    pwd = st.text_input("請輸入管理員密碼：", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("密碼正確，歡迎使用後台！")
        
        m_tab1, m_tab2 = st.tabs(["👥 會友名單調整", "🖼️ 上傳週曆進度圖"])
        
        with m_tab1:
            st.write("目前成員名單：", members)
            add_name = st.text_input("輸入新成員姓名：")
            if st.button("新增成員"):
                if add_name and add_name not in members:
                    members.append(add_name)
                    save_members(members)
                    st.success(f"已成功新增 {add_name}")
                    st.rerun()
                    
        with m_tab2:
            up_w = st.number_input("設定上傳週數：", min_value=1, max_value=208, value=1)
            up_file = st.file_uploader("選擇圖片檔案：", type=["png", "jpg", "jpeg"])
            if up_file and st.button("儲存這張圖片"):
                save_path = os.path.join(SCHEDULE_DIR, f"week_{up_w}.png")
                with open(save_path, "wb") as f:
                    f.write(up_file.getbuffer())
                
                sch_df = pd.read_csv(SCHEDULE_RECORD_FILE)
                sch_df = sch_df[sch_df["week"] != up_w]
                new_row = pd.DataFrame([{"year": PLAN_YEAR, "week": up_w, "img_path": save_path}])
                sch_df = pd.concat([sch_df, new_row], ignore_index=True)
                sch_df.to_csv(SCHEDULE_RECORD_FILE, index=False)
                st.success(f"第 {up_w} 週進度圖更換成功！")
                
    elif pwd != "":
        st.error("密碼不正確！")
