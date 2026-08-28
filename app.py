import streamlit as st
import pandas as pd
from datetime import datetime

# ==========================================
# 1. 頁面基本設定
# ==========================================
st.set_page_config(
    page_title="四年精讀聖經運動簽到",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. CSS 樣式美化（彩色大按鈕頁籤、超大極粗字體）
# ==========================================
st.markdown("""
    <style>
    /* 頁面整體防擠壓 */
    html, body { max-width: 100vw; overflow-x: hidden; }
    
    /* 1. 主標題字體加粗放大 */
    h1 {
        font-size: clamp(26px, 6vw, 38px) !important;
        font-weight: 900 !important;
        line-height: 1.3 !important;
    }

    /* 2. 頁籤 (Tabs) 容器與卡片按鈕化 */
    div[data-testid="stTabs"] [role="tablist"] {
        gap: 10px !important;
        margin-bottom: 20px !important;
        border-bottom: none !important;
    }

    /* 所有 Tab 按鈕基礎卡片外觀 */
    div[data-testid="stTabs"] button[role="tab"] {
        border-radius: 12px !important;
        padding: 10px 18px !important;
        margin: 2px !important;
        transition: all 0.2s ease-in-out !important;
        border: 3px solid #CBD5E1 !important;
        background-color: #F8FAFC !important;
        box-shadow: 0px 3px 6px rgba(0,0,0,0.08) !important;
    }

    /* 頁籤文字：超大號加粗 (24px - 30px) */
    div[data-testid="stTabs"] button[role="tab"] p,
    div[data-testid="stTabs"] button[role="tab"] div {
        font-size: clamp(22px, 5.5vw, 28px) !important;
        font-weight: 900 !important;
        letter-spacing: 0.5px !important;
        line-height: 1.3 !important;
    }

    /* [Tab 1: 簽到專區 - 鮮豔綠色卡片] 未選中 / 已選中 */
    div[data-testid="stTabs"] button[role="tab"]:nth-child(1) {
        background-color: #ECFDF5 !important;
        border-color: #059669 !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:nth-child(1) p { color: #047857 !important; }

    div[data-testid="stTabs"] button[role="tab"]:nth-child(1)[aria-selected="true"] {
        background-color: #059669 !important;
        border-color: #047857 !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:nth-child(1)[aria-selected="true"] p { color: #FFFFFF !important; }

    /* [Tab 2: 過往查詢 - 鮮豔藍色卡片] 未選中 / 已選中 */
    div[data-testid="stTabs"] button[role="tab"]:nth-child(2) {
        background-color: #EFF6FF !important;
        border-color: #2563EB !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:nth-child(2) p { color: #1D4ED8 !important; }

    div[data-testid="stTabs"] button[role="tab"]:nth-child(2)[aria-selected="true"] {
        background-color: #2563EB !important;
        border-color: #1D4ED8 !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:nth-child(2)[aria-selected="true"] p { color: #FFFFFF !important; }

    /* [Tab 3: 後台管理 - 質感灰色卡片] 未選中 / 已選中 */
    div[data-testid="stTabs"] button[role="tab"]:nth-child(3) {
        background-color: #F8FAFC !important;
        border-color: #64748B !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:nth-child(3) p { color: #334155 !important; }

    div[data-testid="stTabs"] button[role="tab"]:nth-child(3)[aria-selected="true"] {
        background-color: #475569 !important;
        border-color: #1E293B !important;
    }
    div[data-testid="stTabs"] button[role="tab"]:nth-child(3)[aria-selected="true"] p { color: #FFFFFF !important; }

    /* 隱藏原生底部的紅色指引線條 */
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    /* 3. 折疊圖框 (Expander) 標題文字放大加粗 */
    div[data-testid="stExpander"] summary p {
        font-size: clamp(22px, 5vw, 28px) !important;
        font-weight: 900 !important;
        color: #0F172A !important;
    }

    /* 4. 一般按鈕與主要按鈕超大文字 */
    div[data-testid="stButton"] button {
        width: 100% !important;
        white-space: normal !important;
        word-break: break-word !important;
    }
    div[data-testid="stButton"] button p {
        font-size: clamp(22px, 5.8vw, 30px) !important;
        font-weight: 900 !important;
    }
    div[data-testid="stButton"] button[kind="secondary"] {
        min-height: 3.5em !important;
        padding: 10px 8px !important;
        border-radius: 14px !important;
        border: 3px solid #0284C7 !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        margin-bottom: 10px !important;
    }
    div[data-testid="stButton"] button[kind="primary"] {
        min-height: 3.8em !important;
        border-radius: 14px !important;
        background-color: #059669 !important;
        margin-bottom: 10px !important;
    }
    div[data-testid="stButton"] button[kind="primary"] p { color: #FFFFFF !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 主標題
# ==========================================
st.title("📖 四年精讀聖經運動簽到")

# ==========================================
# 4. 建立三個主要頁籤 (Tabs)
# ==========================================
tab1, tab2, tab3 = st.tabs([
    "✍️ 會友簽到專區", 
    "🗓️ 過往進度查詢", 
    "🔒 後台統計管理"
])

# ------------------------------------------
# 分頁 1: 會友簽到專區
# ------------------------------------------
with tab1:
    st.subheader("請選擇您的名字進行今日簽到：")
    
    # 範例折疊選單（組別）
    with st.expander("第一組（弟兄組）", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("張弟兄", key="btn_1", type="secondary"):
                st.success("張弟兄 今日簽到成功！🎉")
        with col2:
            if st.button("李弟兄", key="btn_2", type="secondary"):
                st.success("李弟兄 今日簽到成功！🎉")

    with st.expander("第二組（姊妹組）"):
        col3, col4 = st.columns(2)
        with col3:
            if st.button("王姊妹", key="btn_3", type="secondary"):
                st.success("王姊妹 今日簽到成功！🎉")
        with col4:
            if st.button("陳姊妹", key="btn_4", type="secondary"):
                st.success("陳姊妹 今日簽到成功！🎉")

# ------------------------------------------
# 分頁 2: 過往進度查詢
# ------------------------------------------
with tab2:
    st.subheader("🗓️ 個人歷史讀經紀錄查詢")
    st.info("此處提供會友查詢個人過去一週與當月的讀經簽到狀況。")

# ------------------------------------------
# 分頁 3: 後台統計管理
# ------------------------------------------
with tab3:
    st.subheader("🔒 管理員後台統計")
    st.warning("僅限小組長與管理人員查看讀經總體進度。")
