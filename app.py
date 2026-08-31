import streamlit as st
import pandas as pd
import datetime
import os
import logging
import io
import docx
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components
from googleapiclient.discovery import build
import google.generativeai as genai
from PIL import Image
import requests

# ==========================================
# 簽到二次確認彈窗
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
            
            if missing_weeks:
                st.toast(f"🎉 簽到成功！已一併補齊過往 {len(missing_weeks)} 週進度！")
            else:
                st.toast("🎉 簽到成功！")
                
            st.session_state.scroll_target = "divider-top-anchor"
            st.rerun()
            
    with col2:
        if st.button("❌ 取消", type="secondary", use_container_width=True):
            st.rerun()

# 設定 Logging 紀錄
logging.basicConfig(level=logging.INFO)

# ==========================================
# 1. 基礎設定與常數
# ==========================================
MEMBERS_FILE = "church_members.csv"
VERSES_FILE = "verses.csv"
ATTENDANCE_FILE = "attendance_records.csv"
GUIDE_FOLDER_ID = "1-RkVxCZy9wS_2X6Huw5p2mWhv1b6l0HM"

ADMIN_PASSWORD = st.secrets.get("admin_password", "11190928")
PLAN_YEAR = 2

# 66 卷經書與雲端硬碟編號對照表
BOOK_CODE_MAP = {
    "創世記": "01", "出埃及記": "02", "利未記": "03", "民數記": "04", "申命記": "05",
    "約書亞記": "06", "士師記": "07", "路得記": "08", "撒母耳記上": "09", "撒母耳記下": "10",
    "列王紀上": "11", "列王紀下": "12", "歷代志上": "13", "歷代志下": "14", "以斯拉記": "15",
    "尼希米記": "16", "以斯帖記": "17", "約伯記": "18", "詩篇": "19", "箴言": "20",
    "傳道書": "21", "雅歌": "22", "以賽亞書": "23", "耶利米書": "24", "耶利米哀歌": "25",
    "以西結書": "26", "但以理書": "27", "何西阿書": "28", "約珥書": "29", "阿摩司書": "30",
    "俄巴底亞書": "31", "約拿書": "32", "彌迦書": "33", "西番雅": "34", "哈該書": "35",
    "撒迦利亞書": "36", "瑪拉基書": "37", 
    "馬太福音": "38", "馬可福音": "39", "路加福音": "40", "約翰福音": "41", "使徒行傳": "42",
    "羅馬書": "43", "哥林多前書": "44", "哥林多後書": "45", "加拉太書": "46", "以弗所書": "47",
    "腓立比書": "48", "歌羅西書": "49", "帖撒羅尼迦前書": "50", "帖撒羅尼迦後書": "51",
    "提摩太前書": "52", "提摩太後書": "53", "提多書": "54", "腓利門書": "55", "希伯來書": "56",
    "雅各書": "57", "彼得前書": "58", "彼得後書": "59", "約翰一書": "60", "約翰二書": "61",
    "約翰三書": "62", "猶大書": "63", "啟示錄": "64"
}

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
# 2. 輔助與 GCP 憑證函式
# ==========================================
def get_gcp_credentials():
    if "gcp_service_account" not in st.secrets:
        return None
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
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

@st.cache_resource
def get_drive_service():
    creds = get_gcp_credentials()
    if not creds:
        return None
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    scoped_creds = creds.with_scopes(scopes)
    return build("drive", "v3", credentials=scoped_creds)

@st.cache_data(ttl=3600)
def fetch_docx_content_by_books(book_names):
    """根據指定的經卷名稱清單，自動從雲端硬碟對應編號抓取檔案並合併內容"""
    try:
        service = get_drive_service()
        if not service:
            return "⚠️ 無法取得 Google Drive 授權連線。"
        
        query = f"'{GUIDE_FOLDER_ID}' in parents and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        files = results.get("files", [])
        
        combined_text = []
        
        for b_name in book_names:
            matched_code = None
            for key, code in BOOK_CODE_MAP.items():
                if key in b_name:
                    matched_code = code
                    break
            
            target_file = None
            for f in files:
                fname = f["name"]
                if matched_code and (fname.startswith(matched_code) or f"{matched_code}_" in fname or f"{matched_code}." in fname):
                    target_file = f
                    break
                elif b_name in fname:
                    target_file = f
                    break
            
            if target_file:
                request = service.files().get_media(fileId=target_file["id"])
                file_bytes = io.BytesIO(request.execute())
                doc = docx.Document(file_bytes)
                file_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip() != ""])
                combined_text.append(f"📌 【經卷導讀：{b_name} (對應檔案: {target_file['name']})】\n\n{file_text}")
            else:
                combined_text.append(f"💡 雲端資料夾中找不到與「{b_name}」對應的導讀 Word 檔案。")
                
        return "\n\n" + "="*40 + "\n\n".join(combined_text)
    except Exception as e:
        return f"⚠️ 讀取導讀檔案時發生錯誤：{e}"

@st.cache_data(ttl=300)
def get_gdrive_image_url(year_num, week_num):
    try:
        creds = get_gcp_credentials()
        if not creds:
            return None
        
        drive_service = build('drive', 'v3', credentials=creds)

        folder_id = st.secrets.get("drive_folder_id", None)
        if not folder_id:
            return None
            
        if "folders/" in folder_id:
            folder_id = folder_id.split("folders/")[1].split("?")[0]

        actual_year = 2026 - (PLAN_YEAR - year_num)
        search_year = str(actual_year)
        search_term_1 = f"第{week_num}周"
        search_term_2 = f"第{week_num}週"

        query = (
            f"'{folder_id}' in parents and name contains '{search_year}' "
            f"and (name contains '{search_term_1}' or name contains '{search_term_2}') "
            f"and trashed = false"
        )
        
        results = drive_service.files().list(
            q=query, 
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        files = results.get('files', [])
        if files:
            file_id = files[0]['id']
            return f"https://lh3.googleusercontent.com/d/{file_id}"
            
    except Exception as e:
        logging.error(f"從 Google Drive 搜尋 Y{year_num}-W{week_num} 圖片失敗: {e}")
    
    return None

def ai_detect_books_from_image(image_url):
    """利用 Gemini 視覺模型自動辨識進度表圖片中出現的經卷名稱"""
    try:
        if not image_url:
            return []
        
        response = requests.get(image_url)
        img = Image.open(io.BytesIO(response.content))
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = "請仔細閱讀這張聖經讀經進度表圖片，找出這張表所涵蓋的所有聖經書卷名稱（例如創世記、約珥書、阿摩司書等）。請直接條列出書卷名稱即可，不要有多餘的字句。"
        
        result = model.generate_content([img, prompt])
        text_result = result.text.strip()
        
        detected_books = []
        for book_name in BOOK_CODE_MAP.keys():
            if book_name in text_result:
                detected_books.append(book_name)
                
        return detected_books
    except Exception as e:
        logging.error(f"自動辨識圖片失敗: {e}")
        return []

# ==========================================
# 3. 資料庫與簽到邏輯
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

def sync_to_gsheet_async(new_rows_list):
    try:
        creds = get_gcp_credentials()
        if not creds:
            return
        client = gspread.authorize(creds)
        sheet_name = st.secrets.get("spreadsheet_name", "Church_Attendance")
        sheet = client.open(sheet_name).sheet1
        sheet.append_rows(new_rows_list)
    except Exception as e:
        logging.error(f"Google Sheets 同步失敗: {e}")

def add_batch_records(records_list):
    df = load_attendance()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_rows = []
    
    for week_key, member_name in records_list:
        week_key = str(week_key).strip()
        member_name = str(member_name).strip()
        match = df[(df["week_key"] == week_key) & (df["member_name"] == member_name)]
        if match.empty:
            new_rows.append({"week_key": week_key, "member_name": member_name, "timestamp": now_str})
            
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        df = pd.concat([df, new_df], ignore_index=True)
        save_attendance(df)
        gsheet_rows = [[r["week_key"], r["member_name"], r["timestamp"]] for r in new_rows]
        sync_to_gsheet_async(gsheet_rows)

def delete_single_record(week_key, member_name):
    df = load_attendance()
    week_key = str(week_key).strip()
    member_name = str(member_name).strip()
    df_new = df[~((df["week_key"] == week_key) & (df["member_name"] == member_name))]
    save_attendance(df_new)
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

def get_current_week_num():
    now = datetime.datetime.now()
    is_sunday = (now.weekday() == 6)
    calc_date = now + datetime.timedelta(days=1) if is_sunday else now
    return calc_date.isocalendar()[1]

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
# 4. CSS 樣式
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
# 5. 主介面
# ==========================================
if "current_member" not in st.session_state:
    st.session_state.current_member = None

current_week_num = get_current_week_num()
current_week_key = f"Y{PLAN_YEAR}-W{current_week_num:02d}"
current_week_display = f"第 {PLAN_YEAR} 年 - 第 {current_week_num:02d} 週"

df_members = load_members()
member_list = df_members["member_name"].tolist()
df_attendance = load_attendance()

st.title(f"📖 最新讀經進度表（{current_week_display}）")

tab_user, tab_history, tab_admin = st.tabs([
    "✍️ 會友簽到專區", 
    "🗓️ 過往進度與導讀經文查詢", 
    "🔒 後台統計管理"
])

# ------------------------------------------
# TAB 1: 會友簽到區
# ------------------------------------------
with tab_user:
    current_img_url = get_gdrive_image_url(PLAN_YEAR, current_week_num)
    if current_img_url:
        st.image(current_img_url, caption=f"【最新進度】{current_week_display}", use_container_width=True)
    else:
        st.info(f"📌 目前為【{current_week_display}】簽到（雲端硬碟尚未找到第 {current_week_num} 週進度表）。")

    st.markdown("<div id='divider-top-anchor'></div>", unsafe_allow_html=True)
    st.divider()

    if "scroll_target" not in st.session_state:
        st.session_state.scroll_target = None
    if "open_section" not in st.session_state:
        st.session_state.open_section = None

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

                toggle_icon = "🔽" if is_this_open else "▶️"
                header_label = f"{toggle_icon} 📦 【第 {page_num} 區】 {names_text}"

                if st.button(header_label, key=f"sec_toggle_{page_num}", type="secondary", use_container_width=True):
                    if is_this_open:
                        st.session_state.open_section = None
                    else:
                        st.session_state.open_section = page_num
                        st.session_state.scroll_target = f"line-anchor-{page_num}"
                    st.rerun()

                if is_this_open:
                    st.markdown(f"<div id='line-anchor-{page_num}'></div>", unsafe_allow_html=True)
                    st.divider()

                    col1, col2 = st.columns(2)
                    mid = (len(chunk) + 1) // 2

                    with col1:
                        for name in chunk[:mid]:
                            is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == name)].empty
                            status_icon = "✅" if is_signed else "👤"
                            if st.button(f"{status_icon} {name}", key=f"btn_dyn_{page_num}_{name}_c1", type="secondary", use_container_width=True):
                                st.session_state.current_member = name
                                st.session_state.scroll_target = "divider-top-anchor"
                                st.rerun()

                    with col2:
                        for name in chunk[mid:]:
                            is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == name)].empty
                            status_icon = "✅" if is_signed else "👤"
                            if st.button(f"{status_icon} {name}", key=f"btn_dyn_{page_num}_{name}_c2", type="secondary", use_container_width=True):
                                st.session_state.current_member = name
                                st.session_state.scroll_target = "divider-top-anchor"
                                st.rerun()

    else:
        member_name = st.session_state.current_member

        if st.button("⬅️ 返回選擇名字列表", type="secondary", use_container_width=True):
            st.session_state.current_member = None
            current_sec = st.session_state.open_section
            if current_sec:
                st.session_state.scroll_target = f"line-anchor-{current_sec}"
            else:
                st.session_state.scroll_target = "members-list-top"
            st.rerun()

        st.markdown(f"## 👤 {member_name} 的讀經專頁")
        
        signed_weeks = df_attendance[df_attendance["member_name"] == member_name]["week_key"].tolist()
        
        missing_weeks_info = []
        for w in range(1, current_week_num):
            w_key = f"Y{PLAN_YEAR}-W{w:02d}"
            w_display = f"第 {PLAN_YEAR} 年 - 第 {w:02d} 週"
            if w_key not in signed_weeks:
                missing_weeks_info.append({"key": w_key, "display": w_display, "week_num": w})

        st.markdown(f"### 📍 【本週進度】{current_week_display}")

        is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == member_name)].empty

        if is_signed:
            st.success(f"🎉 **{member_name}**，您已完成本週讀經進度，願主保守力上加力恩上加恩！")
        else:
            if st.button(f"🟢 若完成【{current_week_display}】請按此簽到", type="primary", use_container_width=True):
                confirm_checkin_dialog(member_name, current_week_display, current_week_key, missing_weeks_info)
                
                records_to_add = [(current_week_key, member_name)]
                for m_item in missing_weeks_info:
                    records_to_add.append((m_item["key"], member_name))
                
                add_batch_records(records_to_add)

                if missing_weeks_info:
                    st.toast(f"🎉 簽到成功！並已自動為您補齊過往 {len(missing_weeks_info)} 週進度！")
                else:
                    st.toast("🎉 簽到成功！")
                
                st.session_state.scroll_target = "divider-top-anchor"
                st.rerun()

        st.divider()
        st.markdown("### 🟡 【過往進度補簽狀態】")

        if missing_weeks_info:
            if not is_signed:
                st.warning(f"⚠️ 您尚有 **{len(missing_weeks_info)}** 週過往進度尚未簽到，點擊以下按鈕可單獨補簽：")
            else:
                st.info(f"📌 您先前尚有 **{len(missing_weeks_info)}** 週紀錄未補齊，可點擊下方按鈕單獨補簽：")

            mid_m = (len(missing_weeks_info) + 1) // 2

            mc1, mc2 = st.columns(2)
            with mc1:
                for item in missing_weeks_info[:mid_m]:
                    if st.button(f"🟡 {item['display']}", key=f"miss_{member_name}_{item['key']}_c1", type="secondary", use_container_width=True):
                        add_batch_records([(item["key"], member_name)])
                        st.toast(f"✅ 已成功補簽 `{item['display']}`！")
                        st.session_state.scroll_target = "divider-top-anchor"
                        st.rerun()
            with mc2:
                for item in missing_weeks_info[mid_m:]:
                    if st.button(f"🟡 {item['display']}", key=f"miss_{member_name}_{item['key']}_c2", type="secondary", use_container_width=True):
                        add_batch_records([(item["key"], member_name)])
                        st.toast(f"✅ 已成功補簽 `{item['display']}`！")
                        st.session_state.scroll_target = "divider-top-anchor"
                        st.rerun()
        else:
            st.success("🎉 過往進度已全部完成，無需補簽！")

    st.divider()
    verse_info = get_weekly_verse(current_week_num)
    st.markdown(f"📖 **本週靈修經文**：{verse_info['ref']}")
    st.markdown(f"> *{verse_info['verse']}*")
    if verse_info.get('encouragement'):
        st.markdown(f"💬 **心靈補給**：{verse_info['encouragement']}")

# ------------------------------------------
# TAB 2: AI 智慧辨識與歷史導讀經文檢視
# ------------------------------------------
with tab_history:
    st.markdown("### 🗓️ 歷史讀經進度與導讀經文查詢")

    col_y, col_w = st.columns([1, 2])
    with col_y:
        selected_year = st.selectbox("請選擇年份：", [f"第 {y} 年 (Y{y})" for y in range(PLAN_YEAR, 0, -1)], index=0, key="hist_year_sel")
        target_y_num = int(selected_year.split("第 ")[1].split(" 年")[0])

    with col_w:
        max_w_display = current_week_num if target_y_num == PLAN_YEAR else 52
        week_options = [f"第 {w:02d} 週" for w in range(max_w_display, 0, -1)]
        selected_w_label = st.selectbox("請選擇週數：", week_options, index=0, key="hist_week_sel")
        target_w_num = int(selected_w_label.replace("第 ", "").replace(" 週", ""))

    history_img_url = get_gdrive_image_url(target_y_num, target_w_num)

    if history_img_url:
        st.image(history_img_url, caption=f"【第 {target_y_num} 年 - 第 {target_w_num:02d} 週】進度對照表", use_container_width=True)
        
        # 🤖 自動透過 AI 視覺辨識圖片中的經卷
        with st.spinner("🤖 正在智慧辨識進度表圖片中的經文與經卷..."):
            auto_detected_books = ai_detect_books_from_image(history_img_url)
    else:
        st.warning(f"📌 雲端硬碟中尚未找到【第 {target_y_num} 年 - 第 {target_w_num:02d} 週】的進度表圖片。")
        auto_detected_books = []

    st.divider()
    
    default_books = auto_detected_books if auto_detected_books else ["創世記"]
    
    st.markdown(f"### 📖 第 {target_y_num} 年 - 第 {target_w_num:02d} 週 導讀經文自動對應檢視")
    
    selected_books = st.multiselect(
        "✨ AI 已自動辨識本週對應經卷（可隨時手動增減）：",
        options=list(BOOK_CODE_MAP.keys()),
        default=default_books,
        key=f"books_sel_{target_y_num}_{target_w_num}"
    )

    view_mode = st.radio(
        "請選擇檢視模式：",
        ["📜 全週導讀總覽", "📅 按天切換閱讀 (Day 1 - Day 7)"],
        horizontal=True,
        key="hist_view_mode"
    )

    with st.spinner("正在從雲端硬碟對應編號抓取經卷導讀檔案中..."):
        full_doc_content = fetch_docx_content_by_books(selected_books)

    if not full_doc_content or "⚠️" in full_doc_content:
        st.warning(full_doc_content if full_doc_content else "💡 尚未找到對應的導讀檔案。")
    else:
        display_text = full_doc_content
        
        if view_mode == "📅 按天切換閱讀 (Day 1 - Day 7)":
            selected_day_label = st.selectbox(
                "選擇天數：",
                [f"第 {i} 天 (Day {i})" for i in range(1, 8)],
                key="hist_day_sel"
            )
            target_day_num = int(selected_day_label.split("第 ")[1].split(" 天")[0])
            
            lines = full_doc_content.split("\n")
            filtered_lines = []
            capturing = False
            found_any_day_tag = False
            
            for line in lines:
                l_lower = line.lower()
                if f"day {target_day_num}" in l_lower or f"第{target_day_num}天" in l_lower or f"day{target_day_num}" in l_lower:
                    found_any_day_tag = True
                    capturing = True
                    filtered_lines.append(line)
                    continue
                elif capturing:
                    if any(f"day {d}" in l_lower or f"第{d}天" in l_lower for d in range(1, 8) if d != target_day_num):
                        capturing = False
                    else:
                        filtered_lines.append(line)
            
            if found_any_day_tag and filtered_lines:
                display_text = "\n".join(filtered_lines)
            else:
                paragraphs = [p for p in full_doc_content.split("\n\n") if p.strip()]
                if len(paragraphs) >= 7:
                    chunk_size_p = max(1, len(paragraphs) // 7)
                    start_idx = (target_day_num - 1) * chunk_size_p
                    end_idx = start_idx + chunk_size_p if target_day_num < 7 else len(paragraphs)
                    display_text = f"💡 [提示：系統已自動為您擷取第 {target_day_num} 天對應段落]\n\n" + "\n\n".join(paragraphs[start_idx:end_idx])
                else:
                    display_text = full_doc_content

        st.markdown(
            f"""
            <div style="
                height: 480px; 
                overflow-y: scroll; 
                background-color: #f8f9fa; 
                padding: 20px; 
                border-radius: 12px; 
                border: 2px solid #cbd5e1;
                line-height: 1.8;
                font-size: 16px;
                color: #1e293b;
                white-space: pre-wrap;
                box-shadow: inset 0 2px 4px rgba(0,0,0,0.05);
            ">
                {display_text}
            </div>
            """,
            unsafe_allow_html=True
        )

# ------------------------------------------
# TAB 3: 後台統計與管理
# ------------------------------------------
with tab_admin:
    st.subheader("🔒 管理者控制台")
    pwd = st.text_input("請輸入管理者密碼：", type="password")

    if pwd == ADMIN_PASSWORD:
        st.success("🔓 驗證成功，歡迎進入後台管理系統！")

        admin_sub_tab1, admin_sub_tab2 = st.tabs([
            "📊 簽到進度總覽與匯出", 
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
            st.markdown("### 👥 管理會友名單")
            st.write("可在下方文字框中新增或修改會友姓名（每行一位）：")

            current_m_text = "\n".join(member_list)
            new_m_text = st.text_area("會友名單列表：", value=current_m_text, height=350)

            if st.button("💾 儲存名單變更"):
                updated_names = [name.strip() for name in new_m_text.split("\n") if name.strip()]
                save_members(updated_names)
                st.success("🎉 會友名單更新成功！")
                st.rerun()
