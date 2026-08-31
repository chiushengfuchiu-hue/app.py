import io
import os
import datetime
import docx
import streamlit as st
import pandas as pd
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# ==========================================
# 0. 基本設定與常數
# ==========================================
st.set_page_config(page_title="讀經簽到與進度系統", page_icon="📖", layout="centered")

ATTENDANCE_FILE = "attendance_records.csv"
GUIDE_FOLDER_ID = "1-RkVxCZy9wS_2X6Huw5p2mWhv1b6l0HM"

# 所有成員名單
MEMBERS = [
    "周寶燕", "曾笑", "黃然玉", "吳妃玉", "楊游美麗", 
    "翁淑美", "石美莎", "單麗蘭", "鄭富美", "李鶯芳", 
    "趙文崇", "李應昌", "賴健文", "林春妙", "邱文雀", 
    "梁垠盤", "陳宜宏", "郭彩梅", "林春桃", "鳳姐", 
    "黃敏生", "吳秀卉", "陳安俐", "程乃珍", "蕭慧麗", 
    "蔡慧俐", "林雅谷", "李俊修", "林淑惠", "盧正亮", 
    "翁春祝", "劉淑珠", "葉雅雲", "林雅音", "趙文川",
    "邱聖富", "林秀鳳", "陳文智"
]

# ==========================================
# 1. API 與資料讀取函數
# ==========================================
@st.cache_resource
def get_drive_service():
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    if "private_key" in creds_dict:
        pk = creds_dict["private_key"].replace("\\n", "\n")
        if not pk.startswith("-----BEGIN PRIVATE KEY-----"):
            pk = "-----BEGIN PRIVATE KEY-----\n" + pk
        if not pk.endswith("-----END PRIVATE KEY-----"):
            pk = pk + "\n-----END PRIVATE KEY-----"
        creds_dict["private_key"] = pk.strip()

    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return build("drive", "v3", credentials=creds)

@st.cache_data(ttl=3600)
def fetch_docx_content(week_num):
    """從雲端硬碟讀取 Word 導讀檔案內容"""
    try:
        service = get_drive_service()
        query = f"'{GUIDE_FOLDER_ID}' in parents and name contains '{week_num}' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get("files", [])
        
        target_file = None
        for f in files:
            if f["name"].startswith(str(week_num)):
                target_file = f
                break
                
        if not target_file:
            return None

        request = service.files().get_media(fileId=target_file["id"])
        file_bytes = io.BytesIO(request.execute())
        
        doc = docx.Document(file_bytes)
        full_text = [p.text for p in doc.paragraphs if p.text.strip() != ""]
        return "\n\n".join(full_text)
    except Exception as e:
        return f"⚠️ 讀取導讀檔案時發生錯誤：{e}"

def load_attendance_data():
    """讀取簽到資料"""
    if os.path.exists(ATTENDANCE_FILE):
        return pd.read_csv(ATTENDANCE_FILE, dtype=str)
    else:
        return pd.DataFrame(columns=["week_key", "member_name", "timestamp"])

def add_batch_records(records_list):
    """批次寫入簽到紀錄（支援自動補齊過往未簽週數）"""
    df = load_attendance_data()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    new_rows = []
    for week_key, member_name in records_list:
        exists = not df[(df["week_key"] == week_key) & (df["member_name"] == member_name)].empty
        if not exists:
            new_rows.append({"week_key": week_key, "member_name": member_name, "timestamp": now_str})
            
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df = pd.concat([df, df_new], ignore_index=True)
        df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8-sig")

# ==========================================
# 2. 簽到二次確認彈窗 (Dialog)
# ==========================================
@st.dialog("簽到確認")
def confirm_checkin_dialog(member_name, week_display, week_key, missing_weeks):
    st.markdown(f"👉 確定要為 **{member_name}** 辦理 **{week_display}** 的簽到嗎？")
    
    if missing_weeks:
        st.info(f"💡 系統將一併自動為您補簽過往未簽到的 **{len(missing_weeks)}** 週進度！")
        
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 確定簽到", type="primary", use_container_width=True):
            records_to_add = [(week_key, member_name)]
            for m_item in missing_weeks:
                records_to_add.append((m_item["key"], member_name))
            
            add_batch_records(records_to_add)
            st.toast("🎉 簽到成功！")
            st.rerun()
            
    with col2:
        if st.button("❌ 取消", type="secondary", use_container_width=True):
            st.rerun()

# ==========================================
# 3. 頁面主導覽結構
# ==========================================
st.title("📖 讀經進度與簽到系統")

page = st.sidebar.selectbox("請選擇功能分頁：", ["👤 會友個人簽到專頁", "📊 進度查詢與導讀閱覽"])

df_attendance = load_attendance_data()

# ==========================================
# 分頁一：會友個人簽到專頁
# ==========================================
if page == "👤 會友個人簽到專頁":
    st.sidebar.markdown("---")
    member_name = st.selectbox("請選擇您的姓名：", MEMBERS)
    
    st.markdown(f"## 👤 {member_name} 的讀經專頁")
    
    current_week_num = 36
    current_week_key = f"Y2-W{current_week_num:02d}"
    current_week_display = f"第 2 年 - 第 {current_week_num} 週"
    
    st.markdown(f"### 📍 【本週進度】{current_week_display}")
    
    is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == member_name)].empty
    
    missing_weeks_info = []
    for w in range(1, current_week_num):
        w_key = f"Y2-W{w:02d}"
        checked = not df_attendance[(df_attendance["week_key"] == w_key) & (df_attendance["member_name"] == member_name)].empty
        if not checked:
            missing_weeks_info.append({"key": w_key, "display": f"W{w:02d}"})

    if is_signed:
        st.success(f"🎉 **{member_name}**，您已完成本週讀經進度，願主保守力上加力恩上加恩！")
    else:
        if st.button(f"🟢 若完成【{current_week_display}】請按此簽到", type="primary", use_container_width=True):
            confirm_checkin_dialog(member_name, current_week_display, current_week_key, missing_weeks_info)

# ==========================================
# 分頁二：進度查詢與導讀閱覽
# ==========================================
elif page == "📊 進度查詢與導讀閱覽":
    st.markdown("## 📊 讀經進度查詢與每週導讀")
    
    selected_week_num = st.selectbox("請選擇欲查詢的週數：", list(range(1, 44)), index=31)
    selected_week_key = f"Y2-W{selected_week_num:02d}"
    
    st.markdown(f"### 📖 第 {selected_week_num} 週 讀經導讀內容")
    
    view_mode = st.radio(
        "請選擇檢視模式：",
        ["📜 全文導讀", "📅 按天切換閱讀 (Day 1 - Day 7)"],
        horizontal=True
    )

    with st.spinner("正在從雲端硬碟讀取導讀文件中..."):
        doc_content = fetch_docx_content(selected_week_num)

    if not doc_content:
        st.info(f"💡 雲端硬碟中尚無第 {selected_week_num} 週的導讀 Word 文件。")
    else:
        display_text = doc_content
        
        if view_mode == "📅 按天切換閱讀 (Day 1 - Day 7)":
            selected_day = st.selectbox(
                "選擇天數：",
                [f"第 {i} 天" for i in range(1, 8)]
            )
            st.caption("💡 提示：導讀 Word 檔為全週彙整，您也可以切換至「全文導讀」透過滾輪流暢瀏覽完整內容。")

        st.markdown(
            f"""
            <div style="
                height: 400px; 
                overflow-y: scroll; 
                background-color: #f8f9fa; 
                padding: 18px; 
                border-radius: 8px; 
                border: 1px solid #d0d0d0;
                line-height: 1.8;
                font-size: 15px;
                color: #2c3e50;
                white-space: pre-wrap;
            ">
                {display_text}
            </div>
            """,
            unsafe_allow_html=True
        )
