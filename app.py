import streamlit as st
import pandas as pd
import datetime
import os
import logging
import gspread
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

# 設定 Logging 紀錄
logging.basicConfig(level=logging.INFO)

# ==========================================
# 1. 基礎設定與常數
# ==========================================
MEMBERS_FILE = "church_members.csv"
VERSES_FILE = "verses.csv"
ATTENDANCE_FILE = "attendance_records.csv"

ADMIN_PASSWORD = st.secrets.get("admin_password", "11190928")
PLAN_YEAR = 2

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

def init_gspread_client():
    """初始化 gspread 客戶端以操作 Google 試算表"""
    creds = get_gcp_credentials()
    if creds:
        return gspread.authorize(creds)
    return None

# ==========================================
# 3. 雲端導讀經文讀取函式
# ==========================================
def load_verses_from_cloud():
    """
    從 Google 雲端硬碟（Google 試算表）讀取導讀經文。
    若讀取失敗或無設定，則退回到本地讀取 VERSES_FILE。
    """
    try:
        client = init_gspread_client()
        if client and "google_sheet_name" in st.secrets:
            sheet_name = st.secrets["google_sheet_name"]
            # 假設經文資料放在名為 "verses" 或對應的工作表中
            sh = client.open(sheet_name)
            try:
                worksheet = sh.worksheet("verses")
            except Exception:
                worksheet = sh.get_worksheet(0) # 預設取第一個分頁
                
            data = worksheet.get_all_records()
            if data:
                return pd.DataFrame(data)
    except Exception as e:
        logging.warning(f"從雲端讀取導讀經文失敗，改用本地檔案: {e}")
        
    # 本地備援讀取
    if os.path.exists(VERSES_FILE):
        return pd.read_csv(VERSES_FILE)
    else:
        # 若本地也沒有，回傳空的 DataFrame 避免報錯
        return pd.DataFrame(columns=["week", "verse", "commentary"])

# ==========================================
# 4. 簽到二次確認彈窗
# ==========================================
@st.dialog("簽到確認")
def confirm_checkin_dialog(member_name, week_display, week_key, missing_weeks):
    st.markdown(f"👉 確定要為 **{member_name}** 辦理 **{week_display}** 的簽到嗎？")
    
    if missing_weeks:
        st.info(f"💡 系統將一併自動為您補簽過往未簽到的 **{len(missing_weeks)}** 週進度！")
        
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 確定簽到", type="primary", use_container_width=True):
            # 彙整當週與過往未簽週數
            records_to_add = [(week_key, member_name)]
            for m_item in missing_weeks:
                records_to_add.append((m_item["key"], member_name))
            
            # 寫入簽到紀錄 (請確保您的專案中有定義 add_batch_records 函式)
            # add_batch_records(records_to_add)
            
            if missing_weeks:
                st.toast(f"🎉 簽到成功！已一併補齊過往 {len(missing_weeks)} 週進度！")
            else:
                st.toast("🎉 簽到成功！")
                
            st.session_state.scroll_target = "divider-top-anchor"
            st.rerun()
            
    with col2:
        if st.button("❌ 取消", type="secondary", use_container_width=True):
            st.rerun()

# ==========================================
# 5. 主程式載入測試範例
# ==========================================
def main():
    st.title("📖 四年精讀聖經運動簽到系統")
    
    # 測試載入雲端經文
    st.subheader("本週導讀經文預覽")
    df_verses = load_verses_from_cloud()
    if not df_verses.empty:
        st.dataframe(df_verses, use_container_width=True)
    else:
        st.warning("目前尚無經文資料或尚未設定雲端連結。")

if __name__ == "__main__":
    main()
