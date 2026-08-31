import streamlit as st
import pandas as pd
import datetime
import os
import logging
import gspread
from google.oauthimport io
import logging
import os
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pandas as pd
import streamlit as st

# 本地暫存設定
ATTENDANCE_FILE = "attendance_records.csv"
SCHEDULE_DIR = "schedules_img"
os.makedirs(SCHEDULE_DIR, exist_ok=True)

# 取得 Secrets 設定
FOLDER_ID = st.secrets.get("FOLDER_ID", "1pB7pTJ8-SsPDvFqpu7mbE0Q3Op_kyfo9")
SPREADSHEET_NAME = st.secrets.get("spreadsheet_name", "Church_Attendance")

# --- 1. Google 服務連線初始化 ---


@st.cache_resource
def get_gcp_credentials():
  scope = [
      "https://www.googleapis.com/auth/spreadsheets",
      "https://www.googleapis.com/auth/drive",
  ]
  creds_dict = dict(st.secrets["gcp_service_account"])
  if "private_key" in creds_dict:
    pk = creds_dict["private_key"].replace("\\n", "\n")
    if not pk.startswith("-----BEGIN PRIVATE KEY-----"):
      pk = "-----BEGIN PRIVATE KEY-----\n" + pk
    if not pk.endswith("-----END PRIVATE KEY-----"):
      pk = pk + "\n-----END PRIVATE KEY-----"
    creds_dict["private_key"] = pk.strip()
  return Credentials.from_service_account_info(creds_dict, scopes=scope)


def get_drive_service():
  creds = get_gcp_credentials()
  return build("drive", "v3", credentials=creds)


def get_sheets_client():
  creds = get_gcp_credentials()
  return gspread.authorize(creds)


# --- 2. 簽到資料讀取與修復（防止 KeyError: 'week_key'） ---


def load_attendance():
  df = None
  # 優先從 Google Sheets 載入
  try:
    client = get_sheets_client()
    sheet = client.open(SPREADSHEET_NAME).worksheet("Attendance")
    data = sheet.get_all_records()
    if data:
      df = pd.DataFrame(data, dtype=str)
  except Exception as e:
    logging.error(f"從 Google Sheets 讀取失敗: {e}")

  # 若試算表讀取失敗，讀取本地 CSV
  if df is None and os.path.exists(ATTENDANCE_FILE):
    try:
      df = pd.read_csv(ATTENDANCE_FILE, dtype=str)
    except Exception as e:
      logging.error(f"從本地 CSV 讀取失敗: {e}")

  # 防護機制：若資料為空或不存在，強制建立正確欄位結構
  required_cols = ["week_key", "member_name", "timestamp"]
  if df is None or df.empty:
    df = pd.DataFrame(columns=required_cols)

  # 清除欄位名稱前後空格
  df.columns = df.columns.str.strip()

  # 強制自動補齊缺失的必要欄位
  for col in required_cols:
    if col not in df.columns:
      df[col] = ""

  return df


# --- 3. Google Drive 圖片上傳與取得功能 ---


def upload_image_to_drive(uploaded_file, filename):
  """上傳圖片至指定 Google Drive 資料夾並取得直接觀看網址"""
  service = get_drive_service()

  # 1. 檢查是否已存在同名檔案，若有則先刪除舊檔（避免重複）
  query = f"'{FOLDER_ID}' in parents and name = '{filename}' and trashed = false"
  results = (
      service.files()
      .list(q=query, fields="files(id)", supportsAllDrives=True)
      .execute()
  )
  files = results.get("files", [])
  for file in files:
    service.files().delete(
        fileId=file["id"], supportsAllDrives=True
    ).execute()

  # 2. 上傳新圖片
  file_metadata = {"name": filename, "parents": [FOLDER_ID]}
  media = MediaIoBaseUpload(
      io.BytesIO(uploaded_file.getvalue()),
      mimetype=uploaded_file.type,
      resumable=True,
  )
  file = (
      service.files()
      .create(
          body=file_metadata,
          media_body=media,
          fields="id",
          supportsAllDrives=True,
      )
      .execute()
  )

  # 3. 回傳公開預覽網址
  file_id = file.get("id")
  return f"https://lh3.googleusercontent.com/d/{file_id}"


def get_image_url_from_drive(filename):
  """從 Google Drive 尋找特定檔名的圖片網址"""
  try:
    service = get_drive_service()
    query = (
        f"'{FOLDER_ID}' in parents and name = '{filename}' and trashed = false"
    )
    results = (
        service.files()
        .list(q=query, fields="files(id)", supportsAllDrives=True)
        .execute()
    )
    files = results.get("files", [])
    if files:
      return f"https://lh3.googleusercontent.com/d/{files[0]['id']}"
  except Exception as e:
    logging.error(f"從 Drive 搜尋圖片失敗: {e}")
  return None


# --- 4. 後台 Tab 3 上傳邏輯整合 ---


def render_admin_upload_tab():
  st.subheader("📤 後台：上傳進度表圖片")

  week_key = st.text_input(
      "輸入週別代碼（例如：Y2-W01）", key="admin_week_key"
  )
  uploaded_file = st.file_uploader(
      "選擇進度表圖片", type=["jpg", "jpeg", "png"], key="admin_file"
  )

  if st.button("確認上傳進度表", type="primary"):
    if not week_key or not uploaded_file:
      st.warning("請填寫週別並選擇圖片！")
      return

    with st.spinner("圖片上傳備份至 Google Drive 中..."):
      ext = uploaded_file.name.split(".")[-1]
      filename = f"{week_key.strip()}.{ext}"

      # 1. 存入本地暫存
      local_path = os.path.join(SCHEDULE_DIR, filename)
      with open(local_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

      # 2. 同步上傳至 Google Drive（雲端備份）
      img_url = upload_image_to_drive(uploaded_file, filename)

      if img_url:
        st.success(
            f"🎉 【{week_key}】進度表已成功備份至 Google Drive！系統重啟圖片也不會消失。"
        )
      else:
        st.warning("本地已儲存，但雲端備份失敗，請檢查權限設定。")


# --- 5. 前台顯示圖片邏輯 ---


def display_schedule_image(week_key):
  """前台顯示進度表：優先找本地暫存，沒有就從 Google Drive 載入"""
  img_url = None

  # 1. 先找本地暫存
  for ext in ["png", "jpg", "jpeg"]:
    local_path = os.path.join(SCHEDULE_DIR, f"{week_key}.{ext}")
    if os.path.exists(local_path):
      st.image(local_path, caption=f"週別: {week_key}")
      return

  # 2. 本地沒有，自動從 Google Drive 尋找
  for ext in ["png", "jpg", "jpeg"]:
    img_url = get_image_url_from_drive(f"{week_key}.{ext}")
    if img_url:
      st.image(img_url, caption=f"週別: {week_key}（來自雲端）")
      return

# 修正前（文字黏在一起）：
# st.info(f"尚無【{week_key}】的進度表圖片。")2.service_account import Credentials

# 修正後（分開為正常的文字輸出與程式邏輯）：
st.info(f"尚無【{week_key}】的進度表圖片。")

# 設定 Logging 紀錄，方便背景除錯
logging.basicConfig(level=logging.INFO)

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

st.set_page_config(page_title="四年精讀聖經運動簽到系統", page_icon="📖", layout="wide")

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
        except Exception as e:
            logging.error(f"讀取簽到紀錄失敗: {e}")
    return pd.DataFrame(columns=["week_key", "member_name", "timestamp"])

def save_attendance(df):
    df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8-sig")

def delete_single_record(week_key, member_name):
    df = load_attendance()
    week_key = str(week_key).strip()
    member_name = str(member_name).strip()
    
    df_new = df[~((df["week_key"] == week_key) & (df["member_name"] == member_name))]
    save_attendance(df_new)
    return True

def sync_to_gsheet_async(new_rows_list):
    try:
        if "gcp_service_account" not in st.secrets:
            return
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
        logging.error(f"Google Sheets 同步失敗: {e}")

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
    if os.path.exists(MEMBERS_FILE):
        try:
            df_m = pd.read_csv(MEMBERS_FILE, encoding="utf-8-sig")
            if "member_name" in df_m.columns and not df_m.empty:
                df_m["member_name"] = df_m["member_name"].astype(str).str.strip()
                return df_m
        except Exception as e:
            logging.error(f"讀取會友名單失敗: {e}")
            
    df_m = pd.DataFrame({"member_name": INITIAL_MEMBERS})
    df_m.to_csv(MEMBERS_FILE, index=False, encoding="utf-8-sig")
    return df_m

def save_members(members_list):
    pd.DataFrame({"member_name": members_list}).to_csv(MEMBERS_FILE, index=False, encoding="utf-8-sig")

def get_weekly_verse(week_num):
    fallback = {
        "verse": "「你的話是我腳前的燈，是我路上的光。」", 
        "ref": "詩篇 119:105",
        "encouragement": "讓上帝的話語成為你每日的亮光與引導！"
    }
    if os.path.exists(VERSES_FILE):
        try:
            v_df = pd.read_csv(VERSES_FILE)
            if not v_df.empty:
                row = v_df.iloc[(week_num - 1) % len(v_df)]
                return {
                    "verse": str(row["verse"]), 
                    "ref": str(row["ref"]),
                    "encouragement": str(row.get("encouragement", ""))
                }
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

def get_latest_uploaded_week_key():
    if os.path.exists(SCHEDULE_RECORD_FILE):
        try:
            df_s = pd.read_csv(SCHEDULE_RECORD_FILE)
            valid_weeks = []
            for _, row in df_s.iterrows():
                if os.path.exists(str(row["image_path"])):
                    w_key = str(row["week_key"]).strip()
                    if w_key.startswith(f"Y{PLAN_YEAR}-W"):
                        try:
                            w_num = int(w_key.split("-W")[1])
                            valid_weeks.append(w_num)
                        except Exception:
                            pass
            if valid_weeks:
                max_w = max(valid_weeks)
                return f"Y{PLAN_YEAR}-W{max_w:02d}", max_w
        except Exception:
            pass
            
    now = datetime.datetime.now()
    is_sunday = (now.weekday() == 6)
    calc_date = now + datetime.timedelta(days=1) if is_sunday else now
    current_week_num = calc_date.isocalendar()[1]
    return f"Y{PLAN_YEAR}-W{current_week_num:02d}", current_week_num

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
    h1 { font-size: clamp(26px, 6vw, 38px) !important; line-height: 1.3 !important; }
    
    div[data-baseweb="tab-list"] {
        gap: 10px !important;
        margin-bottom: 20px !important;
    }
    
    button[data-baseweb="tab"] {
        border-radius: 12px !important;
        padding: 12px 20px !important;
        margin: 2px !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0px 2px 5px rgba(0,0,0,0.08) !important;
    }
    
    div[data-testid="stTabs"] [role="tab"] p, 
    div[data-testid="stTabs"] [role="tab"] div {
        font-size: clamp(22px, 5.5vw, 28px) !important;
        font-weight: 900 !important;
        letter-spacing: 1px !important;
        line-height: 1.3 !important;
    }
    
    button[data-baseweb="tab"]:nth-child(1) { background-color: #ECFDF5 !important; border: 2.5px solid #10B981 !important; }
    button[data-baseweb="tab"]:nth-child(1) p { color: #047857 !important; }
    button[data-baseweb="tab"]:nth-child(1)[aria-selected="true"] { background-color: #059669 !important; border-color: #047857 !important; }
    button[data-baseweb="tab"]:nth-child(1)[aria-selected="true"] p { color: #FFFFFF !important; }

    button[data-baseweb="tab"]:nth-child(2) { background-color: #EFF6FF !important; border: 2.5px solid #3B82F6 !important; }
    button[data-baseweb="tab"]:nth-child(2) p { color: #1D4ED8 !important; }
    button[data-baseweb="tab"]:nth-child(2)[aria-selected="true"] { background-color: #2563EB !important; border-color: #1D4ED8 !important; }
    button[data-baseweb="tab"]:nth-child(2)[aria-selected="true"] p { color: #FFFFFF !important; }

    button[data-baseweb="tab"]:nth-child(3) { background-color: #F8FAFC !important; border: 2.5px solid #64748B !important; }
    button[data-baseweb="tab"]:nth-child(3) p { color: #334155 !important; }
    button[data-baseweb="tab"]:nth-child(3)[aria-selected="true"] { background-color: #475569 !important; border-color: #334155 !important; }
    button[data-baseweb="tab"]:nth-child(3)[aria-selected="true"] p { color: #FFFFFF !important; }

    div[data-baseweb="tab-highlight"] { display: none !important; }

    div[data-aria-expanded] p, div[data-testid="stExpander"] summary p {
        font-size: clamp(20px, 4.8vw, 26px) !important;
        font-weight: 800 !important;
        line-height: 1.5 !important;
        color: #1E293B !important;
    }
    
    div[data-testid="stButton"] button {
        width: 100% !important;
        white-space: normal !important;
        word-break: break-word !important;
    }
    div[data-testid="stButton"] button p {
        font-size: clamp(20px, 5.5vw, 28px) !important;
        font-weight: 800 !important;
    }
    div[data-testid="stButton"] button[kind="secondary"] {
        min-height: 3.2em !important;
        padding: 10px 8px !important;
        border-radius: 14px !important;
        border: 2.5px solid #0284C7 !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        margin-bottom: 10px !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover { background-color: #E0F2FE !important; }
    div[data-testid="stButton"] button[kind="primary"] {
        min-height: 3.5em !important;
        border-radius: 14px !important;
        background-color: #059669 !important;
        margin-bottom: 10px !important;
    }
    div[data-testid="stButton"] button[kind="primary"] p { color: #FFFFFF !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 4. 主程式介面
# ==========================================
if "current_member" not in st.session_state:
    st.session_state.current_member = None

current_week_key, current_week_num = get_latest_uploaded_week_key()
current_week_display = f"第 {PLAN_YEAR} 年 - 第 {current_week_num:02d} 週"

df_members = load_members()
member_list = df_members["member_name"].tolist()
df_attendance = load_attendance()

st.title(f"📖 最新讀經進度表（{current_week_display}）")

tab_user, tab_history, tab_admin = st.tabs([
    "✍️ 會友簽到專區", 
    "🗓️ 過往進度查詢", 
    "🔒 後台統計管理"
])

import streamlit.components.v1 as components

import streamlit.components.v1 as components

import streamlit.components.v1 as components

import streamlit.components.v1 as components

# ------------------------------------------
# TAB 1: 會友簽到區
# ------------------------------------------
with tab_user:
    current_img_path = get_schedule_image_path(current_week_key)
    if current_img_path:
        st.image(current_img_path, caption=f"【最新進度】{current_week_display}", use_container_width=True)
    else:
        st.info(f"📌 目前為【{current_week_display}】簽到。")

    # 1. 專頁頂部橫線與錨點
    st.markdown("<div id='divider-top-anchor'></div>", unsafe_allow_html=True)
    st.divider()

    # 初始化 Session State
    if "scroll_target" not in st.session_state:
        st.session_state.scroll_target = None
    if "open_section" not in st.session_state:
        st.session_state.open_section = None

    # JavaScript 動態自動滑動定位機制
    if st.session_state.scroll_target:
        target_id = st.session_state.scroll_target
        components.html(
            f"""
            <script>
                setTimeout(function() {{
                    var el = window.parent.document.getElementById('{target_id}');
                    if (el) {{
                        el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
                    }}
                }}, 150);
            </script>
            """,
            height=0,
        )
        st.session_state.scroll_target = None

    # --------------------------------------
    # 情況 A：未選擇會友（顯示 4 組分區圖框）
    # --------------------------------------
    if st.session_state.current_member is None:
        st.markdown("<div id='members-list-top'></div>", unsafe_allow_html=True)
        st.markdown("### 👇 請點擊您所屬的分區展開名字列表：")
        
        valid_members = [
            m for m in member_list 
            if m and str(m).strip() and not str(m).startswith("會友")
        ]
        
        chunk_size = 10
        total_valid = len(valid_members)
        
        for i in range(0, total_valid, chunk_size):
            chunk = valid_members[i:i + chunk_size]
            page_num = (i // chunk_size) + 1
            
            if chunk:
                names_text = "、".join(chunk)
                is_this_open = (st.session_state.open_section == page_num)
                
                # 分區標題圖框
                toggle_icon = "🔽" if is_this_open else "▶️"
                header_label = f"{toggle_icon} 📦 【第 {page_num} 區】 {names_text}"
                
                if st.button(header_label, key=f"sec_toggle_{page_num}", type="secondary", use_container_width=True):
                    if is_this_open:
                        st.session_state.open_section = None
                    else:
                        st.session_state.open_section = page_num
                        # 點擊該區時，將錨點設在該區內部的分割線
                        st.session_state.scroll_target = f"line-anchor-{page_num}"
                    st.rerun()

                # 當該分區被點開時，顯示分割線與名字按鈕
                if is_this_open:
                    # 📍 錨點標籤 + 實線：正好介於標題圖框與第一個名字之間
                    st.markdown(f"<div id='line-anchor-{page_num}'></div>", unsafe_allow_html=True)
                    st.divider()
                    
                    col1, col2 = st.columns(2)
                    mid = (len(chunk) + 1) // 2
                    
                    with col1:
                        for name in chunk[:mid]:
                            is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == name)].empty
                            status_icon = "✅" if is_signed else "👤"
                            if st.button(f"{status_icon} {name}", key=f"btn_dyn_{page_num}_{name}", type="secondary", use_container_width=True):
                                st.session_state.current_member = name
                                st.session_state.scroll_target = "divider-top-anchor"
                                st.rerun()

                    with col2:
                        for name in chunk[mid:]:
                            is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == name)].empty
                            status_icon = "✅" if is_signed else "👤"
                            if st.button(f"{status_icon} {name}", key=f"btn_dyn_{page_num}_{name}", type="secondary", use_container_width=True):
                                st.session_state.current_member = name
                                st.session_state.scroll_target = "divider-top-anchor"
                                st.rerun()

    # --------------------------------------
    # 情況 B：已選擇會友（顯示個人簽到專頁）
    # --------------------------------------
    else:
        member_name = st.session_state.current_member
        
        if st.button("⬅️ 返回選擇名字列表", type="secondary", use_container_width=True):
            st.session_state.current_member = None
            current_sec = st.session_state.open_section
            if current_sec:
                # 返回時精準對焦回剛剛那區名字上方的實線
                st.session_state.scroll_target = f"line-anchor-{current_sec}"
            else:
                st.session_state.scroll_target = "members-list-top"
            st.rerun()
            
        st.markdown(f"## 👤 {member_name} 的讀經專頁")
        st.markdown(f"### 📍 【本週進度】{current_week_display}")
        
        is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == member_name)].empty
        
        if is_signed:
            st.success(f"🎉 **{member_name}**，您已完成本週讀經進度，願主保守力上加力恩上加恩！")
        else:
            if st.button(f"🟢 若完成【{current_week_display}】請按此簽到", type="primary", use_container_width=True):
                add_single_record(current_week_key, member_name)
                st.toast("🎉 簽到成功！")
                st.session_state.scroll_target = "divider-top-anchor"
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
            st.warning(f"📌 共有 **{len(missing_weeks_info)}** 週尚未完成，點擊按鈕補簽：")
            mid_m = (len(missing_weeks_info) + 1) // 2
            
            mc1, mc2 = st.columns(2)
            with mc1:
                for item in missing_weeks_info[:mid_m]:
                    if st.button(f"🟡 {item['display']}", key=f"miss_{member_name}_{item['key']}", type="secondary", use_container_width=True):
                        add_single_record(item["key"], member_name)
                        st.toast(f"✅ 已成功補簽 `{item['display']}`！")
                        st.session_state.scroll_target = "divider-top-anchor"
                        st.rerun()
            with mc2:
                for item in missing_weeks_info[mid_m:]:
                    if st.button(f"🟡 {item['display']}", key=f"miss_{member_name}_{item['key']}", type="secondary", use_container_width=True):
                        add_single_record(item["key"], member_name)
                        st.toast(f"✅ 已成功補簽 `{item['display']}`！")
                        st.session_state.scroll_target = "divider-top-anchor"
                        st.rerun()
        else:
            st.success("🎉 太棒了！過去每一週的進度皆已完成！")

    st.divider()
    verse_info = get_weekly_verse(current_week_num)
    st.markdown(f"📖 **本週靈修經文**：{verse_info['ref']}")
    st.markdown(f"> *{verse_info['verse']}*")
    if verse_info.get('encouragement'):
        st.markdown(f"💬 **心靈補給**：{verse_info['encouragement']}")
# ------------------------------------------
# TAB 2: 獨立過往讀經進度查詢頁面
# ------------------------------------------
with tab_history:
    st.markdown("### 🗓️ 歷史讀經進度表查詢")
    
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

# ------------------------------------------
# TAB 3: 後台統計與管理
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
            
            csv_bytes = df_pivot_filtered.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            
            st.download_button(
                label=f"📥 下載【{time_range}】簽到統計 Excel 報表 (CSV)",
                data=csv_bytes,
                file_name=f"Church_Attendance_{time_range}_{datetime.datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
            st.divider()
            st.markdown("#### 🛠️ 誤簽撤銷 / 刪除紀錄區")
            col_del1, col_del2, col_del3, col_del4 = st.columns([2, 2, 2, 1.5])

            with col_del1:
                del_member = st.selectbox("選擇要修正的會友：", member_list)
            with col_del2:
                del_year_num = st.number_input("選擇年份：", min_value=1, max_value=4, value=PLAN_YEAR)
            with col_del3:
                del_week_num = st.number_input("選擇週數 (1~52)：", min_value=1, max_value=52, value=current_week_num)
                del_week_key = f"Y{del_year_num}-W{del_week_num:02d}"
            with col_del4:
                st.write("")
                st.write("")
                if st.button("❌ 撤銷此簽到", type="secondary"):
                    delete_single_record(del_week_key, del_member)
                    st.toast(f"已成功刪除 {del_member} 在【{del_week_key}】的紀錄！")
                    st.rerun()

        with admin_sub_tab2:
            st.markdown("### 🗓️ 上傳/更換進度表圖片（含歷史年份）")
            
            up_col1, up_col2 = st.columns(2)
            with up_col1:
                up_year = st.number_input("選擇年份 (如: 1代表第1年, 2代表第2年)：", min_value=1, max_value=4, value=PLAN_YEAR)
            with up_col2:
                default_up_week = min(52, current_week_num + 1)
                up_week = st.number_input("選擇週數 (1~52)：", min_value=1, max_value=52, value=default_up_week)
                
            up_week_key = f"Y{up_year}-W{up_week:02d}"
            
            uploaded_img = st.file_uploader(f"請上傳【第 {up_year} 年 - 第 {up_week:02d} 週】進度對照表圖檔：", type=["png", "jpg", "jpeg"])
            
            if uploaded_img is not None:
                if st.button("⬆️ 儲存並發布此進度表"):
                    save_schedule_record(up_week_key, uploaded_img)
                    st.success(f"🎉【{up_week_key}】進度表圖片已成功上傳！系統已自動同步重置為【第 {up_week:02d} 週】簽到頁面！")
                    st.rerun()
            
            cur_img = get_schedule_image_path(up_week_key)
            if cur_img:
                st.markdown(f"**目前【{up_week_key}】使用的圖片：**")
                st.image(cur_img, width=400)

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
