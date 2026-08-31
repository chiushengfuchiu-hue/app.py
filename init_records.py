import pandas as pd
import datetime
import os
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# 檔案名稱設定
ATTENDANCE_FILE = "attendance_records.csv"

# ==========================================
# 1. 解析三張報表中的完整簽到矩陣
# ==========================================
# 所有成員名單 (依據圖片順序)
members = [
    "周寶燕", "曾笑", "黃然玉", "吳妃玉", "楊游美麗", 
    "翁淑美", "石美莎", "單麗蘭", "鄭富美", "李鶯芳", 
    "趙文崇", "李應昌", "賴健文", "林春妙", "邱文雀", 
    "梁垠盤", "陳宜宏", "郭彩梅", "林春桃", "鳳姐", 
    "黃敏生", "吳秀卉", "陳安俐", "程乃珍", "蕭慧麗", 
    "蔡慧俐", "林雅谷", "李俊修", "林淑惠", "盧正亮", 
    "翁春祝", "劉淑珠", "葉雅雲", "林雅音", "趙文川",
    "邱聖富", "林秀鳳", "陳文智"
]

# 定義每位會友「未簽到 (打叉 ❌)」的週數清單 (Y2-W01 ~ Y2-W35)
# 只要不在這個字典裡的週數，預設全部為「已簽到 ⚪ 已讀」
exceptions = {
    "李鶯芳": [31, 33, 34, 35],
    "李應昌": [34, 35],
    "賴健文": [33, 34, 35],
    "林春妙": [34, 35],
    "邱文雀": [34, 35],
    "梁垠盤": [35],
    "陳宜宏": [35],
    "郭彩梅": [34, 35],
    "林春桃": [34, 35],
    "鳳姐": [35],
    "黃敏生": [34, 35],
    "吳秀卉": [35],
    "陳安俐": list(range(28, 36)),  # W28 ~ W35 缺
    "程乃珍": [34, 35],
    "蕭慧麗": [35],
    "蔡慧俐": [35],
    "林雅谷": [35],
    "李俊修": [35],
    "林淑惠": [25, 26] + list(range(27, 36)),  # W25, W26, W27~W35 缺
    "盧正亮": [35],
    "翁春祝": [35],
    "劉淑珠": [35],
    "葉雅雲": [34, 35],
    "林雅音": list(range(22, 36)),  # W22 ~ W35 缺
    "趙文川": [5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26] + list(range(27, 36)),
    "邱聖富": [35],
    "林秀鳳": [22, 23, 24, 25, 26] + list(range(27, 36)),  # W22 ~ W35 缺
    "陳文智": [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26] + list(range(27, 36))  # W16 ~ W35 缺
}

# ==========================================
# 2. 產生完整的紀錄資料表
# ==========================================
records = []
init_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for m in members:
    m_missing = exceptions.get(m, [])
    for w in range(1, 36):  # W01 ~ W35
        if w not in m_missing:
            records.append({
                "week_key": f"Y2-W{w:02d}",
                "member_name": m,
                "timestamp": init_timestamp
            })

df_new = pd.DataFrame(records)

# 寫入本地 CSV 檔案
df_new.to_csv(ATTENDANCE_FILE, index=False, encoding="utf-8-sig")
print(f"✅ 本地 CSV 紀錄檔初始化完成，共建立 {len(df_new)} 筆簽到資料！")

# ==========================================
# 3. 同步寫入 Google Sheets (若有設定 secrets)
# ==========================================
try:
    if "gcp_service_account" in st.secrets:
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

        # 清空舊資料並重設表頭
        sheet.clear()
        sheet.append_row(["week_key", "member_name", "timestamp"])

        # 批次寫入所有初始資料
        rows_to_append = [[r["week_key"], r["member_name"], r["timestamp"]] for r in records]
        sheet.append_rows(rows_to_append)
        print("✅ Google Sheets 雲端同步完成！")
except Exception as e:
    print(f"⚠️ Google Sheets 同步過程發生提醒/跳過（本地資料已建置完成）: {e}")
