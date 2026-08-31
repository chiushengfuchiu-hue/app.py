import io
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

  st.info(f"尚無【{week_key}】的進度表圖片。")
