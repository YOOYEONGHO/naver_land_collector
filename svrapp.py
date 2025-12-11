import streamlit as st
import pandas as pd
import time
import json
import os
from crawler import NaverLandCrawler
from utils import load_data, save_data, clear_data
import streamlit.components.v1 as components

# Page Config
st.set_page_config(
    page_title="[Server] 부동산 매물 수집기",
    page_icon="🤖",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .stApp { opacity: 1 !important; }
    [data-testid="stAppViewContainer"] { opacity: 1 !important; }
    [data-testid="stSidebar"] { opacity: 1 !important; }
    header[data-testid="stHeader"] { opacity: 1 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 [Server] 부동산 데이터 수집 서버")
st.markdown("자동 수집 스케줄러 및 데이터 관리자입니다.")

# --- Persistence Logic ---
CONFIG_FILE = "server_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(new_conf):
    current = load_config()
    current.update(new_conf)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

# Load configuration on startup
config = load_config()

# Initialize Session State from Config if not set
if "is_auto_active" not in st.session_state:
    st.session_state.is_auto_active = config.get("is_auto_active", False)

# --- Sidebar: Collection Settings ---
st.sidebar.header("🛠 수집 설정")

# Defaults from config or fallback
default_complex = config.get("complex_id", "108064")
default_interval = int(config.get("interval", 30))
default_tradetype = config.get("tradetype", "매매 (Sale)")

complex_id = st.sidebar.text_input("단지 식별 번호 (hscpNo)", value=default_complex, help="네이버 부동산 단지 페이지 URL에서 확인 가능합니다.")
trade_type_map = {"매매 (Sale)": "A1", "전세 (Jeonse)": "B1", "월세 (Rent)": "B2"}
trade_options = list(trade_type_map.keys())

try:
    default_ix = trade_options.index(default_tradetype)
except:
    default_ix = 0

trade_type_label = st.sidebar.selectbox("매물 종류", trade_options, index=default_ix)
trade_type_code = trade_type_map[trade_type_label]

interval_min = st.sidebar.number_input("수집 주기 (분)", min_value=1, max_value=1440, value=default_interval)

st.sidebar.markdown("---")
st.sidebar.header("👮 관리자 설정")

# Password
if "admin_pw" not in st.session_state:
    st.session_state.admin_pw = ""
password_input = st.sidebar.text_input("관리자 비밀번호", type="password", key="admin_pw")

# Logic Function
def run_collection_task(c_id, t_code):
    t_label = [k for k,v in trade_type_map.items() if v == t_code][0]
    with st.spinner(f"단지 {c_id} ({t_label}) 수집 중..."):
        try:
            crawler = NaverLandCrawler()
            new_data = crawler.fetch_listings(complex_no=c_id, trade_type=t_code)
            if new_data:
                save_data(new_data)
                return True, f"수집 완료: {len(new_data)}건 ({t_label})"
            else:
                return False, "매물 없음 또는 API 오류"
        except Exception as e:
            return False, f"오류: {e}"

# Status Display
# If config says active, we trust it.
# Check if we need to sync session state again (just in case)
if config.get("is_auto_active"):
    st.session_state.is_auto_active = True

status_icon = "🟢" if st.session_state.is_auto_active else "🔴"
status_msg = "자동 수집 활성화" if st.session_state.is_auto_active else "자동 수집 중지"

# Last run time handling
# We can store last_run_time in config too, or keep strictly in session/memory. 
# Memory is fine for display, but for scheduling, config is better if we crash.
# Let's keep it simple: read from config if available.
if "last_run_time" not in st.session_state:
    st.session_state.last_run_time = config.get("last_run_time", 0)

last_run_str = "-"
if st.session_state.last_run_time > 0:
    last_run_str = time.strftime("%H:%M:%S", time.localtime(st.session_state.last_run_time))

st.sidebar.markdown(f"**상태:** {status_icon} {status_msg}")
st.sidebar.caption(f"최근 실행 시각: {last_run_str}")

# Callbacks
def on_start_click():
    if st.session_state.admin_pw == "Aqwe123!@#":
        st.session_state.is_auto_active = True
        st.session_state.trigger_run = True 
        st.session_state.admin_pw = ""
        st.session_state.auth_msg = ("success", "자동 수집이 시작되었습니다.")
        
        # Persist State
        save_config({
            "is_auto_active": True,
            "complex_id": complex_id,
            "interval": interval_min,
            "tradetype": trade_type_label
        })
    else:
        st.session_state.auth_msg = ("error", "비밀번호가 올바르지 않습니다!")

def on_stop_click():
    if st.session_state.admin_pw == "Aqwe123!@#":
        st.session_state.is_auto_active = False
        st.session_state.admin_pw = ""
        st.session_state.auth_msg = ("success", "자동 수집이 중지되었습니다.")
        
        # Persist State
        save_config({"is_auto_active": False})
    else:
        st.session_state.auth_msg = ("error", "비밀번호가 올바르지 않습니다!")

def on_clear_data_click():
    if st.session_state.admin_pw == "Aqwe123!@#":
        clear_data()
        st.session_state.admin_pw = ""
        st.session_state.auth_msg = ("success", "모든 데이터가 삭제되었습니다.")
    else:
        st.session_state.auth_msg = ("error", "비밀번호가 필요합니다.")

col_btn1, col_btn2 = st.sidebar.columns(2)
col_btn1.button("🚀 수집 시작", on_click=on_start_click, use_container_width=True)
col_btn2.button("🛑 수집 중지", on_click=on_stop_click, use_container_width=True)

# Message handling
if "auth_msg" in st.session_state and st.session_state.auth_msg:
    msg_type, msg_text = st.session_state.auth_msg
    if msg_type == "success":
        st.sidebar.success(msg_text)
    else:
        st.sidebar.error(msg_text)
    st.session_state.auth_msg = None

# Result Toast
if "trigger_result" in st.session_state and st.session_state.trigger_result:
    is_success, t_msg = st.session_state.trigger_result
    if is_success:
        st.toast(f"✅ {t_msg}", icon="🎉")
        st.sidebar.success(f"[자동] {t_msg}")
    else:
        st.toast(f"⚠️ {t_msg}", icon="🚨")
        st.sidebar.error(f"[자동] {t_msg}")
    st.session_state.trigger_result = None

# Data Manage
st.sidebar.markdown("---")
st.sidebar.button("🗑️ 모든 데이터 삭제", on_click=on_clear_data_click)


# --- Main Dashboard: Collection History ---
data = load_data()
if data:
    df = pd.DataFrame(data)
    
    # Summary Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("총 수집 데이터 건수", f"{len(df)} 건")
    
    latest_ts = df['timestamp'].max() if not df.empty else "-"
    col2.metric("최근 수집 시각", latest_ts)
    
    uniq_complex = df['atclNm'].nunique() if 'atclNm' in df.columns else 0
    col3.metric("수집 단지 수", f"{uniq_complex} 개")
    
    st.markdown("### 📋 수집 이력 로그")
    # Group by timestamp to show history
    history = df.groupby('timestamp').size().reset_index(name='Count')
    history = history.sort_values('timestamp', ascending=False)
    st.dataframe(history, width="stretch")
    
else:
    st.info("수집된 데이터가 없습니다.")


# --- Auto Collection Logic (Robust) ---

# 1. Trigger Handling (Manual Start or Force Run)
if st.session_state.get('trigger_run'):
    st.session_state.trigger_run = False
    
    success, msg = run_collection_task(complex_id, trade_type_code)
    st.session_state.trigger_result = (success, msg)
    
    # Update Last Run Time
    now_ts = time.time()
    st.session_state.last_run_time = now_ts
    save_config({"last_run_time": now_ts})
    
    st.rerun()

# 2. Scheduled Logic
if st.session_state.is_auto_active:
    # Ensure variables are set
    c_id = config.get("complex_id", complex_id)
    t_label = config.get("tradetype", trade_type_label)
    t_code = trade_type_map.get(t_label, "A1")
    i_min = int(config.get("interval", interval_min))

    now = time.time()
    gap = i_min * 60
    
    last_run = st.session_state.last_run_time
    # If last run was 0 (never), set it to now (as we assume we just started or missed it?) 
    # Actually if we just started, we probably triggered a run. 
    # If we recovered from config and never ran, last_run checks will trigger immediate run if 0.
    
    next_run = last_run + gap
    remaining = next_run - now
    
    # Force run if time elapsed (handles auto-reload trigger)
    if remaining <= 0:
        with st.spinner("자동 수집 실행 중... (스케줄)"):
             success, msg = run_collection_task(c_id, t_code)
             st.session_state.trigger_result = (success, msg)
             
             new_ts = time.time()
             st.session_state.last_run_time = new_ts
             save_config({"last_run_time": new_ts})
             
        st.rerun()
    else:
        # Display Countdown
        countdown_html = f"""
        <div style="
            padding: 10px;
            border-radius: 5px;
            background-color: #f0f2f6; 
            color: #31333F;
            border: 1px solid #d6d6d6;
            font-family: sans-serif;
            font-size: 14px;
            text-align: center;
        ">
            ⏳ 다음 수집(2차)까지 <b><span id="timer">{int(remaining)}</span>초</b>
        </div>
        <script>
            var timeleft = {int(remaining)};
            var countdownElement = document.getElementById("timer");
            
            var downloadTimer = setInterval(function(){{
                timeleft--;
                if(timeleft >= 0){{
                    if(countdownElement) countdownElement.textContent = timeleft;
                }}
                
                if(timeleft <= -1){{
                    clearInterval(downloadTimer);
                    try {{
                        window.parent.location.reload();
                    }} catch(e) {{
                        window.location.reload();
                    }}
                }}
            }}, 1000);
        </script>
        """
        with st.sidebar:
            components.html(countdown_html, height=60, scrolling=False)
