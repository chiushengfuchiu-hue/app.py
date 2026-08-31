import os
import threading
import logging
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 設定與檔案路徑
# ==========================================
ATTENDANCE_FILE = "attendance_records.csv"
MEMBER_FILE = "members.csv"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ==========================================
# Google Sheets 服務帳號連接
# ==========================================
def get_gspread_client():
    """取得授權的 gspread client"""
    if "gcp_service_account" not in st.secrets:
        logging.warning("未設定 secrets.gcp_service_account，無法連線至 Google Sheets")
        return None
    try:
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
            
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        logging.error(f"Google Sheets 認證授權失敗: {e}")
        return None

def sync_to_gsheet_async(week_key, member_name, timestamp):
    """背景非同步寫入單筆紀錄至 Google Sheets"""
    def _sync():
        try:
            client = get_gspread_client()
            if client:
                sheet_name = st.secrets.get("spreadsheet_name", "Church_Attendance")
                sheet = client.open(sheet_name).sheet1
                sheet.append_row([str(week_key), str(member_name), str(timestamp)])
                logging.info(f"成功同步寫入 Google Sheets: {week_key}, {member_name}")
        except Exception as e:
            logging.error(f"同步寫入 Google Sheets 失敗: {e}")

    thread = threading.Thread(target=_sync)
    thread.start()

def delete_from_gsheet_async(week_key, member_name):
    """背景非同步從 Google Sheets 刪除單筆紀錄"""
    def _delete():
        try:
            client = get_gspread_client()
            if client:
                sheet_name = st.secrets.get("spreadsheet_name", "Church_Attendance")
                sheet = client.open(sheet_name).sheet1
                cell_list = sheet.findall(str(member_name).strip())
                for cell in cell_list:
                    row_vals = sheet.row_values(cell.row)
                    if len(row_vals) >= 2 and row_vals[0].strip() == str(week_key).strip() and row_vals[1].strip() == str(member_name).strip():
                        sheet.delete_rows(cell.row)
                        logging.info(f"成功從 Google Sheets 刪除: {week_key}, {member_name}")
                        break
        except Exception as e:
            logging.error(f"從 Google Sheets 刪除紀錄失敗: {e}")

    thread = threading.Thread(target=_delete)
    thread.start()

# ==========================================
# 資料讀寫邏輯 (CSV & Google Sheets)
# ==========================================
def save_attendance(df):
    """儲存資料至本地 CSV 備份"""
    try:
        df.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8-sig")
    except Exception as e:
        logging.error(f"寫入本地 CSV 失敗: {e}")

def load_attendance():
    """優先從 Google Sheets 讀取歷史簽到資料，失敗時降級讀取本地 CSV"""
    try:
        client = get_gspread_client()
        if client:
            sheet_name = st.secrets.get("spreadsheet_name", "Church_Attendance")
            sheet = client.open(sheet_name).sheet1
            data = sheet.get_all_values()
            
            if data and len(data) > 0:
                # 判斷有無標頭列
                if data[0][0] in ["week_key", "週次", "Week"]:
                    df = pd.DataFrame(data[1:], columns=data[0])
                else:
                    df = pd.DataFrame(data, columns=["week_key", "member_name", "timestamp"])
                
                df.columns = [str(c).strip() for c in df.columns]
                for col in ["week_key", "member_name", "timestamp"]:
                    if col in df.columns:
                        df[col] = df[col].astype(str).str.strip()
                    else:
                        df[col] = ""
                
                # 更新同步至本地 CSV 備份
                save_attendance(df)
                return df
    except Exception as e:
        logging.error(f"從 Google Sheets 載入資料失敗，降級使用本地 CSV: {e}")

    # 本地 CSV 備份
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
            logging.error(f"讀取本地 CSV 簽到檔失敗: {e}")

    return pd.DataFrame(columns=["week_key", "member_name", "timestamp"])

def add_single_record(week_key, member_name, timestamp):
    """新增單筆簽到紀錄"""
    week_key = str(week_key).strip()
    member_name = str(member_name).strip()
    timestamp = str(timestamp).strip()

    df = load_attendance()
    # 避免重複簽到
    exists = df[(df["week_key"] == week_key) & (df["member_name"] == member_name)]
    if not exists.empty:
        return False, "已存在簽到紀錄"

    new_row = pd.DataFrame([{"week_key": week_key, "member_name": member_name, "timestamp": timestamp}])
    df = pd.concat([df, new_row], ignore_index=True)
    save_attendance(df)

    # 異步寫入 Google Sheets
    sync_to_gsheet_async(week_key, member_name, timestamp)
    return True, "簽到成功"

def delete_single_record(week_key, member_name):
    """刪除單筆簽到紀錄"""
    week_key = str(week_key).strip()
    member_name = str(member_name).strip()

    df = load_attendance()
    df_new = df[~((df["week_key"] == week_key) & (df["member_name"] == member_name))]
    save_attendance(df_new)

    # 異步從 Google Sheets 刪除
    delete_from_gsheet_async(week_key, member_name)
    return True

# ==========================================
# 會友名單載入
# ==========================================
def load_members():
    """載入會友名單 CSV"""
    if os.path.exists(MEMBER_FILE):
        try:
            df = pd.read_csv(MEMBER_FILE)
            if "name" in df.columns:
                return df["name"].dropna().astype(str).str.strip().tolist()
        except Exception as e:
            logging.error(f"讀取會友名單失敗: {e}")
    return []

# ==========================================
# Streamlit UI 介面設計
# ==========================================
def main():
    st.set_page_config(page_title="團契/小組出席簽到系統", page_icon="⛪", layout="wide")
    st.title("⛪ 團契/小組出席簽到系統")

    # 載入資料
    members = load_members()
    df_attendance = load_attendance()

    # 選擇週次
    st.sidebar.header("🗓️ 週次設定")
    selected_week = st.sidebar.text_input("輸入週次名稱或日期 (例: 2026-W35 或 0831)", value="2026-W35")

    tab1, tab2 = st.tabs(["📝 會友簽到", "📊 出席總覽與管理"])

    # --------------------------------------
    # Tab 1: 會友簽到頁面
    # --------------------------------------
    with tab1:
        st.subheader(f"📍 當前簽到週次：{selected_week}")
        
        if not members:
            st.warning("請先在同目錄下建立 `members.csv` 並加入 `name` 欄位以載入會友名單。")
        else:
            # 找出本週已簽到的人
            checked_members = df_attendance[df_attendance["week_key"] == str(selected_week)]["member_name"].tolist()
            
            st.write("### 點擊姓名進行簽到：")
            cols = st.columns(4) # 每排顯示 4 個按鈕
            for idx, member in enumerate(members):
                col = cols[idx % 4]
                is_checked = member in checked_members
                
                if is_checked:
                    col.button(f"✅ {member} (已簽到)", key=f"btn_{member}", disabled=True)
                else:
                    if col.button(f"➕ {member}", key=f"btn_{member}"):
                        now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
                        success, msg = add_single_record(selected_week, member, now_str)
                        if success:
                            st.success(f"{member} 簽到成功！")
                            st.rerun()
                        else:
                            st.error(msg)

    # --------------------------------------
    # Tab 2: 管理員/出席紀錄頁面
    # --------------------------------------
    with tab2:
        st.subheader("📋 簽到總覽與紀錄管理")
        
        df_current = df_attendance[df_attendance["week_key"] == str(selected_week)]
        
        col_stat1, col_stat2 = st.columns(2)
        col_stat1.metric("總人數", f"{len(members)} 人")
        col_stat2.metric("本週出席人數", f"{len(df_current)} 人")

        st.markdown("---")
        st.write(f"#### 📅 {selected_week} 已簽到名單：")

        if df_current.empty:
            st.info("本週尚無簽到紀錄。")
        else:
            for idx, row in df_current.iterrows():
                m_name = row["member_name"]
                t_stamp = row.get("timestamp", "")
                
                c1, c2, c3 = st.columns([2, 3, 1])
                c1.write(f"👤 **{m_name}**")
                c2.write(f"🕒 {t_stamp}")
                if c3.button("撤銷/刪除", key=f"del_{selected_week}_{m_name}"):
                    delete_single_record(selected_week, m_name)
                    st.success(f"已刪除 {m_name} 的簽到紀錄！")
                    st.rerun()

        st.markdown("---")
        with st.expander("🔍 檢視完整歷史 CSV 數據"):
            st.dataframe(df_attendance, use_container_width=True)

if __name__ == "__main__":
    main()
