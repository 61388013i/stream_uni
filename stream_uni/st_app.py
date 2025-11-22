import streamlit as st
from google import genai
from google.genai.errors import APIError
import os
import json 
import time

# --- 1. 配置與金鑰 (Key) ---
# 警告：此金鑰將被部署到雲端，請務必了解其風險。
GEMINI_API_KEY = "AIzaSyD_Cs5LftBQCwiwJG7xVjmP8Rfd46EMjJs"
MODEL_NAME = "gemini-2.5-flash"              
REQUEST_TIMEOUT = 90                         

# --- 星座列表 (從原 index.html 移植) ---
CONSTELLATIONS = [
    "牡羊座", "金牛座", "雙子座", "巨蟹座", "獅子座", 
    "處女座", "天秤座", "天蠍座", "射手座", "摩羯座", 
    "水瓶座", "雙魚座"
]

# --- 主題標籤 ---
topic_labels = {
    "love": "戀愛／關係",
    "work": "工作／職場",
    "study": "學業／考試",
    "heal": "心情／療癒",
    "other": "一般／綜合"
}

# --- 2. 核心 AI 提示詞函數 ---
def create_prompt(constellation, topic, note):
    """根據星座名稱、主題和備註建立結構化提示詞。"""
    
    prompt_text = f"""
    你是一位中文占星專家，請嚴格按照以下要求生成報告：

    **背景資訊：**
    - 使用者的星座是: {constellation}
    - 使用者的主題是: {topic} (請根據這個主題深化建議內容)
    - 使用者的煩惱備註: {note if note else '無'}

    **報告結構要求 (必須包含以下六個部分，請以清晰的條列式呈現)：**
    1. **總體運勢**
    2. **工作建議** (如果主題是戀愛/心情，請提供一般性的生活建議)
    3. **愛情建議** (如果主題是工作/學業，請提供人際關係的平衡建議)
    4. **學業建議** (如果主題不是學業，請提供學習新知的建議)
    5. **幸運元素** (請包含一個幸運顏色和一個幸運數字)
    6. **鼓勵的話** (一句正向、溫暖、激勵人心的話)
    """
    return prompt_text

# --- 3. 主題偵測邏輯 ---
def detect_topic(note):
    """偵測使用者煩惱的關鍵主題，並回傳標籤 (love, work, etc.)。"""
    n = note.strip()
    if not n: return "other"

    love_keywords = ["喜歡", "曖昧", "戀愛", "感情", "在一起", "分手", "告白", "心動", "男友", "女友"]
    work_keywords = ["工作", "上班", "職場", "公司", "老闆", "主管", "面試", "加班", "專案"]
    study_keywords = ["報告", "作業", "功課", "考試", "學校", "期中", "期末", "論文", "學習"]
    heal_keywords = ["心累", "焦慮", "憂鬱", "想哭", "崩潰", "壓力", "好累", "疲憊", "不想動"]

    check = lambda lst: any(k in n for k in lst)

    if check(love_keywords): return "love"
    if check(work_keywords): return "work"
    if check(study_keywords): return "study"
    if check(heal_keywords): return "heal"
    return "other"


# --- 4. Streamlit 應用程式主體 ---
st.set_page_config(
    page_title="星座占卜小宇宙",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 狀態儲存 (用於手動覆蓋主題)
if 'topic_override' not in st.session_state:
    st.session_state['topic_override'] = None

def set_topic_override(topic):
    st.session_state['topic_override'] = topic

# --- 讀取 HTML 樣式 (已修正路徑讀取方式) ---
try:
    # 修正後的讀取方式：確保 Streamlit 無論在哪裡運行都能找到它
    current_dir = os.path.dirname(__file__)
    file_path = os.path.join(current_dir, "index.html")
    
    with open(file_path, "r", encoding="utf-8") as f:
        html_code = f.read()

    # 提取 HTML 中的樣式和基礎結構（用於背景和卡片樣式）
    # 我們只需要從 <body> 開始到第一個輸入區塊前的所有樣式
    header_start = html_code.find('<body>')
    header_end = html_code.find('')

    # 顯示 Header 和 CSS
    st.markdown(html_code[header_start:header_end], unsafe_allow_html=True)
    
    # 調整 Streamlit 內部元素樣式 (覆蓋 Streamlit 預設樣式)
    st.markdown("""
    <style>
    /* ------------------------------------------- */
    /* 低飽和度配色方案：柔和灰綠/霧面藍 */
    /* ------------------------------------------- */
    /* 確保 Streamlit 容器使用 index.html 中的卡片樣式 */
    div[data-testid="stVerticalBlock"] {
        background: rgba(14, 14, 40, 0.92);
        border-radius: 24px;
        padding: 24px 24px 28px;
        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.55);
        backdrop-filter: blur(18px);
        border: 1px solid rgba(180, 180, 255, 0.25);
    }
    .stApp {
        background: radial-gradient(circle at top, #1b1b3a 0%, #050510 55%, #000000 100%) !important;
        color: #f7f7ff;
    }
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* 1. 主要按鈕顏色 (柔和的藍綠色漸層) */
    .stButton button {
        background: linear-gradient(135deg, #A8DADC, #45A29E); 
        color: #1a1a1a; 
        font-weight: 600;
        border-radius: 999px;
        border: none;
        padding: 8px 14px;
    }

    /* 2. 標籤文字顏色 (柔和的灰綠色) */
    .stTextArea label, .stSelectbox label {
        font-size: 0.9rem !important;
        color: #AEC2B6; 
        margin-bottom: 0.35rem;
    }
    
    /* 3. Streamlit 輸入框和選單背景/文字顏色 */
    div[data-testid="stSelectbox"] > div,
    div[data-testid="stTextArea"] > div > textarea {
        background-color: rgba(10, 10, 30, 0.85); /* 深色背景 */
        color: #f7f7ff; /* 白色文字 */
        border: 1px solid rgba(180, 180, 255, 0.25);
    }
    </style>
    """, unsafe_allow_html=True)

except FileNotFoundError:
    st.error("🚨 錯誤：Streamlit 應用程式找不到 index.html 檔案。請檢查您的 GitHub 儲存庫中是否遺失該檔案或路徑錯誤。")
    st.stop()
except Exception as e:
    st.error(f"🚨 載入錯誤: {e}")
    st.stop()


# --- Streamlit Python 互動元素 ---

# 1. 修正後的星座選擇框
sign = st.selectbox("你的星座", CONSTELLATIONS, index=0, key="sign_select")

# 2. 煩惱輸入框
note = st.text_area("想補充給宇宙知道的小事（AI 會參考這段內容）", 
                     placeholder="例如：最近在煩惱喜歡的人、報告、工作或只是覺得心很累。",
                     key="note_input")

# 3. 主題偵測與顯示
detected_topic = detect_topic(note)
current_topic_key = st.session_state['topic_override'] if st.session_state['topic_override'] else detected_topic
current_topic_label = topic_labels.get(current_topic_key, topic_labels['other'])

st.markdown(f"""
<div style='font-size: 0.8rem; margin-top: 10px; margin-bottom: 10px; opacity: 0.8;'>
目前主題：**{current_topic_label}** {'（手動選擇）' if st.session_state['topic_override'] else '（系統判定）'}
</div>
""", unsafe_allow_html=True)


# 4. 手動覆蓋按鈕 (主題選擇)
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.button(topic_labels['love'], on_click=set_topic_override, args=("love",), key="btn_love")
with col2:
    st.button(topic_labels['work'], on_click=set_topic_override, args=("work",), key="btn_work")
with col3:
    st.button(topic_labels['study'], on_click=set_topic_override, args=("study",), key="btn_study")
with col4:
    st.button(topic_labels['heal'], on_click=set_topic_override, args=("heal",), key="btn_heal")
with col5:
    st.button(topic_labels['other'], on_click=set_topic_override, args=("other",), key="btn_other")


# 5. 核心功能按鈕與 API 呼叫
if st.button("🔮 獲得今日解析", key="btn_horoscope_final"):
    if not GEMINI_API_KEY:
        st.error("🚨 錯誤：Gemini API Key 未設定。")
    else:
        with st.spinner(f"正在連線 Gemini AI... (主題: {current_topic_label})"):
            try:
                # 執行 API 呼叫邏輯
                prompt = create_prompt(sign, current_topic_label, note)
                client = genai.Client(api_key=GEMINI_API_KEY)

                response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        timeout=REQUEST_TIMEOUT
    )
                
                generated_text = response.text
                
                final_output = f"【{sign}｜今日解析｜主題：{current_topic_label}】\n\n" + generated_text
                
                # 顯示結果
                st.success("✅ 解析成功！")
                st.markdown("---")
                st.markdown(f"**🔎 解析結果**")
                
                # 將輸出顯示在一個美觀的代碼塊中，保留 Markdown 格式
                st.code(final_output, language='markdown') 
                
            except APIError as e:
                st.error(f"🔴 Gemini API 服務錯誤: {e.status_code}")
                st.warning("請檢查您的 API Key 是否有效或帳戶額度是否足夠。")
                
            except Exception as e:
                st.exception(e)
                st.error("伺服器內部錯誤，請檢查網路連線。")


st.markdown('<div class="hint">※ 內容由 Gemini AI 模型生成，僅供參考。</div>', unsafe_allow_html=True)


