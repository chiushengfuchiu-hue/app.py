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
ATTENDANCE_FILE = "attendance_records.csv"
SCHEDULE_DIR = "schedules_img"
ADMIN_PASSWORD = "11190928"

PLAN_YEAR = 2 

os.makedirs(SCHEDULE_DIR, exist_ok=True)

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
# 2. 資料庫與邏輯處理
# ==========================================
def load_attendance():
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
    df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8-sig")

def delete_single_record(week_key, member_name):
    """【新增】撤銷/刪除特定會友某週的簽到紀錄"""
    df = load_attendance()
    week_key = str(week_key).strip()
    member_name = str(member_name).strip()
    
    df_new = df[~((df["week_key"] == week_key) & (df["member_name"] == member_name))]
    save_attendance(df_new)
    return True

def sync_to_gsheet_async(new_rows_list):
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
    """修正：優先讀取檔案，防止後台新增/修改的會友資料被還原"""
    if os.path.exists(MEMBERS_FILE):
        try:
            df_m = pd.read_csv(MEMBERS_FILE, encoding="utf-8-sig")
            if "member_name" in df_m.columns and not df_m.empty:
                df_m["member_name"] = df_m["member_name"].astype(str).str.strip()
                return df_m
        except Exception:
            pass
            
    df_m = pd.DataFrame({"member_name": INITIAL_MEMBERS})
    df_m.to_csv(MEMBERS_FILE, index=False, encoding="utf-8-sig")
    return df_m

def save_members(members_list):
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

def generate_pivot_report(target_year, max_week):
    df_att = load_attendance()
    members = load_members()["member_name"].tolist()
    
    report_data = []
    week_cols = [f"Y{target_year}-W{w:02d}" for w in range(1, max_week + 1)]
    
    for m in members:
        row = {"member_name": m}
        completed_count = 0
        m_signed = set(df_att[df_att["member_name"] == m]["week_key"].tolist())
        
        for w_col in week_cols:
            if w_col in m_signed:
                row[w_col] = "⚪ 已讀"
                completed_count += 1
            else:
                row[w_col] = "❌"
        
        row["完成週數"] = f"{completed_count} / {max_week}"
        row["完成率"] = f"{(completed_count / max_week * 100):.2f}%" if max_week > 0 else "0.00%"
        report_data.append(row)
        
    df_report = pd.DataFrame(report_data)
    cols_order = ["member_name", "完成週數", "完成率"] + week_cols
    return df_report[cols_order]

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

    st.markdown("#### 🗓️ 讀經進度表查詢")
    
    col_y, col_w = st.columns([1, 2])
    with col_y:
        selected_year = st.selectbox("請選擇年份：", [f"第 {y} 年 (Y{y})" for y in range(PLAN_YEAR, 0, -1)], index=0)
        target_y_num = int(selected_year.split("第 ")[1].split(" 年")[0])
    
    with col_w:
        max_w_display = current_week_num if target_y_num == PLAN_YEAR else 52
        week_options = [f"第 {w:02d} 週" for w in range(max_w_display, 0, -1)]
        selected_w_label = st.selectbox("請選擇週數：", week_options, index=0)
        target_w_num = int(selected_w_label.replace("第 ", "").replace(" 週", ""))
        
    selected_week_key = f"Y{target_y_num}-W{target_w_num:02d}"
    selected_img_path = get_schedule_image_path(selected_week_key)
    
    if selected_img_path:
        st.image(selected_img_path, caption=f"【第 {target_y_num} 年 - 第 {target_w_num:02d} 週】進度對照表", use_container_width=True)
    else:
        st.warning(f"📌 目前尚未上傳【Y{target_y_num}-W{target_w_num:02d}】的進度表圖片。")

    st.divider()

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

    else:
        member_name = st.session_state.current_member
        if st.button("⬅️ 返回名字列表", type="secondary", use_container_width=True):
            st.session_state.current_member = None
            st.rerun()
            
        st.markdown(f"## 👤 {member_name} 的讀經專頁")
        st.markdown(f"### 📍 【本週進度】{current_week_display}")
        
        is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == member_name)].empty
        
        if is_signed:
            st.success(f"🎉 **{member_name}**，您已完成本周讀經進度，願主保守力上加力恩上加恩！")
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
        
        admin_sub_tab1, admin_sub_tab2, admin_sub_tab3 = st.tabs([
            "📊 簽到進度總覽與匯出", 
            "🗓️ 上傳跨年進度表圖片", 
            "👥 會友名單編輯"
        ])
        
        # --- 子功能 1: 簽到總覽、四大季度匯出與誤簽撤銷 ---
        with admin_sub_tab1:
            st.markdown("### 📊 全會友讀經簽到進度總表")
            
            time_range = st.selectbox(
                "📅 請選擇匯出與統計時間區間：",
                ["最近 4 週", "第一季 (W01~W13)", "第二季 (W14~W26)", "第三季 (W27~W39)", "第四季 (W40~W52)", "半年 (26 週)", "全年度 (52 週)"]
            )
            
            if time_range == "第一季 (W01~W13)":
                start_w, end_w = 1, 13
            elif time_range == "第二季 (W14~W26)":
                start_w, end_w = 14, 26
            elif time_range == "第三季 (W27~W39)":
                start_w, end_w = 27, 39
            elif time_range == "第四季 (W40~W52)":
                start_w, end_w = 40, 52
            elif time_range == "最近 4 週":
                start_w, end_w = max(1, current_week_num - 3), current_week_num
            elif time_range == "半年 (26 週)":
                start_w, end_w = max(1, current_week_num - 25), current_week_num
            else:
                start_w, end_w = 1, 52

            df_pivot = generate_pivot_report(PLAN_YEAR, 52)
            target_cols = ["member_name", "完成週數", "完成率"] + [f"Y{PLAN_YEAR}-W{w:02d}" for w in range(start_w, end_w + 1)]
            df_pivot_filtered = df_pivot[target_cols]

            st.dataframe(df_pivot_filtered, use_container_width=True, height=400)
            
            # 將資料轉為帶有 BOM 的 UTF-8 位元組，確保 Excel 開啟絕不亂碼
            csv_bytes = df_pivot_filtered.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            
            st.download_button(
                label=f"📥 下載【{time_range}】簽到統計 Excel 報表 (CSV)",
                data=csv_bytes,
                file_name=f"Church_Attendance_{time_range}_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary"
            )
            # --- 🛠️ 誤簽撤銷區塊 ---
            st.divider()
            st.markdown("#### 🛠️ 誤簽撤銷 / 刪除紀錄區")
            col_del1, col_del2, col_del3 = st.columns([2, 2, 1])

            with col_del1:
                del_member = st.selectbox("選擇要修正的會友：", member_list)
            with col_del2:
                del_week_num = st.number_input("選擇要撤銷的週數 (1~52)：", min_value=1, max_value=52, value=current_week_num)
                del_week_key = f"Y{PLAN_YEAR}-W{del_week_num:02d}"
            with col_del3:
                st.write("")
                st.write("")
                if st.button("❌ 撤銷此簽到", type="secondary"):
                    delete_single_record(del_week_key, del_member)
                    st.toast(f"已成功刪除 {del_member} 在【{del_week_key}】的紀錄！")
                    st.rerun()

        # --- 子功能 2: 跨年份上傳進度表圖片 ---
        with admin_sub_tab2:
            st.markdown("### 🗓️ 上傳/更換進度表圖片（含歷史年份）")
            
            up_col1, up_col2 = st.columns(2)
            with up_col1:
                up_year = st.number_input("選擇年份 (如: 1代表第1年, 2代表第2年)：", min_value=1, max_value=4, value=PLAN_YEAR)
            with up_col2:
                up_week = st.number_input("選擇週數 (1~52)：", min_value=1, max_value=52, value=current_week_num)
                
            up_week_key = f"Y{up_year}-W{up_week:02d}"
            
            uploaded_img = st.file_uploader(f"請上傳【第 {up_year} 年 - 第 {up_week:02d} 週】進度對照表圖檔：", type=["png", "jpg", "jpeg"])
            
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
