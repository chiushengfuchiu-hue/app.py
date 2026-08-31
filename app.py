import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, date
import os

# -----------------------------------------------------------------------------
# 0. 系統基本設定
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="讀經班簽到與進度資源系統",
    page_icon="📖",
    layout="wide"
)

# 系統數據檔案路徑 (簽到紀錄)
DATA_FILE = "member_attendance.csv"

# 初始化 CSV 檔案 (如果不存在，建立完整相容欄位)
if not os.path.exists(DATA_FILE):
    df_init = pd.DataFrame(columns=["日期", "姓名", "年份", "週次", "讀經進度", "備註"])
    df_init.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

def load_data():
    df = pd.read_csv(DATA_FILE, encoding="utf-8-sig")
    # 確保字串欄位無多餘空白
    if not df.empty:
        df['姓名'] = df['姓名'].astype(str).str.strip()
        if '週次' in df.columns:
            df['週次'] = df['週次'].astype(str).str.strip()
    return df

def save_data(df):
    df.to_csv(DATA_FILE, index=False, encoding="utf-8-sig")

# -----------------------------------------------------------------------------
# 讀經進度資料庫 (包含天與整週對照)
# -----------------------------------------------------------------------------
SCHEDULE_DATA = [
    {"年份": "第 2 年", "週次": "第 36 週", "日期": "2026-08-30", "星期": "週日", "經文範圍": "約爾書 3:1-21", "導讀主題/重點": "上帝的審判與猶大/耶路撒利的恢復；約法谷（審判谷）與列國的追討。"},
    {"年份": "第 2 年", "週次": "第 36 週", "日期": "2026-08-31", "星期": "週一", "經文範圍": "阿摩斯書 1:1-2:5", "導讀主題/重點": "先知阿摩斯背景介紹；上帝對列國的審判。"},
    {"年份": "第 2 年", "週次": "第 36 週", "日期": "2026-09-01", "星期": "週二", "經文範圍": "阿摩斯書 2:6-16", "導讀主題/重點": "上帝對北國以色列的指控：欺壓貧窮與社會不公。"},
    {"年份": "第 2 年", "週次": "第 36 週", "日期": "2026-09-02", "星期": "週三", "經文範圍": "阿摩斯書 3:1-15", "導讀主題/重點": "立約子民的責任與特權；奢華與虛偽的降罪。"},
    {"年份": "第 2 年", "週次": "第 36 週", "日期": "2026-09-03", "星期": "週四", "經文範圍": "阿摩斯書 4:1-13", "導讀主題/重點": "嚴懲撒馬利亞貴婦；自然的災難與警訊。"},
    {"年份": "第 2 年", "週次": "第 36 週", "日期": "2026-09-04", "星期": "週五", "經文範圍": "阿摩斯書 5:1-27", "導讀主題/重點": "以色列的哀歌；尋求上帝就必存活；實踐社會公平正義。"},
    {"年份": "第 2 年", "週次": "第 36 週", "日期": "2026-09-05", "星期": "週六", "經文範圍": "阿摩斯書 6:1-14", "導讀主題/重點": "警告安逸奢華者；自大的盲目與虛無的倚靠。"}
]

df_schedule = pd.DataFrame(SCHEDULE_DATA)

# -----------------------------------------------------------------------------
# 外部音訊與影片網址
# -----------------------------------------------------------------------------
SOUNDON_LU_PASTOR_URL = "https://player.soundon.fm/p/520fefe3-1e30-4024-bcb1-260d1594bdf7"
SOUNDON_BIBLE_PODCAST_URL = "https://player.soundon.fm/p/28cbcb5d-2a87-4bb8-8b89-a3c2ccae77f8"
SOUNDON_BOOK_INTRO_URL = "" 
YOUTUBE_CHANNEL_URL = "https://youtube.com/channel/UCw1XdsEXHBAZ2tX8A2MjR1w"

# -----------------------------------------------------------------------------
# 標題區
# -----------------------------------------------------------------------------
st.title("📖 讀經班管理與語音資源系統")

# 四大主頁籤
tab1, tab2, tab3, tab4 = st.tabs([
    "✍️ 會友簽到", 
    "📅 查詢進度與閱覽", 
    "📚 相關資料查詢", 
    "⚙️ 後台管理"
])

# =============================================================================
# 第一頁籤：會友簽到 (個人專頁與補籤)
# =============================================================================
with tab1:
    st.header("✍️ 會友讀經簽到專頁")
    
    # 載入所有紀錄
    df_records = load_data()
    
    # 選擇會友姓名
    member_name = st.text_input("👤 請輸入您的姓名以進行簽到 / 查詢個人進度：", placeholder="例如：單麗蘭").strip()
    
    if member_name:
        st.subheader(f"👤 {member_name} 的讀經專頁")
        
        # 取得該會友已簽到的週次列表
        user_records = df_records[df_records["姓名"] == member_name] if not df_records.empty else pd.DataFrame()
        signed_weeks = user_records["週次"].tolist() if not user_records.empty and "週次" in user_records.columns else []
        
        current_year = "第 2 年"
        current_week = "第 36 週"
        full_current_week_str = f"{current_year} - {current_week}"
        
        # 本週簽到按鈕
        st.markdown(f"📍 **【本週進度】{full_current_week_str}**")
        if current_week in signed_weeks or full_current_week_str in signed_weeks:
            st.success(f"🎉 您已完成 【{full_current_week_str}】 的簽到！")
        else:
            if st.button(f"🟢 若完成 【{full_current_week_str}】 請按此簽到", use_container_width=True):
                new_entry = {
                    "日期": datetime.now().strftime("%Y-%m-%d"),
                    "姓名": member_name,
                    "年份": current_year,
                    "週次": current_week,
                    "讀經進度": "約爾書第3章 ~ 阿摩斯書第6章",
                    "備註": "本週簽到"
                }
                df_updated = pd.concat([df_records, pd.DataFrame([new_entry])], ignore_index=True)
                save_data(df_updated)
                st.success(f"✅ {member_name} 兄姊，【{full_current_week_str}】 簽到成功！")
                st.rerun()

        st.divider()

        # 補籤區塊
        st.markdown("🟡 **【補籤未完成進度】**")
        all_weeks = [f"第 {i:02d} 週" for i in range(1, 36)]
        
        # 找出未簽到的週次
        unsigned_weeks = [w for w in all_weeks if w not in signed_weeks and f"{current_year} - {w}" not in signed_weeks]
        
        if unsigned_weeks:
            st.caption(f"📌 共有 {len(unsigned_weeks)} 週尚未完成，點擊按鈕補籤：")
            cols = st.columns(2)
            for idx, w_str in enumerate(unsigned_weeks):
                col = cols[idx % 2]
                with col:
                    if col.button(f"🟡 {current_year} - {w_str}", key=f"btn_{w_str}", use_container_width=True):
                        new_entry = {
                            "日期": datetime.now().strftime("%Y-%m-%d"),
                            "姓名": member_name,
                            "年份": current_year,
                            "週次": w_str,
                            "讀經進度": f"補籤 {w_str}",
                            "備註": "補籤"
                        }
                        df_updated = pd.concat([df_records, pd.DataFrame([new_entry])], ignore_index=True)
                        save_data(df_updated)
                        st.success(f"✅ 已完成 【{current_year} - {w_str}】 補籤！")
                        st.rerun()
        else:
            st.info("👏 太棒了！您過去所有週次的進度皆已全數完成簽到！")

# =============================================================================
# 第二頁籤：查詢進度與閱覽 (按整週 vs 按天)
# =============================================================================
with tab2:
    st.header("📅 讀經進度與導讀經文閱覽")
    
    view_mode = st.radio("🔍 請選擇檢視模式：", ["🗓️ 按整週進度閱覽", "📌 按單日進度查詢"], horizontal=True)
    st.divider()
    
    if view_mode == "🗓️ 按整週進度閱覽":
        weeks = df_schedule["週次"].unique()
        selected_week = st.selectbox("📆 請選擇週次：", weeks)
        week_df = df_schedule[df_schedule["週次"] == selected_week]
        
        st.subheader(f"📋 {selected_week} 讀經總進度表")
        st.dataframe(week_df[["日期", "星期", "經文範圍", "導讀主題/重點"]], use_container_width=True, hide_index=True)

    else:
        search_date = st.date_input("📆 請選擇查詢日期：", date(2026, 8, 31))
        date_str = search_date.strftime("%Y-%m-%d")
        daily_data = df_schedule[df_schedule["日期"] == date_str]
        
        if not daily_data.empty:
            item = daily_data.iloc[0]
            st.success(f"📌 **{item['日期']} ({item['星期']}) 讀經進度**")
            st.markdown(f"### 📖 經文範圍：`{item['經文範圍']}`")
            st.info(f"💡 **導讀重點：** {item['導讀主題/重點']}")
        else:
            st.warning(f"⚠️ 找不到 {date_str} 的特定進度，以下為本週預設進度供您參考：")
            st.dataframe(df_schedule[["日期", "星期", "經文範圍", "導讀主題/重點"]], use_container_width=True, hide_index=True)

# =============================================================================
# 第三頁籤：相關資料查詢 (含舊進度 YT 影片搜尋)
# =============================================================================
with tab3:
    st.header("📚 相關資料與多媒體導讀查詢")
    
    media_tab1, media_tab2, media_tab3, media_tab4 = st.tabs([
        "🎙️ 聖經導讀 SoundOn", 
        "🎧 聖經 Podcast SoundOn", 
        "📖 認識經書 SoundOn", 
        "📺 YouTube 導讀影片庫"
    ])

    with media_tab1:
        st.subheader("🎙️ 盧俊義牧師聖經導讀")
        st.link_button("🔗 開啟 SoundOn 導讀頁面", SOUNDON_LU_PASTOR_URL)
        components.iframe(SOUNDON_LU_PASTOR_URL, height=450, scrolling=True)

    with media_tab2:
        st.subheader("🎧 聖經 PODCAST")
        st.link_button("🔗 開啟 SoundOn Podcast 頁面", SOUNDON_BIBLE_PODCAST_URL)
        components.iframe(SOUNDON_BIBLE_PODCAST_URL, height=450, scrolling=True)

    with media_tab3:
        st.subheader("📖 認識經書系列 SoundOn")
        if SOUNDON_BOOK_INTRO_URL:
            components.iframe(SOUNDON_BOOK_INTRO_URL, height=450, scrolling=True)
        else:
            st.info("ℹ️ 認識經書 SoundOn 資源內容整備中，敬請期待！")

    with media_tab4:
        st.subheader("📺 YouTube 每週導讀字幕影片庫")
        
        YOUTUBE_VIDEOS_DB = [
            {
                "id": "DT_8leW9zPI",
                "title": "第 36 週：約爾書第3章 ~ 阿摩斯書第6章",
                "week": "第 36 週",
                "date": "2026-08-30 ~ 2026-09-05",
                "desc": "上帝對列國的審判、公義與公平的呼喚、約法谷的復興。"
            }
        ]
        
        video_titles = [f"【{v['week']}】{v['title']}" for v in YOUTUBE_VIDEOS_DB]
        selected_video_str = st.selectbox("🎥 請選擇導讀影片：", video_titles)
        selected_index = video_titles.index(selected_video_str)
        target_video = YOUTUBE_VIDEOS_DB[selected_index]

        st.divider()
        st.markdown(f"### 🎬 {target_video['title']}")
        yt_embed_url = f"https://www.youtube.com/embed/{target_video['id']}"
        components.iframe(yt_embed_url, height=480, scrolling=False)
        st.info(f"💡 **導讀摘要**：{target_video['desc']}")

# =============================================================================
# 第四頁籤：後台管理
# =============================================================================
with tab4:
    st.header("⚙️ 後台管理與簽到統計")
    
    admin_password = st.text_input("🔑 請輸入管理員密碼", type="password")
    
    if admin_password == "admin123":
        st.success("🔓 驗證成功，歡迎進入管理後台！")
        
        df = load_data()
        
        st.subheader("📊 會友簽到紀錄總覽與統計")
        if df.empty:
            st.info("目前尚無簽到紀錄。")
        else:
            col_stat1, col_stat2 = st.columns(2)
            with col_stat1:
                st.metric("總簽到人次", f"{len(df)} 次")
            with col_stat2:
                st.metric("參與會友數", f"{df['姓名'].nunique()} 人")
                
            st.dataframe(df, use_container_width=True)
            
            csv_data = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            st.download_button(
                label="📥 下載完整簽到 Excel/CSV 檔",
                data=csv_data,
                file_name=f"讀經班簽到紀錄_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    elif admin_password:
        st.error("❌ 密碼錯誤，請重新輸入！")
    else:
        st.info("🔒 請輸入管理員密碼以解鎖後台功能。（預設密碼：admin123）")
