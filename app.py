import streamlit as st
import pandas as pd
import datetime
import os
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. 檔案與基礎設定
# ==========================================
MEMBERS_FILE = "church_members.csv"
VERSES_FILE = "verses.csv"
SCHEDULE_RECORD_FILE = "schedule_records.csv"
ATTENDANCE_FILE = "attendance_records.csv"  # 本地簽到資料庫
SCHEDULE_DIR = "schedules_img"
ADMIN_PASSWORD = "610113"

PLAN_YEAR = 2 

os.makedirs(SCHEDULE_DIR, exist_ok=True)

# 已更新最新 36 位會友名單（含 翁春祝、邱聖富）
INITIAL_MEMBERS = [
    "周寶燕", "曾笑", "黃然玉", "吳妃玉", "楊游美麗", 
    "翁淑美", "石美莎", "單麗蘭", "鄭富美", "李鶯芳", 
    "趙文崇", "李應昌", "賴健文", "林春妙", "邱文雀", 
    "梁垠盤", "陳宜宏", "郭彩梅", "林春桃", "鳳姐", 
    "黃敏生", "吳秀卉", "陳安俐", "程乃珍", "蕭慧麗", 
    "蔡慧俐", "林雅谷", "李俊修", "林淑惠", "盧正亮", 
    "翁春祝", "劉淑珠", "葉雅雲", "林雅音", "趙文川",
    "邱聖富"
]

st.set_page_config(page_title="教會4年讀經計畫簽到系統", page_icon="📖", layout="wide")

# ==========================================
# 2. 資料庫與 API 處理邏輯
# ==========================================
def load_attendance():
    """載入簽到紀錄"""
    if os.path.exists(ATTENDANCE_FILE):
        try:
            df = pd.read_csv(ATTENDANCE_FILE, dtype=str)
            for col in ["week_key", "member_name", "timestamp"]:
                if col not in df.columns:
                    df[col] = ""
                else:
                    df[col] = df[col].astype(str).str.strip()
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=["week_key", "member_name", "timestamp"])

def save_attendance(df):
    """儲存簽到紀錄至本地"""
    df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8-sig")

def sync_to_gsheet_async(new_rows_list):
    """背景備份寫入 Google Sheets"""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict:
            pk = creds_dict["private_key"].replace("\\n", "\n")
            if not pk.startswith("-----BEGIN PRIVATE KEY-----"):
                pk = "-----BEGIN PRIVATE KEY-----\n" + pk
            if not pk.endswith("-----END PRIVATE KEY-----"):
                pk = pk + "\n-----END PRIVATE KEY-----"
            creds_dict["private_key"] = pk.strip()
            
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet_name = st.secrets.get("spreadsheet_name", "Church_Attendance")
        sheet = client.open(sheet_name).sheet1
        sheet.append_rows(new_rows_list)
    except Exception:
        pass

def add_single_record(week_key, member_name):
    """新增單筆簽到"""
    df = load_attendance()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    week_key = str(week_key).strip()
    member_name = str(member_name).strip()
    
    match = df[(df["week_key"] == week_key) & (df["member_name"] == member_name)]
    if match.empty:
        new_row = pd.DataFrame([{"week_key": week_key, "member_name": member_name, "timestamp": now_str}])
        df = pd.concat([df, new_row], ignore_index=True)
        save_attendance(df)
        sync_to_gsheet_async([[week_key, member_name, now_str]])
    return True

def load_members():
    """優先載入 church_members.csv，若無檔案才建立預設值"""
    if os.path.exists(MEMBERS_FILE):
        try:
            df_m = pd.read_csv(MEMBERS_FILE)
            col_name = "member_name" if "member_name" in df_m.columns else df_m.columns[0]
            current_names = df_m[col_name].dropna().astype(str).str.strip().tolist()
            if current_names:
                return pd.DataFrame({"member_name": current_names})
        except Exception:
            pass

    # 若尚未產生檔案，則自動以 INITIAL_MEMBERS 初始化
    df_m = pd.DataFrame({"member_name": INITIAL_MEMBERS})
    df_m.to_csv(MEMBERS_FILE, index=False, encoding="utf-8-sig")
    return df_m

def save_members(members_list):
    """將後台修改後的名單強制覆蓋寫入 CSV"""
    pd.DataFrame({"member_name": members_list}).to_csv(MEMBERS_FILE, index=False, encoding="utf-8-sig")

def get_weekly_verse(week_num):
    fallback = {"verse": "「你的話是我腳前的燈，是我路上的光。」", "ref": "詩篇 119:105"}
    if os.path.exists(VERSES_FILE):
        try:
            v_df = pd.read_csv(VERSES_FILE)
            if not v_df.empty:
                row = v_df.iloc[(week_num - 1) % len(v_df)]
                return {"verse": str(row["verse"]), "ref": str(row["ref"])}
        except Exception:
            pass
    return fallback

def get_schedule_image_path(week_key):
    if os.path.exists(SCHEDULE_RECORD_FILE):
        try:
            df_s = pd.read_csv(SCHEDULE_RECORD_FILE)
            match = df_s[df_s["week_key"] == week_key]
            if not match.empty:
                img_path = match.iloc[0]["image_path"]
                if os.path.exists(img_path): return img_path
        except Exception: pass
    return None

def save_schedule_record(week_key, uploaded_file):
    file_extension = uploaded_file.name.split(".")[-1]
    file_path = os.path.join(SCHEDULE_DIR, f"{week_key}.{file_extension}")
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    df_s = pd.read_csv(SCHEDULE_RECORD_FILE) if os.path.exists(SCHEDULE_RECORD_FILE) else pd.DataFrame(columns=["week_key", "image_path"])
    df_s = df_s[df_s["week_key"] != week_key]
    df_s = pd.concat([df_s, pd.DataFrame([{"week_key": week_key, "image_path": file_path}])], ignore_index=True)
    df_s.to_csv(SCHEDULE_RECORD_FILE, index=False, encoding="utf-8-sig")

# ==========================================
# 3. CSS 樣式美化
# ==========================================
st.markdown("""
    <style>
    html, body { max-width: 100vw; overflow-x: hidden; }
    h1 { font-size: clamp(22px, 6vw, 32px) !important; line-height: 1.3 !important; }
    
    div[data-testid="stButton"] button {
        width: 100% !important;
        white-space: normal !important;
        word-break: break-word !important;
    }
    div[data-testid="stButton"] button p {
        font-size: clamp(18px, 5vw, 26px) !important;
        font-weight: 800 !important;
    }
    div[data-testid="stButton"] button[kind="secondary"] {
        min-height: 3em !important;
        padding: 8px 6px !important;
        border-radius: 12px !important;
        border: 2px solid #0284C7 !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        margin-bottom: 8px !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background-color: #E0F2FE !important;
    }
    div[data-testid="stButton"] button[kind="primary"] {
        min-height: 3.2em !important;
        border-radius: 12px !important;
        background-color: #059669 !important;
        margin-bottom: 8px !important;
    }
    div[data-testid="stButton"] button[kind="primary"] p { color: #FFFFFF !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. 主程式介面
# ==========================================
if "current_member" not in st.session_state:
    st.session_state.current_member = None

now = datetime.datetime.now()
is_sunday = (now.weekday() == 6)
calc_date = now + datetime.timedelta(days=1) if is_sunday else now
current_week_num = calc_date.isocalendar()[1]

current_week_key = f"Y{PLAN_YEAR}-W{current_week_num:02d}"
current_week_display = f"第 {PLAN_YEAR} 年 - 第 {current_week_num:02d} 週"

df_members = load_members()
member_list = df_members["member_name"].tolist()
df_attendance = load_attendance()

st.title(f"📖 教會讀經簽到（{current_week_display}）")

tab_user, tab_admin = st.tabs(["✍️ 會友簽到專區", "🔒 後台統計與管理"])

# ------------------------------------------
# TAB 1: 會友簽到區
# ------------------------------------------
with tab_user:
    verse_info = get_weekly_verse(current_week_num)
    st.info(f"📖 **本週經文**：*{verse_info['verse']}* —— **{verse_info['ref']}**")

    # 顯示最新進度表
    latest_week_num = current_week_num
    if os.path.exists(SCHEDULE_RECORD_FILE):
        try:
            df_s_check = pd.read_csv(SCHEDULE_RECORD_FILE)
            if not df_s_check.empty:
                uploaded_weeks = df_s_check["week_key"].str.extract(r'W(\d+)')[0].dropna().astype(int).tolist()
                if uploaded_weeks: latest_week_num = max(uploaded_weeks)
        except Exception: pass

    latest_week_key = f"Y{PLAN_YEAR}-W{latest_week_num:02d}"
    latest_week_label = f"第 {PLAN_YEAR} 年 - 第 {latest_week_num:02d} 週"

    st.markdown(f"#### 🗓️ 最新進度表（{latest_week_label}）")
    latest_img_path = get_schedule_image_path(latest_week_key)
    if latest_img_path:
        st.image(latest_img_path, caption=f"【{latest_week_label}】進度對照表", use_container_width=True)
    else:
        st.warning(f"📌 目前尚未上傳【{latest_week_label}】的進度表圖片。")

    st.divider()

    # 會友名字列表
    if st.session_state.current_member is None:
        chunk_size = 10
        total_members = len(member_list)
        pages = [f"第 {i//chunk_size + 1} 頁 ({i+1}~{min(i+chunk_size, total_members)}人)" for i in range(0, total_members, chunk_size)]
        
        selected_page_label = st.radio("選擇分頁：", pages, horizontal=True)
        selected_page_idx = pages.index(selected_page_label)
        
        start_idx = selected_page_idx * chunk_size
        current_page_members = member_list[start_idx:min(start_idx + chunk_size, total_members)]
        
        st.write("👇 **請點選您的名字圖框：**")
        mid = (len(current_page_members) + 1) // 2
        col1, col2 = st.columns(2)
        
        with col1:
            for name in current_page_members[:mid]:
                is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == name)].empty
                status_icon = "✅" if is_signed else "👤"
                if st.button(f"{status_icon} {name}", key=f"btn_{name}", type="secondary", use_container_width=True):
                    st.session_state.current_member = name
                    st.rerun()

        with col2:
            for name in current_page_members[mid:]:
                is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == name)].empty
                status_icon = "✅" if is_signed else "👤"
                if st.button(f"{status_icon} {name}", key=f"btn_{name}", type="secondary", use_container_width=True):
                    st.session_state.current_member = name
                    st.rerun()

    # 個人簽到/補簽頁
    else:
        member_name = st.session_state.current_member
        if st.button("⬅️ 返回名字列表", type="secondary", use_container_width=True):
            st.session_state.current_member = None
            st.rerun()
            
        st.markdown(f"## 👤 {member_name} 的讀經專頁")
        st.markdown(f"### 📍 【本週進度】{current_week_display}")
        
        is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == member_name)].empty
        
        if is_signed:
            st.success(f"🎉 **{member_name}**，您本週已經完成簽到！")
        else:
            if st.button(f"🟢 完成【{current_week_display}】簽到", type="primary", use_container_width=True):
                add_single_record(current_week_key, member_name)
                st.toast("🎉 簽到成功！")
                st.rerun()
                
        st.divider()
        st.markdown("### 🟡 【補簽未完成進度】")
        
        signed_weeks = df_attendance[df_attendance["member_name"] == member_name]["week_key"].tolist()
        
        missing_weeks_info = []
        for w in range(1, current_week_num):
            w_key = f"Y{PLAN_YEAR}-W{w:02d}"
            w_display = f"第 {PLAN_YEAR} 年 - 第 {w:02d} 週"
            if w_key not in signed_weeks:
                missing_weeks_info.append({"key": w_key, "display": w_display})
        
        if missing_weeks_info:
            st.warning(f"📌 共有 **{len(missing_weeks_info)}** 週尚未完成，點擊圖框補簽：")
            mid_m = (len(missing_weeks_info) + 1) // 2
            
            mc1, mc2 = st.columns(2)
            with mc1:
                for item in missing_weeks_info[:mid_m]:
                    if st.button(f"🟡 {item['display']}", key=f"miss_{item['key']}", type="secondary", use_container_width=True):
                        add_single_record(item["key"], member_name)
                        st.toast(f"✅ 已成功補簽 `{item['display']}`！")
                        st.rerun()
            with mc2:
                for item in missing_weeks_info[mid_m:]:
                    if st.button(f"🟡 {item['display']}", key=f"miss_{item['key']}", type="secondary", use_container_width=True):
                        add_single_record(item["key"], member_name)
                        st.toast(f"✅ 已成功補簽 `{item['display']}`！")
                        st.rerun()
        else:
            st.success("🎉 太棒了！過去每一週的進度皆已完成！")

# ------------------------------------------
# TAB 2: 後台管理功能
# ------------------------------------------
with tab_admin:
    st.subheader("🔒 管理者控制台")
    pwd = st.text_input("請輸入管理者密碼：", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("🔓 驗證成功，歡迎進入後台管理系統！")
        
        admin_sub_tab1, admin_sub_tab2, admin_sub_tab3, admin_sub_tab4 = st.tabs([
            "📊 簽到數據總覽", 
            "🗓️ 上傳進度表圖片", 
            "👥 會友名單編輯", 
            "📥 匯出資料備份"
        ])
        
        # --- 子功能 1: 簽到數據總覽 ---
        with admin_sub_tab1:
            st.markdown("### 📊 簽到數據統計")
            total_records = len(df_attendance)
            unique_members = df_attendance["member_name"].nunique() if not df_attendance.empty else 0
            
            c1, c2 = st.columns(2)
            c1.metric("目前總簽到人次", f"{total_records} 次")
            c2.metric("已有簽到紀錄會友數", f"{unique_members} 人")
            
            st.divider()
            st.markdown("#### 🔍 簽到紀錄明細表")
            if not df_attendance.empty:
                st.dataframe(df_attendance.sort_values(by="timestamp", ascending=False), use_container_width=True)
            else:
                st.info("尚無任何簽到紀錄。")

        # --- 子功能 2: 上傳進度表圖片 ---
        with admin_sub_tab2:
            st.markdown("### 🗓️ 上傳/更換每週進度表圖片")
            target_week = st.number_input("選擇週數 (1~52)：", min_value=1, max_value=52, value=current_week_num)
            up_week_key = f"Y{PLAN_YEAR}-W{target_week:02d}"
            
            uploaded_img = st.file_uploader(f"請上傳【第 {PLAN_YEAR} 年 - 第 {target_week:02d} 週】進度對照表圖檔：", type=["png", "jpg", "jpeg"])
            
            if uploaded_img is not None:
                if st.button("⬆️ 儲存並發布此進度表"):
                    save_schedule_record(up_week_key, uploaded_img)
                    st.success(f"🎉【{up_week_key}】進度表圖片已成功更新！")
                    st.rerun()
            
            cur_img = get_schedule_image_path(up_week_key)
            if cur_img:
                st.markdown(f"**目前【{up_week_key}】使用的圖片：**")
                st.image(cur_img, width=400)

        # --- 子功能 3: 會友名單編輯 ---
        with admin_sub_tab3:
            st.markdown("### 👥 管理會友名單")
            st.write("可在下方文字框中新增或修改會友姓名（每行一位）：")
            
            current_m_text = "\n".join(member_list)
            new_m_text = st.text_area("會友名單列表：", value=current_m_text, height=350)
            
            if st.button("💾 儲存名單變更"):
                updated_names = [name.strip() for name in new_m_text.split("\n") if name.strip()]
                save_members(updated_names)
                st.success("🎉 會友名單更新成功！")
                st.rerun()

        # --- 子功能 4: 匯出資料備份 ---
        with admin_sub_tab4:
            st.markdown("### 📥 匯出與下載簽到資料")
            st.write("點擊下方按鈕可直接下載完整的簽到 CSV 檔：")
            
            if not df_attendance.empty:
                csv_data = df_attendance.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="⬇️ 下載簽到資料檔 (attendance_records.csv)",
                    data=csv_data,
                    file_name=f"Church_Attendance_Backup_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("目前尚無資料可供下載。")
