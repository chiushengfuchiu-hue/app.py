import streamlit as st
import pandas as pd
import datetime
import os

# ==========================================
# 1. 檔案與預設設定
# ==========================================
DATA_FILE = "church_attendance.csv"
MEMBERS_FILE = "church_members.csv"
VERSES_FILE = "verses.csv"
SCHEDULE_RECORD_FILE = "schedule_records.csv"  # 記錄週別與對應圖片檔名的對照表
SCHEDULE_DIR = "schedules_img"                 # 儲存進度圖的資料夾
ADMIN_PASSWORD = "church_admin"                # 後台密碼

# 4年讀經計畫設定：今年為第 2 年
PLAN_YEAR = 2 

# 確保圖片儲存資料夾存在
os.makedirs(SCHEDULE_DIR, exist_ok=True)

# 圖片辨識出的 34 位真實名單底稿
INITIAL_MEMBERS = [
    "周寶燕", "曾笑", "黃然玉", "吳妃玉", "楊游美麗", 
    "翁淑美", "石美莎", "單麗蘭", "鄭富美", "李鶯芳", 
    "趙文崇", "李應昌", "賴健文", "林春妙", "邱文雀", 
    "梁垠盤", "陳宜宏", "郭彩梅", "林春桃", "鳳姐", 
    "黃敏生", "吳秀卉", "陳安俐", "程乃珍", "蕭慧麗", 
    "蔡慧俐", "林雅谷", "李俊修", "林淑惠", "盧正亮", 
    "林雅音", "劉淑珠", "葉雅雲", "趙文川"
]

st.set_page_config(page_title="教會4年讀經計畫簽到系統", page_icon="📖", layout="wide")

# ==========================================
# CSS 響應式與字體自適應修正
# ==========================================
st.markdown("""
    <style>
    html, body {
        max-width: 100vw;
        overflow-x: hidden;
    }

    h1 {
        font-size: clamp(22px, 6vw, 32px) !important;
        line-height: 1.3 !important;
        word-break: break-word !important;
        padding-top: 0.2rem !important;
        padding-bottom: 0.5rem !important;
    }
    
    div[data-testid="stButton"] button {
        width: 100% !important;
        white-space: normal !important;
        word-break: break-word !important;
        line-height: 1.2 !important;
        box-sizing: border-box !important;
    }

    div[data-testid="stButton"] button p {
        font-size: clamp(18px, 5vw, 26px) !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
        margin: 0 !important;
        padding: 2px 0 !important;
    }

    div[data-testid="stButton"] button[kind="secondary"] {
        min-height: 3em !important;
        height: auto !important;
        padding: 8px 6px !important;
        border-radius: 12px !important;
        border: 2px solid #0284C7 !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.06) !important;
        margin-bottom: 8px !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background-color: #E0F2FE !important;
        border-color: #0369A1 !important;
    }

    div[data-testid="stButton"] button:disabled {
        background-color: #F1F5F9 !important;
        border: 2px dashed #94A3B8 !important;
        box-shadow: none !important;
        cursor: not-allowed !important;
    }
    div[data-testid="stButton"] button:disabled p {
        color: #94A3B8 !important;
        font-size: clamp(14px, 4vw, 20px) !important;
        font-weight: normal !important;
    }

    div[data-testid="stButton"] button[kind="primary"] {
        min-height: 3.2em !important;
        height: auto !important;
        padding: 8px 12px !important;
        border-radius: 12px !important;
        border: none !important;
        background-color: #059669 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.15) !important;
        margin-bottom: 8px !important;
    }
    div[data-testid="stButton"] button[kind="primary"] p {
        color: #FFFFFF !important;
        font-size: clamp(20px, 6vw, 30px) !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background-color: #047857 !important;
    }

    div[data-testid="stRadio"] label p {
        font-size: clamp(16px, 4.5vw, 20px) !important;
        font-weight: bold !important;
    }

    @media (max-width: 360px) {
        h1 {
            font-size: 20px !important;
        }
        div[data-testid="stButton"] button p {
            font-size: 18px !important;
        }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 資料處理函式
# ==========================================
def load_members():
    default_members = list(INITIAL_MEMBERS)
    for i in range(len(INITIAL_MEMBERS), 50):
        default_members.append(f"會友 {i+1:02d}")
        
    need_reset = False
    if os.path.exists(MEMBERS_FILE):
        try:
            df_m = pd.read_csv(MEMBERS_FILE)
            current_names = df_m["member_name"].tolist() if not df_m.empty else []
            if "會友 01" in current_names or len(current_names) < 34:
                need_reset = True
        except Exception:
            need_reset = True
    else:
        need_reset = True

    if need_reset:
        df_m = pd.DataFrame({"member_name": default_members})
        df_m.to_csv(MEMBERS_FILE, index=False, encoding="utf-8-sig")
        return df_m
    else:
        return df_m

def save_members(members_list):
    df_m = pd.DataFrame({"member_name": members_list})
    df_m.to_csv(MEMBERS_FILE, index=False, encoding="utf-8-sig")

def update_member_name(old_name, new_name):
    df_m = load_members()
    df_m["member_name"] = df_m["member_name"].replace(old_name, new_name)
    df_m.to_csv(MEMBERS_FILE, index=False, encoding="utf-8-sig")
    
    if os.path.exists(DATA_FILE):
        df_a = pd.read_csv(DATA_FILE)
        if not df_a.empty:
            df_a["member_name"] = df_a["member_name"].replace(old_name, new_name)
            df_a.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

def load_attendance():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    else:
        return pd.DataFrame(columns=["week_key", "member_name", "timestamp"])

def save_record(week_key, member_name):
    df = load_attendance()
    mask = (df["week_key"] == week_key) & (df["member_name"] == member_name)
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not mask.any():
        new_data = pd.DataFrame([{
            "week_key": week_key,
            "member_name": member_name,
            "timestamp": timestamp_str
        }])
        df = pd.concat([df, new_data], ignore_index=True)
        df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")
        return True
    return False

def get_weekly_verse(week_num):
    fallback = {"verse": "「你的話是我腳前的燈，是我路上的光。」", "ref": "詩篇 119:105"}
    if os.path.exists(VERSES_FILE):
        try:
            v_df = pd.read_csv(VERSES_FILE)
            if not v_df.empty:
                idx = (week_num - 1) % len(v_df)
                row = v_df.iloc[idx]
                return {"verse": str(row["verse"]), "ref": str(row["ref"])}
        except Exception:
            pass
    return fallback

# 進度圖管理相關函式
def get_schedule_image_path(week_key):
    if os.path.exists(SCHEDULE_RECORD_FILE):
        df_s = pd.read_csv(SCHEDULE_RECORD_FILE)
        match = df_s[df_s["week_key"] == week_key]
        if not match.empty:
            img_path = match.iloc[0]["image_path"]
            if os.path.exists(img_path):
                return img_path
    return None

def save_schedule_record(week_key, uploaded_file):
    file_extension = uploaded_file.name.split(".")[-1]
    file_path = os.path.join(SCHEDULE_DIR, f"{week_key}.{file_extension}")
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    if os.path.exists(SCHEDULE_RECORD_FILE):
        df_s = pd.read_csv(SCHEDULE_RECORD_FILE)
    else:
        df_s = pd.DataFrame(columns=["week_key", "image_path"])
        
    df_s = df_s[df_s["week_key"] != week_key]
    new_row = pd.DataFrame([{"week_key": week_key, "image_path": file_path}])
    df_s = pd.concat([df_s, new_row], ignore_index=True)
    df_s.to_csv(SCHEDULE_RECORD_FILE, index=False, encoding="utf-8-sig")

# ==========================================
# 3. Session State 狀態初始化 (週日為一週開始)
# ==========================================
if "current_member" not in st.session_state:
    st.session_state.current_member = None

now = datetime.datetime.now()

# 調整週日為一週第一天：如果是週日(weekday==6)，週數加 1
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
# TAB 1: 前台 - 手機滿框大字簽到與進度圖查詢
# ------------------------------------------
with tab_user:
    verse_info = get_weekly_verse(current_week_num)
    st.info(f"📖 **本週經文**：*{verse_info['verse']}* —— **{verse_info['ref']}**")

    # ----------------------------------------------------
    # 進度圖表展開與歷史查詢專區 (自動顯示最新上傳圖檔)
    # ----------------------------------------------------
    with st.expander("🖼️ 點此查看【本週/歷史進度對照表】", expanded=False):
        # 取得已上傳的最大週數，若無則預設為當週
        latest_week_num = current_week_num
        if os.path.exists(SCHEDULE_RECORD_FILE):
            try:
                df_s_check = pd.read_csv(SCHEDULE_RECORD_FILE)
                if not df_s_check.empty:
                    uploaded_weeks = df_s_check["week_key"].str.extract(r'W(\d+)')[0].dropna().astype(int).tolist()
                    if uploaded_weeks:
                        latest_week_num = max(uploaded_weeks)
            except Exception:
                pass

        all_weeks_options = [f"Y{PLAN_YEAR}-W{w:02d} (第 {w} 週)" for w in range(1, 53)]
        
        # 預設選取最新發布的週數
        default_index = max(0, latest_week_num - 1)
        selected_w_str = st.selectbox("選擇要查看的週別進度圖：", all_weeks_options, index=default_index)
        
        target_img_week = selected_w_str.split(" ")[0]
        target_img_label = selected_w_str
            
        img_path = get_schedule_image_path(target_img_week)
        if img_path:
            st.image(img_path, caption=f"【{target_img_label}】進度表", use_container_width=True)
        else:
            st.warning(f"📌 目前尚未上傳【{target_img_label}】的進度表圖片，敬請期待管理者更新！")

    st.divider()

    # ----------------------------------------------------
    # 第一層：名字點選圖框選單
    # ----------------------------------------------------
    if st.session_state.current_member is None:
        st.markdown(f"**當前簽到進度：`{current_week_display}`**")
        
        chunk_size = 10
        total_members = len(member_list)
        pages = [f"第 {i//chunk_size + 1} 頁 ({i+1}~{min(i+chunk_size, total_members)}人)" for i in range(0, total_members, chunk_size)]
        
        if pages:
            selected_page_label = st.radio("選擇分頁：", pages, horizontal=True)
            selected_page_idx = pages.index(selected_page_label)
            
            start_idx = selected_page_idx * chunk_size
            end_idx = min(start_idx + chunk_size, total_members)
            current_page_members = member_list[start_idx:end_idx]
            
            st.write("👇 **請點選您的名字圖框：**")
            
            mid = (len(current_page_members) + 1) // 2
            left_col_members = current_page_members[:mid]
            right_col_members = current_page_members[mid:]
            
            col1, col2 = st.columns(2)
            
            with col1:
                for name in left_col_members:
                    is_placeholder = name.startswith("會友 ")
                    is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == name)].empty
                    
                    if is_placeholder:
                        btn_label = f"🔒 {name} (未啟用)"
                        is_disabled = True
                    else:
                        status_icon = "✅" if is_signed else "👤"
                        btn_label = f"{status_icon} {name}"
                        is_disabled = False
                        
                    if st.button(btn_label, key=f"select_{name}", type="secondary", disabled=is_disabled, use_container_width=True):
                        st.session_state.current_member = name
                        st.rerun()

            with col2:
                for name in right_col_members:
                    is_placeholder = name.startswith("會友 ")
                    is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == name)].empty
                    
                    if is_placeholder:
                        btn_label = f"🔒 {name} (未啟用)"
                        is_disabled = True
                    else:
                        status_icon = "✅" if is_signed else "👤"
                        btn_label = f"{status_icon} {name}"
                        is_disabled = False
                        
                    if st.button(btn_label, key=f"select_{name}", type="secondary", disabled=is_disabled, use_container_width=True):
                        st.session_state.current_member = name
                        st.rerun()

    # ----------------------------------------------------
    # 第二層：個人專屬頁面
    # ----------------------------------------------------
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
                save_record(current_week_key, member_name)
                st.toast(f"🎉 簽到成功！願神祝福您！")
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
            left_missing = missing_weeks_info[:mid_m]
            right_missing = missing_weeks_info[mid_m:]
            
            mc1, mc2 = st.columns(2)
            with mc1:
                for item in left_missing:
                    if st.button(f"🟡 {item['display']}", key=f"btn_miss_{item['key']}", type="secondary", use_container_width=True):
                        save_record(item["key"], member_name)
                        st.toast(f"✅ 已成功補簽 `{item['display']}`！")
                        st.rerun()
            with mc2:
                for item in right_missing:
                    if st.button(f"🟡 {item['display']}", key=f"btn_miss_{item['key']}", type="secondary", use_container_width=True):
                        save_record(item["key"], member_name)
                        st.toast(f"✅ 已成功補簽 `{item['display']}`！")
                        st.rerun()
        else:
            st.success("🎉 太棒了！過去每一週的進度皆已完成！")

# ------------------------------------------
# TAB 2: 後台 - 資料管理與進度圖上傳
# ------------------------------------------
with tab_admin:
    st.subheader("🔒 管理者數據與功能管理")
    pwd = st.text_input("請輸入管理者密碼：", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("身分驗證成功！")
        
        sub1, sub2, sub3, sub4 = st.tabs([
            "📊 多維度統計", 
            "🖼️ 上傳/更新進度圖表", 
            "👥 名單管理", 
            "⚡ 手動代簽"
        ])
        
        # 1. 統計報表
        with sub1:
            st.markdown(f"### 🔍 第 {PLAN_YEAR} 年彈性時間區間讀經統計")
            filter_mode = st.selectbox("請選擇查詢時間基準：", [
                "當月 (最近 4 週)", "第一季 Q1 (W01~W13)", "第二季 Q2 (W14~W26)", 
                "第三季 Q3 (W27~W39)", "第四季 Q4 (W40~W52)", "上半年 (W01~W26)", 
                "下半年 (W27~W52)", "全年度 (W01~W52)"
            ])
            
            if "當月" in filter_mode:
                target_weeks = [f"Y{PLAN_YEAR}-W{w:02d}" for w in range(max(1, current_week_num-3), current_week_num+1)]
            elif "Q1" in filter_mode:
                target_weeks = [f"Y{PLAN_YEAR}-W{w:02d}" for w in range(1, 14)]
            elif "Q2" in filter_mode:
                target_weeks = [f"Y{PLAN_YEAR}-W{w:02d}" for w in range(14, 27)]
            elif "Q3" in filter_mode:
                target_weeks = [f"Y{PLAN_YEAR}-W{w:02d}" for w in range(27, 40)]
            elif "Q4" in filter_mode:
                target_weeks = [f"Y{PLAN_YEAR}-W{w:02d}" for w in range(40, 53)]
            elif "上半年" in filter_mode:
                target_weeks = [f"Y{PLAN_YEAR}-W{w:02d}" for w in range(1, 27)]
            elif "下半年" in filter_mode:
                target_weeks = [f"Y{PLAN_YEAR}-W{w:02d}" for w in range(27, 53)]
            else:
                target_weeks = [f"Y{PLAN_YEAR}-W{w:02d}" for w in range(1, 53)]
                
            if not df_attendance.empty:
                filtered_df = df_attendance[df_attendance["week_key"].isin(target_weeks)]
                clean_df = filtered_df.drop_duplicates(subset=["member_name", "week_key"], keep="last")
                
                pivot_df = clean_df.pivot_table(index="member_name", columns="week_key", values="timestamp", aggfunc="first")
                pivot_df = pivot_df.reindex(index=member_list, columns=target_weeks)
                
                count_series = pivot_df.notna().sum(axis=1)
                total_target_weeks = len(target_weeks)
                
                result_df = pivot_df.notna().replace({True: "🟢 已讀", False: "❌"})
                result_df.insert(0, "完成率", (count_series / total_target_weeks * 100).round(1).astype(str) + "%")
                result_df.insert(0, "完成週數", count_series.astype(str) + f" / {total_target_weeks}")
                
                st.dataframe(result_df, use_container_width=True)
                
                csv_data = result_df.to_csv(index=True).encode('utf-8-sig')
                st.download_button(f"📥 匯出 [{filter_mode}] 統計報表 (.csv)", data=csv_data, file_name=f"church_report_Y{PLAN_YEAR}_{filter_mode}.csv", mime="text/csv")
            else:
                st.info("尚無簽到紀錄。")

        # 2. 上傳/更新進度圖表 (預設帶入下週 W+1)
        with sub2:
            st.markdown("### 🖼️ 上傳每週讀經進度表圖片")
            st.info("💡 每週五提前上傳時，系統預設已為您切換至【下週進度】。")
            
            # 預設帶入下一週 (current_week_num)
            next_week_idx = min(51, current_week_num) 
            upload_week_num = st.selectbox("選擇要上傳的週別：", list(range(1, 53)), index=next_week_idx)
            target_upload_key = f"Y{PLAN_YEAR}-W{upload_week_num:02d}"
            
            uploaded_schedule_file = st.file_uploader(f"上傳【第 {upload_week_num} 週】進度表圖片 (支援 JPG, PNG)", type=["png", "jpg", "jpeg"])
            
            if uploaded_schedule_file is not None:
                st.image(uploaded_schedule_file, caption=f"預覽：第 {upload_week_num} 週進度表", use_container_width=True)
                if st.button("🚀 確認儲存並發布此週進度圖"):
                    save_schedule_record(target_upload_key, uploaded_schedule_file)
                    st.success(f"🎉 成功發布第 {upload_week_num} 週進度表！會友現在即可在前台查看。")

        # 3. 名單管理
        with sub3:
            st.markdown("### ✏️ 修改會友姓名 (舊名換新名)")
            c1, c2 = st.columns(2)
            old_name_target = c1.selectbox("選擇要修改的會友：", member_list, key="rename_select")
            new_name_input = c2.text_input("輸入正確的新名字：", value=old_name_target)
            
            if st.button("✏️ 確認修改名字"):
                if new_name_input.strip() and new_name_input.strip() != old_name_target:
                    update_member_name(old_name_target, new_name_input.strip())
                    st.success(f"成功將【{old_name_target}】修改為【{new_name_input.strip()}】！")
                    st.rerun()
                else:
                    st.warning("請輸入與原姓名不同的新名字！")
                    
            st.divider()
            st.markdown("### ➕ 新增全新會友")
            add_name = st.text_input("輸入新會友姓名：")
            if st.button("➕ 確認新增"):
                if add_name.strip() and add_name.strip() not in member_list:
                    member_list.append(add_name.strip())
                    save_members(member_list)
                    st.success(f"已成功新增會友：{add_name.strip()}！")
                    st.rerun()
                elif add_name.strip() in member_list:
                    st.error("該會友姓名已存在！")

            st.divider()
            st.markdown("### ❌ 移除會友")
            del_target = st.selectbox("選擇要移除的會友：", ["-- 請選擇 --"] + member_list, key="delete_select")
            if del_target != "-- 請選擇 --" and st.button(f"❌ 確定移除 {del_target}"):
                member_list.remove(del_target)
                save_members(member_list)
                st.success(f"已從名單中移除 {del_target}")
                st.rerun()

        # 4. 手動代簽
        with sub4:
            st.markdown("### ⚡ 管理者指定補簽")
            c1, c2 = st.columns(2)
            adm_m = c1.selectbox("會友：", member_list)
            adm_w = c2.text_input("週別 (例: Y2-W35)：", value=current_week_key)
            if st.button("確認代簽"):
                save_record(adm_w, adm_m)
                st.toast(f"✅ 已為 {adm_m} 補簽 {adm_w}")
                st.rerun()
                
    elif pwd != "":
        st.error("密碼錯誤！")
