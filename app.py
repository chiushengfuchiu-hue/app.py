import streamlit as st
import pandas as pd
import datetime
import os
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. 檔案與設定
# ==========================================
MEMBERS_FILE = "church_members.csv"
VERSES_FILE = "verses.csv"
SCHEDULE_RECORD_FILE = "schedule_records.csv"
ATTENDANCE_FILE = "attendance_records.csv"  # 本地簽到資料庫
SCHEDULE_DIR = "schedules_img"
ADMIN_PASSWORD = "church_admin"

PLAN_YEAR = 2 

os.makedirs(SCHEDULE_DIR, exist_ok=True)

INITIAL_MEMBERS = [
    "周寶燕", "曾笑", "黃然玉", "吳妃玉", "楊游美麗", 
    "翁淑美", "石美莎", "單麗蘭", "鄭富美", "李鶯芳", 
    "趙文崇", "李應昌", "賴健文", "林春妙", "邱文雀", 
    "梁垠盤", "陳宜宏", "郭彩梅", "林春桃", "鳳姐", 
    "黃敏生", "吳秀卉", "陳安俐", "程乃珍", "蕭慧麗", 
    "蔡慧俐", "林雅谷", "李俊修", "林淑惠", "盧正亮", 
    "林雅音", "劉淑珠", "葉雅雲", "趙文川"
]

TARGET_28_MEMBERS = [
    "周寶燕", "曾笑", "黃然玉", "吳妃玉", "楊游美麗", 
    "翁淑美", "石美莎", "單麗蘭", "鄭富美", 
    "趙文崇", "李應昌", "林春妙", "邱文雀", 
    "梁垠盤", "陳宜宏", "郭彩梅", "林春桃", "鳳姐", 
    "黃敏生", "吳秀卉", "程乃珍", "蕭慧麗", 
    "蔡慧俐", "林雅谷", "李俊修", "盧正亮", 
    "劉淑珠", "葉雅雲"
]

st.set_page_config(page_title="教會4年讀經計畫簽到系統", page_icon="📖", layout="wide")

# ==========================================
# 2. 本地與雲端資料處理
# ==========================================
def load_attendance():
    """載入本地簽到紀錄，保證 0 延遲且不會被 1000 行限制卡住"""
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
    """儲存簽到紀錄至本地 CSV"""
    df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8-sig")

def sync_to_gsheet_async(new_rows_list):
    """背景同步寫入 Google Sheets（不影響前台速度）"""
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
    except Exception as e:
        pass # 即使雲端失敗，本地資料庫依然正常發揮

def add_single_record(week_key, member_name):
    """新增單筆簽到"""
    df = load_attendance()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    week_key = str(week_key).strip()
    member_name = str(member_name).strip()
    
    # 避免重複
    match = df[(df["week_key"] == week_key) & (df["member_name"] == member_name)]
    if match.empty:
        new_row = pd.DataFrame([{"week_key": week_key, "member_name": member_name, "timestamp": now_str}])
        df = pd.concat([df, new_row], ignore_index=True)
        save_attendance(df)
        sync_to_gsheet_async([[week_key, member_name, now_str]])
    return True

# ==========================================
# CSS 樣式設定
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
# 3. 會友與進度資料處理
# ==========================================
def load_members():
    default_members = list(INITIAL_MEMBERS)
    for i in range(len(INITIAL_MEMBERS), 50):
        default_members.append(f"會友 {i+1:02d}")
        
    if os.path.exists(MEMBERS_FILE):
        try:
            df_m = pd.read_csv(MEMBERS_FILE)
            col_name = "member_name" if "member_name" in df_m.columns else df_m.columns[0]
            current_names = df_m[col_name].dropna().astype(str).str.strip().tolist()
            if len(current_names) >= 34 and "會友 01" not in current_names:
                return pd.DataFrame({"member_name": current_names})
        except Exception:
            pass

    df_m = pd.DataFrame({"member_name": default_members})
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

# ==========================================
# 4. 主程式頁面
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

    # 顯示最新的進度表
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

    # 名字列表
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

    # 個人專屬補簽頁面
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
        
        # 抓取該會友已簽到的週數
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
# TAB 2: 後台與一鍵批次補簽
# ------------------------------------------
with tab_admin:
    st.subheader("🔒 管理者數據與功能管理")
    pwd = st.text_input("請輸入管理者密碼：", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("身分驗證成功！")
        
        # 強大的一鍵批次初始化按鈕
        st.markdown("---")
        st.subheader("🚀 28 位會友一鍵批次補簽工具 (1~33週)")
        st.write(f"點擊下方按鈕，系統將自動寫入 **28位會友 × 1~33週** 的簽到紀錄，**保證圖框瞬間消失**！")
        
        if st.button("⚡ 點此立即完成 28 位會友 1~33 週批次補簽", type="primary"):
            df_att = load_attendance()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 建立比對 Set
            existing_set = set(zip(df_att["week_key"], df_att["member_name"]))
            
            new_records = []
            for m in TARGET_28_MEMBERS:
                for w in range(1, 34):
                    w_key = f"Y{PLAN_YEAR}-W{w:02d}"
                    if (w_key, m) not in existing_set:
                        new_records.append({"week_key": w_key, "member_name": m, "timestamp": now_str})
            
            if new_records:
                new_df = pd.DataFrame(new_records)
                df_att = pd.concat([df_att, new_df], ignore_index=True)
                save_attendance(df_att)
                st.success(f"🎉 成功寫入 {len(new_records)} 筆紀錄！過去 1~33 週補簽圖框已全數消失！")
                st.rerun()
            else:
                st.info("💡 1~33 週的紀錄先前已經存在，補簽圖框已清空！")
