import streamlit as st
import pandas as pd
import plotly.express as px
from crawler import NaverLandCrawler
import time
from utils import load_data, save_data, clean_price

# Helper for Korean currency formatting in charts
def format_currency(value):
    return f"{value/100000000:.1f}억"

# Page Config
st.set_page_config(
    page_title="네이버 부동산 허위매물 수집기",
    page_icon="🏢",
    layout="wide"
)

# Custom CSS for aesthetics
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .stButton>button {
        width: 100%;
        background-color: #03c75a; 
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# Title and description
st.title("🏢 네이버 부동산 매물 수집 및 분석 도구")
st.markdown("**허위매물** 의심 사례 수집을 위한 데이터 크롤링 및 시각화 도구입니다.")

# Sidebar
st.sidebar.header("🛠 수집 설정")

# Restore params from URL if available (for Auto Mode consistency across reloads)
qp_complex = st.query_params.get("complex", "108064")
qp_interval = int(st.query_params.get("interval", 2))

# Inputs
complex_id = st.sidebar.text_input("단지 식별 번호 (hscpNo)", value=qp_complex, help="네이버 부동산 단지 페이지 URL에서 확인 가능합니다.")
trade_type_map = {"매매 (Sale)": "A1", "전세 (Jeonse)": "B1", "월세 (Rent)": "B2"}
trade_type_label = st.sidebar.selectbox("매물 종류", list(trade_type_map.keys()))
trade_type_code = trade_type_map[trade_type_label]

# --- Logic Functions ---
if 'auto_running' not in st.session_state:
    st.session_state.auto_running = False

def run_collection_task():
    with st.spinner(f"단지 ID {complex_id} 데이터 수집 중..."):
        try:
            crawler = NaverLandCrawler()
            new_data = crawler.fetch_listings(complex_no=complex_id, trade_type=trade_type_code)
            if new_data:
                save_data(new_data)
                return True, f"수집 완료: {len(new_data)}건"
            else:
                return False, "매물 없음 또는 API 오류"
        except Exception as e:
            return False, f"오류: {e}"

# --- Sidebar Inputs ---
interval_min = st.sidebar.number_input("수집 주기 (분)", min_value=1, max_value=60, value=qp_interval)

st.sidebar.markdown("---")
st.sidebar.header("👮 관리자 설정")

# Password Input with Session State
if "admin_pw" not in st.session_state:
    st.session_state.admin_pw = ""

password_input = st.sidebar.text_input("관리자 비밀번호", type="password", key="admin_pw")

# Auto-Collection State
if "is_auto_active" not in st.session_state:
    st.session_state.is_auto_active = False

# Status Display
last_run_str = "-"
if 'last_run_time' in st.session_state:
    last_run_str = time.strftime("%H:%M:%S", time.localtime(st.session_state.last_run_time))

status_icon = "🟢" if st.session_state.is_auto_active else "🔴"
status_msg = "자동 수집 활성화" if st.session_state.is_auto_active else "자동 수집 중지"

st.sidebar.markdown(f"**상태:** {status_icon} {status_msg}")
st.sidebar.caption(f"최근 실행 시각: {last_run_str}")

# Action Callbacks
def on_start_click():
    if st.session_state.admin_pw == "Aqwe123!@#":
        st.session_state.is_auto_active = True
        st.session_state.trigger_run = True 
        st.session_state.admin_pw = ""
        st.session_state.auth_msg = ("success", "자동 수집이 시작되었습니다.")
        # Persist State AND Inputs via Query Param
        st.query_params["auto"] = "true"
        st.query_params["complex"] = complex_id
        st.query_params["interval"] = str(interval_min)
    else:
        st.session_state.auth_msg = ("error", "비밀번호가 올바르지 않습니다!")

def on_stop_click():
    if st.session_state.admin_pw == "Aqwe123!@#":
        st.session_state.is_auto_active = False
        st.session_state.admin_pw = ""
        st.session_state.auth_msg = ("success", "자동 수집이 중지되었습니다.")
        # Clear Query Params
        st.query_params.clear()
    else:
        st.session_state.auth_msg = ("error", "비밀번호가 올바르지 않습니다!")

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

# Show Result from previous trigger run if any
if "trigger_result" in st.session_state and st.session_state.trigger_result:
    is_success, t_msg = st.session_state.trigger_result
    if is_success:
        st.toast(f"✅ {t_msg}", icon="🎉")
        st.sidebar.success(f"[자동] {t_msg}")
    else:
        st.toast(f"⚠️ {t_msg}", icon="🚨")
        st.sidebar.error(f"[자동] {t_msg}")
    
    # Clear result so it doesn't persist forever, but slight delay or next rerun clears it naturally?
    # Better to clear it here so it doesn't show on manual interaction reruns
    st.session_state.trigger_result = None

# --- Auto Collection Logic (Non-blocking & Robust) ---
import streamlit.components.v1 as components

# 0. Check Query Params for Restoration/Trigger (Fix for refresh stopping auto-mode)
if st.query_params.get("auto") == "true":
    st.session_state.is_auto_active = True

# 1. Trigger Handling (Immediate or from Reload)
param_trigger = st.query_params.get("trigger")

if st.session_state.get('trigger_run') or param_trigger:
    st.session_state.trigger_run = False
    
    # Run Collection
    # Update: run_collection_task returns status
    success, msg = run_collection_task()
    
    # Save result to session state to show AFTER rerun
    st.session_state.trigger_result = (success, msg)
    
    # Update Time
    st.session_state.last_run_time = time.time()
    
    # Trigger cleanup
    if param_trigger:
        st.query_params.clear()
        st.query_params["auto"] = "true"
        # Restore input params to URL so they persist on NEXT reload too
        st.query_params["complex"] = complex_id
        st.query_params["interval"] = str(interval_min)
        
    st.rerun()

# 2. Scheduled Logic
if st.session_state.is_auto_active:
    # Initialize last_run_time if missing
    if 'last_run_time' not in st.session_state:
         st.session_state.last_run_time = time.time()
    
    now = time.time()
    gap = interval_min * 60
    
    # Calculate next scheduled time
    next_run = st.session_state.last_run_time + gap
    remaining = next_run - now
    
    # Safety Check: If remaining is negative but we didn't trigger yet (maybe slight drift),
    # or if we just missed the trigger logic above.
    # But usually the JS reload with 'trigger' handles the expiration.
    # The 'remaining' here is for the NEXT run (after the one we just did or are waiting for).
    
    # Display Countdown
    # If logic works, 'remaining' should be positive (gap) right after a run.
    # If we are waiting, it decreases.
    if remaining <= 0:
        # Fallback if JS didn't reload or something
        # Just show 0 or reload manually?
        # Let's show "Updating..."
        st.sidebar.warning("갱신 중...")
        st.rerun()
    else:
        # Wait mode - Show live countdown using JS
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
            ⏳ 다음 수집까지 <b><span id="timer">{int(remaining)}</span>초</b>
        </div>
        <script>
            var timeleft = {int(remaining)};
            var countdownElement = document.getElementById("timer");
            
            var downloadTimer = setInterval(function(){{
                timeleft--;
                if(timeleft >= 0){{
                    countdownElement.textContent = timeleft;
                }}
                
                if(timeleft <= 0){{
                    clearInterval(downloadTimer);
                    // Reload with trigger param to force collection
                    // Use window.location (current iframe) instead of parent to avoid Cross-Origin issues on Cloud
                    try {{
                        const url = new URL(window.location.href);
                        url.searchParams.set('auto', 'true');
                        url.searchParams.set('trigger', Date.now());
                        window.location.href = url.href;
                    }} catch(e) {{
                        console.error(e);
                        window.location.reload();
                    }}
                }}
            }}, 1000);
        </script>
        """
        
        # Inject into sidebar
        with st.sidebar:
            components.html(countdown_html, height=60, scrolling=False)

# Main Content
st.markdown("---")

# Custom CSS to remove 'running' opacity overlay and other tweaks
st.markdown("""
    <style>
    /* 
       Streamlit grays out the app when running. 
       We target common containers to force opacity to 1.
    */
    
    /* Main App Container */
    .stApp {
        opacity: 1 !important;
    }
    
    /* The view container that holds main and sidebar */
    [data-testid="stAppViewContainer"] {
        opacity: 1 !important;
    }
    
    /* The actual content blocks */
    [data-testid="stAppViewBlockContainer"] {
        opacity: 1 !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        opacity: 1 !important;
    }
    
    /* Header */
    header[data-testid="stHeader"] {
        opacity: 1 !important;
    }
    
    /* Disable transitions that might look like fading */
    * {
        transition: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Load Data
data = load_data()

if not data:
    st.info("수집된 데이터가 없습니다. 왼쪽 사이드바에서 '수집 시작'을 눌러주세요.")
else:
    df = pd.DataFrame(data)
    
    # Ensure new columns exist for backward compatibility with old data
    for col in ["buildingName", "realtorName", "direction"]:
        if col not in df.columns:
            df[col] = "정보없음"
            
    # Pre-calculate units for charts (억 단위)
    df['price_eok'] = df['price_int'] / 100000000
    
    # filters
    st.sidebar.header("🔎 분석 필터")
    
    # Complex Filter Logic
    complexes = df['atclNm'].unique()
    
    # Default selection logic:
    # 1. If we just crawled, try to select the complex matching the ID (requires data match which we don't have direct id mapping, but we can infer from crawled count or session state if we had it. 
    # For now, let's default to the *most recently collected* complex name if available, instead of ALL.
    default_selection = []
    if len(complexes) > 0:
        # Sort by latest timestamp presence to find most active/recent
        latest_complex = df.sort_values("timestamp", ascending=False).iloc[0]['atclNm']
        default_selection = [latest_complex]

    selected_complex = st.sidebar.multiselect("단지 선택", complexes, default=default_selection)
    
    # Area Filter placeholder
    
    if not selected_complex:
        st.warning("최소 하나의 단지를 선택해주세요.")
        st.stop()
        
    filtered_df = df[df['atclNm'].isin(selected_complex)]

    # Create Tabs (Renamed per user request)
    tab1, tab2 = st.tabs(["📈 증감량 추이", "🔎 매물 상세 분석"])

    with tab1:
        # --- Metrics Logic ---
        unique_timestamps = sorted(filtered_df['timestamp'].unique(), reverse=True)
        
        if not unique_timestamps:
            latest_count = 0
            avg_price = 0
            count_diff = 0 # Renamed from new_listing_count
            ts_display = "-"
            latest_df = pd.DataFrame()
        else:
            latest_ts = unique_timestamps[0]
            ts_display = pd.to_datetime(latest_ts).strftime("%Y/%m/%d %H:%M")
            latest_df = filtered_df[filtered_df['timestamp'] == latest_ts]
            
            latest_count = len(latest_df)
            avg_price = latest_df['price_int'].mean()
            
            if len(unique_timestamps) > 1:
                prev_ts = unique_timestamps[1]
                prev_snapshot = filtered_df[filtered_df['timestamp'] == prev_ts]
                count_diff = latest_count - len(prev_snapshot)
                
                # New Arrivals (Purely new items)
                new_ids = set(latest_df['articleNo']) - set(prev_snapshot['articleNo'])
                new_listing_count = len(new_ids)
                
                # Deleted items (Transactions or Cancelled)
                deleted_ids = set(prev_snapshot['articleNo']) - set(latest_df['articleNo'])
                deleted_count = len(deleted_ids)
            else:
                count_diff = 0
                new_listing_count = 0
                deleted_count = 0

        # Display Metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric(f"현재 매물 수 ({ts_display} 기준)", f"{latest_count}개")
        col2.metric(f"평균 가격 ({ts_display} 기준)", f"{avg_price/100000000:.2f} 억" if avg_price else "0 억")
        col3.metric("매물 수 증감 (이전 대비)", f"{count_diff:+}개", delta=count_diff)
        col4.metric("신규 진입 매물 (New)", f"{new_listing_count}개")
        col5.metric("삭제된 매물 (Sold/Cancel)", f"{deleted_count}개")

        st.markdown("---")

        # --- Lowest Price Analysis ---
        st.subheader(f"📉 전용면적별 최저가 매물 ({ts_display} 기준)")
        if not latest_df.empty:
            idx = latest_df.groupby('spc2')['price_int'].idxmin()
            lowest_price_df = latest_df.loc[idx].sort_values('spc2')
            
            display_cols = ['spc2', 'tradePrice', 'floorInfo', 'direction', 'buildingName', 'realtorName']
            display_df = lowest_price_df[display_cols].copy()
            # tradePrice is already string like "10억", we can keep it or format price_int? 
            # User wants to SEE price. tradePrice is "10억 5,000", good for display.
            display_df.columns = ['전용면적', '가격', '층수', '향', '동', '중개사']
            
            st.dataframe(display_df, width="stretch", hide_index=True)
        else:
            st.info("데이터가 없습니다.")

        st.markdown("---")

        # --- Charts ---
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            # Price Distribution
            # Use price_int for histogram numeric
            # Ticks: 50 million won interval
            step = 50000000 # 5000만원
            min_p = int(latest_df['price_int'].min())
            max_p = int(latest_df['price_int'].max())
            tick_vals = list(range(min_p, max_p + step, step))
            
            def format_kr_price_tick(x):
                # x is in won. 1450000000 -> 14.5 -> 14억 5천
                eok = x // 100000000
                chun = (x % 100000000) // 10000
                if chun == 0:
                    return f"{eok}억"
                elif chun == 5000:
                    return f"{eok}억 5천"
                else:
                    return f"{x/100000000:.1f}억"

            tick_text = [format_kr_price_tick(x) for x in tick_vals]

            fig_hist = px.histogram(latest_df, x="price_int", nbins=20, title="매물 가격 분포 (최신)")
            fig_hist.update_xaxes(tickformat=".1f", ticksuffix="억", title="가격 (원)", 
                                  tickvals=tick_vals,
                                  ticktext=tick_text)
            st.plotly_chart(fig_hist, width="stretch")
            
        with col_c2:
             # Area Distribution
            fig_area = px.histogram(latest_df, x="spc2", nbins=10, title="면적별 매물 분포 (최신)")
            fig_area.update_xaxes(title="전용면적 (m²)")
            fig_area.update_yaxes(title="매물 수")
            st.plotly_chart(fig_area, width="stretch")

        # Trend Chart
        # Group by EXACT timestamp (Snapshot)
        trend_df = filtered_df.groupby('timestamp').size().reset_index(name='count')
        trend_df['timestamp_dt'] = pd.to_datetime(trend_df['timestamp'])
        trend_df = trend_df.sort_values('timestamp_dt')
        trend_df = trend_df.tail(10)
        trend_df['xaxis_label'] = trend_df['timestamp_dt'].dt.strftime("%Y/%m/%d %H:%M")
        
        fig_line = px.line(trend_df, x='xaxis_label', y='count', markers=True, 
                           title="매물 수집 시점별 매물 수 변화 (최근 10회)",
                           labels={"xaxis_label": "수집 일시", "count": "매물 수 (개)"})
        
        min_count = trend_df['count'].min()
        max_count = trend_df['count'].max()
        y_min = max(0, min_count - 10)
        y_max = max_count + 10
        
        fig_line.update_xaxes(type='category')
        fig_line.update_yaxes(tickformat="d", dtick=1, range=[y_min, y_max])
        st.plotly_chart(fig_line, width="stretch")

        # --- Data Grid (Latest) ---
        st.markdown("---")
        st.subheader("📋 전체 매물 데이터 (최신)")
        st.dataframe(latest_df.sort_values(by="timestamp", ascending=False), width="stretch")


    with tab2:
        # Advanced Analysis: Realtor & Building
        st.header("🕵️ 상세 분석")
        
        subtab1, subtab2 = st.tabs(["🏢 부동산(중개사)별 분석", "🏙️ 동(Building)별 분석"])
        
        with subtab1:
            st.subheader("부동산별 매물 수 (상위 20곳)")
            if not latest_df.empty:
                realtor_counts = latest_df['realtorName'].value_counts().reset_index()
                realtor_counts.columns = ['realtorName', 'count']
                
                # Interactive Table
                selection_realtor = st.dataframe(
                    realtor_counts.head(20),
                    width="stretch",
                    on_select="rerun",
                    selection_mode="single-row"
                )
                
                # Drill-down
                if selection_realtor.selection.rows:
                    selected_idx_list = selection_realtor.selection.rows
                    if selected_idx_list:
                        selected_row_idx = selected_idx_list[0]
                        selected_realtor = realtor_counts.iloc[selected_row_idx]['realtorName']
                        
                        st.divider()
                        st.markdown(f"#### 🔎 '{selected_realtor}' 상세 분석")
                        
                        # 1. Trend for this realtor
                        r_trend = filtered_df[filtered_df['realtorName'] == selected_realtor].groupby('timestamp').size().reset_index(name='count')
                        r_trend['timestamp_dt'] = pd.to_datetime(r_trend['timestamp'])
                        r_trend = r_trend.sort_values('timestamp_dt')
                        r_trend['xaxis_label'] = r_trend['timestamp_dt'].dt.strftime("%Y/%m/%d %H:%M")

                        fig_r = px.line(r_trend, x='xaxis_label', y='count', markers=True, 
                                        title=f"'{selected_realtor}' 매물 수 추이")
                        fig_r.update_xaxes(type='category')
                        fig_r.update_yaxes(tickformat="d", dtick=1, rangemode="tozero")
                        st.plotly_chart(fig_r, width="stretch")

                        # 2. Detailed Listing Table
                        st.markdown(f"**현재 등록 매물 목록**")
                        r_listings = latest_df[latest_df['realtorName'] == selected_realtor]
                        cols_r = ['articleNo', 'spc2', 'buildingName', 'floorInfo', 'tradePrice', 'direction', 'atclFetrDesc']
                        st.dataframe(r_listings[cols_r], width="stretch", hide_index=True)


        with subtab2:
            st.subheader("동별 매물 수")
            if not latest_df.empty:
                building_counts = latest_df['buildingName'].value_counts().reset_index()
                building_counts.columns = ['buildingName', 'count']
                
                # Interactive Table
                selection_building = st.dataframe(
                    building_counts,
                    width="stretch",
                    on_select="rerun",
                    selection_mode="single-row"
                )
                
                # Drill-down
                if selection_building.selection.rows:
                    selected_idx_list_b = selection_building.selection.rows
                    if selected_idx_list_b:
                        selected_row_idx_b = selected_idx_list_b[0]
                        selected_building = building_counts.iloc[selected_row_idx_b]['buildingName']
                        
                        st.divider()
                        st.markdown(f"#### 🔎 '{selected_building}' 상세 분석")
                        
                        # 1. Trend for this building
                        b_trend = filtered_df[filtered_df['buildingName'] == selected_building].groupby('timestamp').size().reset_index(name='count')
                        b_trend['timestamp_dt'] = pd.to_datetime(b_trend['timestamp'])
                        b_trend = b_trend.sort_values('timestamp_dt')
                        b_trend['xaxis_label'] = b_trend['timestamp_dt'].dt.strftime("%Y/%m/%d %H:%M")

                        fig_b = px.line(b_trend, x='xaxis_label', y='count', markers=True, 
                                        title=f"'{selected_building}' 매물 수 추이")
                        fig_b.update_xaxes(type='category')
                        fig_b.update_yaxes(tickformat="d", dtick=1, rangemode="tozero")
                        st.plotly_chart(fig_b, width="stretch")

                        # 2. Detailed Listing Table
                        st.markdown(f"**현재 등록 매물 목록**")
                        b_listings = latest_df[latest_df['buildingName'] == selected_building]
                        cols_b = ['articleNo', 'buildingName', 'floorInfo', 'spc2', 'tradePrice', 'direction', 'realtorName', 'atclFetrDesc']
                        st.dataframe(b_listings[cols_b], width="stretch", hide_index=True)

    # Export
    # Convert DF to CSV for download (Use latest_df or filtered_df? User probably wants what they see in grid, which is latest)
    # But usually export data implies all data. Let's keep filtered_df for export but raw grid is latest.
    csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="💾 데이터 다운로드 (CSV)",
        data=csv,
        file_name='naver_land_evidence.csv',
        mime='text/csv',
    )


# Danger Zone
st.sidebar.markdown("---")
st.sidebar.header("⚠️ 데이터 관리")
if st.sidebar.button("🗑️ 모든 수집 데이터 삭제"):
    from utils import clear_data
    
    with st.spinner("데이터 삭제 중..."):
        clear_data()
        
    st.sidebar.success("모든 데이터가 삭제되었습니다! 페이지를 새로고침하세요.")
    time.sleep(1)
    st.rerun()
