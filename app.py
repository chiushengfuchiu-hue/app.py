import datetime
import logging
import os
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

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
    "周寶燕",
    "曾笑",
    "黃然玉",
    "吳妃玉",
    "楊游美麗",
    "翁淑美",
    "石美莎",
    "單麗蘭",
    "鄭富美",
    "李鶯芳",
    "趙文崇",
    "李應昌",
    "賴健文",
    "林春妙",
    "邱文雀",
    "梁垠盤",
    "陳宜宏",
    "郭彩梅",
    "林春桃",
    "鳳姐",
    "黃敏生",
    "吳秀卉",
    "陳安俐",
    "程乃珍",
    "蕭慧麗",
    "蔡慧俐",
    "林雅谷",
    "李俊修",
    "林淑惠",
    "盧正亮",
    "翁春祝",
    "劉淑珠",
    "葉雅雲",
    "林雅音",
    "趙文川",
    "邱聖富",
]

st.set_page_config(
    page_title="四年精讀聖經運動簽到系統", page_icon="📖", layout="wide"
)


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

  df_new = df[
      ~((df["week_key"] == week_key) & (df["member_name"] == member_name))
  ]
  save_attendance(df_new)
  return True


def sync_to_gsheet_async(new_rows_list):
  try:
    if "gcp_service_account" not in st.secrets:
      return
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
    new_row = pd.DataFrame([{
        "week_key": week_key,
        "member_name": member_name,
        "timestamp": now_str,
    }])
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
  pd.DataFrame({"member_name": members_list}).to_csv(
      MEMBERS_FILE, index=False, encoding="utf-8-sig"
  )


def get_weekly_verse(week_num):
  fallback = {
      "verse": "「你的話是我腳前的燈，是我路上的光。」",
      "ref": "詩篇 119:105",
      "encouragement": "讓上帝的話語成為你每日的亮光與引導！",
  }
  if os.path.exists(VERSES_FILE):
    try:
      v_df = pd.read_csv(VERSES_FILE)
      if not v_df.empty:
        row = v_df.iloc[(week_num - 1) % len(v_df)]
        return {
            "verse": str(row["verse"]),
            "ref": str(row["ref"]),
            "encouragement": str(row.get("encouragement", "")),
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
        if os.path.exists(img_path):
          return img_path
    except Exception:
      pass
  return None


def save_schedule_record(week_key, uploaded_file):
  file_extension = uploaded_file.name.split(".")[-1]
  file_path = os.path.join(SCHEDULE_DIR, f"{week_key}.{file_extension}")
  with open(file_path, "wb") as f:
    f.write(uploaded_file.getbuffer())
  df_s = (
      pd.read_csv(SCHEDULE_RECORD_FILE)
      if os.path.exists(SCHEDULE_RECORD_FILE)
      else pd.DataFrame(columns=["week_key", "image_path"])
  )
  df_s = df_s[df_s["week_key"] != week_key]
  df_s = pd.concat(
      [df_s, pd.DataFrame([{"week_key": week_key, "image_path": file_path}])],
      ignore_index=True,
  )
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
  is_sunday = now.weekday() == 6
  calc_date = now + datetime.timedelta(days=1) if is_sunday else now
  current_week_num = calc_date.isocalendar()[1]
  return f"Y{PLAN_YEAR}-W{current_week_num:02d}", current_week_num


def generate_pivot_report(target_year, start_w, end_w):
  df_att = load_attendance()
  members = load_members()["member_name"].tolist()

  report_data = []
  week_cols = [f"Y{target_year}-W{w:02d}" for w in range(start_w, end_w + 1)]
  total_weeks = len(week_cols)

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

    row["完成週數"] = f"{completed_count} / {total_weeks}"
    row["完成率"] = (
        f"{(completed_count / total_weeks * 100):.2f}%"
        if total_weeks > 0
        else "0.00%"
    )
    report_data.append(row)

  df_report = pd.DataFrame(report_data)
  cols_order = ["member_name", "完成週數", "完成率"] + week_cols
  return df_report[cols_order]


# ==========================================
# 3. CSS 樣式美化
# ==========================================
st.markdown(
    """
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
""",
    unsafe_allow_html=True,
)

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

tab_user, tab_history, tab_admin = st.tabs(
    ["✍️ 會友簽到專區", "🗓️ 過往進度查詢", "🔒 後台統計管理"]
)

# ------------------------------------------
# TAB 1: 會友簽到區
# ------------------------------------------
with tab_user:
  current_img_path = get_schedule_image_path(current_week_key)
  if current_img_path:
    st.image(
        current_img_path,
        caption=f"【最新進度】{current_week_display}",
        use_container_width=True,
    )
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
  # 情況 A：未選擇會友（顯示分區圖框）
  # --------------------------------------
  if st.session_state.current_member is None:
    st.markdown("<div id='members-list-top'></div>", unsafe_allow_html=True)
    st.markdown("### 👇 請點擊您所屬的分區展開名字列表：")

    valid_members = [
        m
        for m in member_list
        if m and str(m).strip() and not str(m).startswith("會友")
    ]

    chunk_size = 10
    total_valid = len(valid_members)

    for i in range(0, total_valid, chunk_size):
      chunk = valid_members[i : i + chunk_size]
      page_num = (i // chunk_size) + 1

      if chunk:
        names_text = "、".join(chunk)
        is_this_open = st.session_state.open_section == page_num

        toggle_icon = "🔽" if is_this_open else "▶️"
        header_label = f"{toggle_icon} 📦 【第 {page_num} 區】 {names_text}"

        if st.button(
            header_label,
            key=f"sec_toggle_{page_num}",
            type="secondary",
            use_container_width=True,
        ):
          if is_this_open:
            st.session_state.open_section = None
          else:
            st.session_state.open_section = page_num
            st.session_state.scroll_target = f"line-anchor-{page_num}"
          st.rerun()

        if is_this_open:
          st.markdown(
              f"<div id='line-anchor-{page_num}'></div>", unsafe_allow_html=True
          )
          st.divider()

          col1, col2 = st.columns(2)
          mid = (len(chunk) + 1) // 2

          with col1:
            for name in chunk[:mid]:
              is_signed = not df_attendance[
                  (df_attendance["week_key"] == current_week_key)
                  & (df_attendance["member_name"] == name)
              ].empty
              status_icon = "✅" if is_signed else "👤"
              if st.button(
                  f"{status_icon} {name}",
                  key=f"btn_dyn_{page_num}_{name}",
                  type="secondary",
                  use_container_width=True,
              ):
                st.session_state.current_member = name
                st.session_state.scroll_target = "divider-top-anchor"
                st.rerun()

          with col2:
            for name in chunk[mid:]:
              is_signed = not df_attendance[
                  (df_attendance["week_key"] == current_week_key)
                  & (df_attendance["member_name"] == name)
              ].empty
              status_icon = "✅" if is_signed else "👤"
              if st.button(
                  f"{status_icon} {name}",
                  key=f"btn_dyn_{page_num}_{name}",
                  type="secondary",
                  use_container_width=True,
              ):
                st.session_state.current_member = name
                st.session_state.scroll_target = "divider-top-anchor"
                st.rerun()

  # --------------------------------------
  # 情況 B：已選擇會友（個人簽到頁）
  # --------------------------------------
  else:
    member_name = st.session_state.current_member

    if st.button(
        "⬅️ 返回選擇名字列表", type="secondary", use_container_width=True
    ):
      st.session_state.current_member = None
      current_sec = st.session_state.open_section
      if current_sec:
        st.session_state.scroll_target = f"line-anchor-{current_sec}"
      else:
        st.session_state.scroll_target = "members-list-top"
      st.rerun()

    st.markdown(f"## 👤 {member_name} 的讀經專頁")
    st.markdown(f"### 📍 【本週進度】{current_week_display}")

    is_signed = not df_attendance[
        (df_attendance["week_key"] == current_week_key)
        & (df_attendance["member_name"] == member_name)
    ].empty

    if is_signed:
      st.success(
          f"🎉 **{member_name}**，您已完成本週讀經進度，願主保守力上加力恩上加恩！"
      )
    else:
      if st.button(
          f"🟢 若完成【{current_week_display}】請按此簽到",
          type="primary",
          use_container_width=True,
      ):
        add_single_record(current_week_key, member_name)
        st.toast("🎉 簽到成功！")
        st.session_state.scroll_target = "divider-top-anchor"
        st.rerun()

    st.divider()
    st.markdown("### 🟡 【補簽未完成進度】")

    signed_weeks = df_attendance[
        df_attendance["member_name"] == member_name
    ]["week_key"].tolist()

    missing_weeks_info = []
    for w in range(1, current_week_num):
      w_key = f"Y{PLAN_YEAR}-W{w:02d}"
      w_display = f"第 {PLAN_YEAR} 年 - 第 {w:02d} 週"
      if w_key not in signed_weeks:
        missing_weeks_info.append({"key": w_key, "display": w_display})

    if missing_weeks_info:
      st.warning(
          f"📌 共有 **{len(missing_weeks_info)}** 週尚未完成，點擊按鈕補簽："
      )
      mid_m = (len(missing_weeks_info) + 1) // 2

      mc1, mc2 = st.columns(2)
      with mc1:
        for item in missing_weeks_info[:mid_m]:
          if st.button(
              f"🟡 {item['display']}",
              key=f"miss_{member_name}_{item['key']}",
              type="secondary",
              use_container_width=True,
          ):
            add_single_record(item["key"], member_name)
            st.toast(f"✅ 已成功補簽 `{item['display']}`！")
            st.session_state.scroll_target = "divider-top-anchor"
            st.rerun()
      with mc2:
        for item in missing_weeks_info[mid_m:]:
          if st.button(
              f"🟡 {item['display']}",
              key=f"miss_{member_name}_{item['key']}",
              type="secondary",
              use_container_width=True,
          ):
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
  if verse_info.get("encouragement"):
    st.markdown(f"💬 **心靈補給**：{verse_info['encouragement']}")

# ------------------------------------------
# TAB 2: 過往讀經進度查詢
# ------------------------------------------
with tab_history:
  st.markdown("### 🗓️ 歷史讀經進度表查詢")

  col_y, col_w = st.columns([1, 2])
  with col_y:
    selected_year = st.selectbox(
        "請選擇年份：",
        [f"第 {y} 年 (Y{y})" for y in range(PLAN_YEAR, 0, -1)],
        index=0,
    )
    target_y_num = int(selected_year.split("第 ")[1].split(" 年")[0])

  with col_w:
    max_w_display = current_week_num if target_y_num == PLAN_YEAR else 52
    week_options = [f"第 {w:02d} 週" for w in range(max_w_display, 0, -1)]
    selected_w_label = st.selectbox("請選擇週數：", week_options, index=0)
    target_w_num = int(selected_w_label.replace("第 ", "").replace(" 週", ""))

  selected_week_key = f"Y{target_y_num}-W{target_w_num:02d}"
  selected_img_path = get_schedule_image_path(selected_week_key)

  if selected_img_path:
    st.image(
        selected_img_path,
        caption=f"【第 {target_y_num} 年 - 第 {target_w_num:02d} 週】進度對照表",
        use_container_width=True,
    )
  else:
    st.warning(
        f"📌 目前尚未上傳【Y{target_y_num}-W{target_w_num:02d}】的進度表圖片。"
    )

# ------------------------------------------
# TAB 3: 後台統計與管理
# ------------------------------------------
with tab_admin:
  st.subheader("🔒 管理者控制台")
  pwd = st.text_input("請輸入管理者密碼：", type="password")

  if pwd == ADMIN_PASSWORD:
    st.success("🔓 驗證成功，歡迎進入後台管理系統！")

    admin_sub_tab1, admin_sub_tab2, admin_sub_tab3 = st.tabs(
        ["📊 簽到進度總覽與匯出", "🗓️ 上傳進度表圖片", "👥 會友名單編輯"]
    )

    # Sub-tab 3-1: 統計總覽與匯出
    with admin_sub_tab1:
      st.markdown("### 📊 全會友讀經簽到進度總表")

      time_range = st.selectbox(
          "📅 請選擇匯出與統計時間區間：",
          [
              "最近 4 週",
              "第一季 (W01~W13)",
              "第二季 (W14~W26)",
              "第三季 (W27~W39)",
              "第四季 (W40~W52)",
              "上半年 (W01~W26)",
              "全年度 (W01~W52)",
          ],
      )

      # 算起訖週數
      if time_range == "最近 4 週":
        start_w = max(1, current_week_num - 3)
        end_w = current_week_num
      elif time_range == "第一季 (W01~W13)":
        start_w, end_w = 1, 13
      elif time_range == "第二季 (W14~W26)":
        start_w, end_w = 14, 26
      elif time_range == "第三季 (W27~W39)":
        start_w, end_w = 27, 39
      elif time_range == "第四季 (W40~W52)":
        start_w, end_w = 40, 52
      elif time_range == "上半年 (W01~W26)":
        start_w, end_w = 1, 26
      else:
        start_w, end_w = 1, 52

      df_pivot = generate_pivot_report(PLAN_YEAR, start_w, end_w)
      st.dataframe(df_pivot, use_container_width=True)

      # 下載功能
      csv_data = df_pivot.to_csv(index=False, encoding="utf-8-sig").encode(
          "utf-8-sig"
      )
      st.download_button(
          label="📥 下載簽到統計表 (CSV)",
          data=csv_data,
          file_name=f"church_attendance_Y{PLAN_YEAR}_W{start_w:02d}-W{end_w:02d}.csv",
          mime="text/csv",
      )

    # Sub-tab 3-2: 上傳跨年進度表圖片
    with admin_sub_tab2:
      st.markdown("### 🗓️ 上傳/更新進度表圖片")
      c1, c2 = st.columns(2)
      with c1:
        up_year = st.number_input(
            "年份", min_value=1, max_value=4, value=PLAN_YEAR
        )
      with c2:
        up_week = st.number_input(
            "週數", min_value=1, max_value=52, value=current_week_num
        )

      target_up_key = f"Y{up_year}-W{up_week:02d}"
      uploaded_file = st.file_uploader(
          f"請選擇 【{target_up_key}】 的進度圖檔 (JPG/PNG)",
          type=["png", "jpg", "jpeg"],
      )

      if uploaded_file is not None:
        if st.button(f"📤 確認上傳 {target_up_key} 圖片", type="primary"):
          save_schedule_record(target_up_key, uploaded_file)
          st.success(f"🎉 【{target_up_key}】進度圖片已成功更新！")
          st.rerun()

    # Sub-tab 3-3: 會友名單編輯
    with admin_sub_tab3:
      st.markdown("### 👥 會友名單管理")
      df_curr_m = load_members()
      curr_m_list = df_curr_m["member_name"].tolist()

      st.markdown("#### ➕ 新增會友")
      new_member_name = st.text_input("請輸入新會友姓名：").strip()
      if st.button("確認新增"):
        if new_member_name and new_member_name not in curr_m_list:
          curr_m_list.append(new_member_name)
          save_members(curr_m_list)
          st.success(f"已成功新增會友：{new_member_name}")
          st.rerun()
        elif new_member_name in curr_m_list:
          st.warning("該會友姓名已存在！")

      st.divider()
      st.markdown("#### ❌ 刪除會友")
      del_member_name = st.selectbox(
          "請選擇要移除的會友：", ["-- 請選擇 --"] + curr_m_list
      )
      if (
          del_member_name != "-- 請選擇 --"
          and st.button(f"確認刪除 {del_member_name}")
      ):
        curr_m_list.remove(del_member_name)
        save_members(curr_m_list)
        st.success(f"已移除會友：{del_member_name}")
        st.rerun()
