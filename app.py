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
ADMIN_PASSWORD = "church_admin"  # 後台密碼

# 4年讀經計畫設定：今年為第 2 年
PLAN_YEAR = 2 

st.set_page_config(page_title="教會4年讀經計畫簽到系統", page_icon="📖", layout="wide")

# ==========================================
# CSS 視覺修正
# ==========================================
st.markdown("""
    <style>
    /* 1. 所有按鈕內部的文字通用大字樣式 */
    div[data-testid="stButton"] button p {
        font-size: 32px !important;
        font-weight: 900 !important;
        letter-spacing: 1px !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.1 !important;
    }

    /* 2. 預設/次要按鈕（名字圖框 & 補簽圖框）：白底藍框大字 */
    div[data-testid="stButton"] button[kind="secondary"] {
        height: 2.8em !important;
        min-height: 2.8em !important;
        padding: 4px 8px !important;
        border-radius: 12px !important;
        border: 3px solid #0284C7 !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08) !important;
        margin-bottom: 6px !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background-color: #E0F2FE !important;
        border-color: #0369A1 !important;
    }

    /* 3. 主要按鈕（本週簽到大綠按鈕） */
    div[data-testid="stButton"] button[kind="primary"] {
        height: 3.2em !important;
        min-height: 3.2em !important;
        padding: 4px 8px !important;
        border-radius: 12px !important;
        border: none !important;
        background-color: #059669 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.15) !important;
        margin-bottom: 6px !important;
    }
    div[data-testid="stButton"] button[kind="primary"] p {
        color: #FFFFFF !important;
        font-size: 34px !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background-color: #047857 !important;
    }

    /* 4. 分頁選單字體 */
    div[data-testid="stRadio"] label p {
        font-size: 20px !important;
        font-weight: bold !important;
    }
    
    /* 5. 手機版邊距 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 資料處理函式
# ==========================================
def load_members():
    if os.path.exists(MEMBERS_FILE):
        return pd.read_csv(MEMBERS_FILE)
    else:
        default_members = [f"會友 {i+1:02d}" for i in range(50)]
        df_m = pd.DataFrame({"member_name": default_members})
        df_m.to_csv(MEMBERS_FILE, index=False, encoding="utf-8-sig")
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

# ==========================================
# 3. Session State 狀態初始化
# ==========================================
if "current_member" not in st.session_state:
    st.session_state.current_member = None

now = datetime.datetime.now()
current_week_num = now.isocalendar()[1]
current_week_key = f"Y{PLAN_YEAR}-W{current_week_num:02d}"
current_week_display = f"第 {PLAN_YEAR} 年 - 第 {current_week_num:02d} 週"

df_members = load_members()
member_list = df_members["member_name"].tolist()
df_attendance = load_attendance()

st.title(f"📖 教會讀經簽到（第 {PLAN_YEAR} 年）")

tab_user, tab_admin = st.tabs(["✍️ 會友簽到專區", "🔒 後台統計查詢"])

# ------------------------------------------
# TAB 1: 前台 - 手機滿框大字簽到
# ------------------------------------------
with tab_user:
    verse_info = get_weekly_verse(current_week_num)
    st.info(f"📖 **本週經文**：*{verse_info['verse']}* —— **{verse_info['ref']}**")

    # ----------------------------------------------------
    # 第一層：名字點選圖框選單
    # ----------------------------------------------------
    if st.session_state.current_member is None:
        st.markdown(f"**當前進度：`{current_week_display}`**")
        
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
            
            cols = st.columns(2)
            for idx, name in enumerate(current_page_members):
                with cols[idx % 2]:
                    is_signed = not df_attendance[(df_attendance["week_key"] == current_week_key) & (df_attendance["member_name"] == name)].empty
                    status_icon = "✅" if is_signed else "👤"
                    
                    if st.button(f"{status_icon} {name}", key=f"select_{name}", type="secondary", use_container_width=True):
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
        
        # 1. 本週簽到區塊
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
        
        # 2. 補簽未完成進度
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
            
            cols_missing = st.columns(2)
            for idx, item in enumerate(missing_weeks_info):
                with cols_missing[idx % 2]:
                    if st.button(f"🟡 {item['display']}", key=f"btn_miss_{item['key']}", type="secondary", use_container_width=True):
                        save_record(item["key"], member_name)
                        st.toast(f"✅ 已成功補簽 `{item['display']}`！")
                        st.rerun()
        else:
            st.success("🎉 太棒了！過去每一週的進度皆已完成！")

# ------------------------------------------
# TAB 2: 後台 - 資料管理
# ------------------------------------------
with tab_admin:
    st.subheader("🔒 管理者數據查詢與報表")
    pwd = st.text_input("請輸入管理者密碼：", type="password")
    
    if pwd == ADMIN_PASSWORD:
        st.success("身分驗證成功！")
        
        sub1, sub2, sub3 = st.tabs(["📊 多維度統計", "👥 名單管理 (改名/新增/刪除)", "⚡ 手動代簽"])
        
        # 1. 防爆表格統計報表
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
                
                # 防重複核心修正：自動剔除重複簽到紀錄，保留最新的一筆
                clean_df = filtered_df.drop_duplicates(subset=["member_name", "week_key"], keep="last")
                
                # 使用 pivot_table 取代 pivot
                pivot_df = clean_df.pivot_table(index="member_name", columns="week_key", values="timestamp", aggfunc="first")
                pivot_df = pivot_df.reindex(index=member_list, columns=target_weeks)
                
                count_series = pivot_df.notna().sum(axis=1)
                total_target_weeks = len(target_weeks)
                
                result_df = pivot_df.notna().replace({True: "🟢 已讀", False: "❌"})
                result_df.insert(0, "完成率", (count_series / total_target_weeks * 100).round(1).astype(str) + "%")
                result_df.insert(0, "完成週數", count_series.astype(str) + f" / {total_target_weeks}")
                
                st.write(f"顯示範圍：**{filter_mode}**（共 {total_target_weeks} 週）")
                st.dataframe(result_df, use_container_width=True)
                
                csv_data = result_df.to_csv(index=True).encode('utf-8-sig')
                st.download_button(f"📥 匯出 [{filter_mode}] 統計報表 (.csv)", data=csv_data, file_name=f"church_report_Y{PLAN_YEAR}_{filter_mode}.csv", mime="text/csv")
            else:
                st.info("尚無簽到紀錄。")

        # 2. 名單管理
        with sub2:
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

        # 3. 手動代簽
        with sub3:
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
