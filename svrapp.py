import streamlit as st
import pandas as pd
import time
import math
import json
import os
import threading
from streamlit.runtime.scriptrunner import add_script_run_ctx
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
st.markdown("백그라운드 스레드 기반 자동 수집 스케줄러입니다. (브라우저를 닫아도 수집됩니다)")

# --- Persistence (Config) Logic ---
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

config = load_config()

# --- Core Logic Function ---
# Needs to be standalone so thread can call it (or static method)
def run_collection_task(c_id, t_code):
    # Mapping for display (Reverse lookup)
    trade_type_map = {"매매 (Sale)": "A1", "전세 (Jeonse)": "B1", "월세 (Rent)": "B2"}
    inv_map = {v: k for k, v in trade_type_map.items()}
    t_label = inv_map.get(t_code, t_code)
    
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] [Scheduler] Start collection: {c_id}, {t_label}")
    try:
        crawler = NaverLandCrawler()
        new_data = crawler.fetch_listings(complex_no=c_id, trade_type=t_code)
        if new_data:
            if save_data(new_data):
                msg = f"수집 완료: {len(new_data)}건"
                print(f"[Scheduler] {msg}")
                return True, msg
            else:
                msg = "수집 데이터 저장 실패 (로그 확인)"
                print(f"[Scheduler] {msg}")
                return False, msg
        else:
            msg = "매물 없음 또는 API 오류"
            print(f"[Scheduler] {msg}")
            return False, msg
    except Exception as e:
        msg = f"오류: {e}"
        print(f"[Scheduler] {msg}")
        return False, msg

# --- Background Scheduler Class ---
class BackgroundScheduler:
    def __init__(self):
        self.is_running = False
        self.interval_minutes = 30
        self.complex_id = "108064"
        self.trade_type = "A1"
        
        self.last_run_time = 0
        self.next_run_time = 0
        
        self._thread = None
        self._lock = threading.Lock()
        self.status_msg = "초기화 대기"

    def start(self, interval, complex_id, trade_type):
        with self._lock:
            self.interval_minutes = interval
            self.complex_id = complex_id
            self.trade_type = trade_type
            self.is_running = True
            
            # Reset schedule
            self.last_run_time = 0 # Or keep history? let's reset for immediate run or schedule
            
            # OPTION: Run immediately on start? 
            # Let's schedule first run immediately for feedback
            self.next_run_time = time.time() 
            
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, daemon=True)
                add_script_run_ctx(self._thread)
                self._thread.start()
            
            self.status_msg = "실행 중"

    def stop(self):
        with self._lock:
            self.is_running = False
            self.status_msg = "중지됨"

    def _loop(self):
        while True:
            # Check every 1s
            if self.is_running:
                now = time.time()
                if now >= self.next_run_time:
                    # Time to run!
                    self.status_msg = "수집 실행 중..."
                    success, msg = run_collection_task(self.complex_id, self.trade_type)
                    
                    # Schedule next

                    self.last_run_time = time.time()
                    interval_sec = self.interval_minutes * 60
                    self.next_run_time = math.ceil(time.time() / interval_sec) * interval_sec 
                    
                    next_run_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.next_run_time))
                    self.status_msg = f"대기 중 (다음 수집: {next_run_str})"
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [Scheduler] Collection finished. Next run scheduled at: {next_run_str}")
            
            time.sleep(1)

# Singleton Instance
@st.cache_resource
def get_scheduler():
    return BackgroundScheduler()

scheduler = get_scheduler()

# --- Sidebar: Collection Settings ---
st.sidebar.header("🛠 수집 설정")

# Defaults from Scheduler or Config
# Since scheduler is singleton, we can pull checks from it if running
default_complex = config.get("complex_id", "108064")
default_interval = int(config.get("interval", 30))
default_tradetype = config.get("tradetype", "매매 (Sale)")

complex_id = st.sidebar.text_input("단지 식별 번호 (hscpNo)", value=default_complex)
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
if "admin_pw" not in st.session_state:
    st.session_state.admin_pw = ""
password_input = st.sidebar.text_input("관리자 비밀번호", type="password", key="admin_pw")

# Callbacks
def on_start_click():
    if st.session_state.admin_pw == "Aqwe123!@#":
        scheduler.start(interval_min, complex_id, trade_type_code)
        
        # Persist config
        save_config({
            "is_auto_active": True,
            "complex_id": complex_id,
            "interval": interval_min,
            "tradetype": trade_type_label
        })
        st.session_state.admin_pw = ""
        st.success("스케줄러가 시작되었습니다.")
    else:
        st.error("비밀번호 불일치")

def on_stop_click():
    if st.session_state.admin_pw == "Aqwe123!@#":
        scheduler.stop()
        save_config({"is_auto_active": False})
        st.session_state.admin_pw = ""
        st.success("스케줄러가 중지되었습니다.")
    else:
        st.error("비밀번호 불일치")

def on_clear_data_click():
    if st.session_state.admin_pw == "Aqwe123!@#":
        clear_data()
        st.session_state.admin_pw = ""
        st.success("데이터가 삭제되었습니다.")
    else:
        st.error("비밀번호 불일치")

col_btn1, col_btn2 = st.sidebar.columns(2)
col_btn1.button("🚀 수집 시작", on_click=on_start_click, use_container_width=True, disabled=scheduler.is_running)
col_btn2.button("🛑 수집 중지", on_click=on_stop_click, use_container_width=True, disabled=not scheduler.is_running)

# --- Status Display ---
st.sidebar.markdown("---")
status_icon = "🟢" if scheduler.is_running else "🔴"
st.sidebar.markdown(f"**상태:** {status_icon} {scheduler.status_msg}")

if scheduler.is_running:
    next_ts = scheduler.next_run_time
    if next_ts > 0:
        remain = next_ts - time.time()
        if remain < 0: remain = 0
        st.sidebar.info(f"다음 수집: {int(remain)}초 후")
        
        # Simple auto-refresh for UI (not logic)
        # Refresh every 10s just to update the "seconds left" visual
        # Logic handles itself in background even if this loop dies
        
        # We use a simple meta refresh or st.rerun if we want lively updates
        # But extensive reruns are annoying. Let's do a gentle JS interval for reload
    if st.sidebar.button("🔄 상태 새로고침"):
        st.rerun()

    # Optional Auto-refresh
    st.sidebar.markdown("---")
    
    monitor_interval_min = st.sidebar.number_input(
        "모니터링 새로고침 주기 (분)", 
        min_value=1, 
        value=1, 
        step=1,
        help="브라우저 화면을 자동으로 새로고침하는 주기입니다."
    )
    
    auto_refresh = st.sidebar.checkbox(f"⚡ 실시간 모니터링 켜기 ({monitor_interval_min}분 마다)", value=False)
    
    if auto_refresh:
        refresh_ms = monitor_interval_min * 60 * 1000
        st.components.v1.html(f"""
            <script>
                setTimeout(function(){{
                    window.parent.location.reload();
                }}, {refresh_ms});
            </script>
        """, height=0)

# Data Manage
st.sidebar.markdown("---")
st.sidebar.button("🗑️ 모든 데이터 삭제", on_click=on_clear_data_click)

# --- Dashboard ---
# Load FRESH data
data = load_data()
if data:
    df = pd.DataFrame(data)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("총 수집 데이터", f"{len(df)} 건")
    
    latest_ts = df['timestamp'].max() if not df.empty else "-"
    col2.metric("최근 수집 시각", latest_ts)
    
    uniq = df['atclNm'].nunique() if 'atclNm' in df.columns else 0
    col3.metric("수집 단지 수", f"{uniq} 개")
    
    st.markdown("### 📋 수집 이력 로그")
    history = df.groupby('timestamp').size().reset_index(name='Count')
    history = history.sort_values('timestamp', ascending=False)
    st.dataframe(history, width="stretch")

else:
    st.info("수집된 데이터가 없습니다.")
