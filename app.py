import streamlit as st
import pandas as pd
import plotly.express as px
import time
import streamlit.components.v1 as components
from utils import load_data, get_complex_list, IS_SUPABASE_READY
from datetime import datetime, timedelta

# Page Config
st.set_page_config(
    page_title="네이버 부동산 매물 분석 대시보드",
    page_icon="🏢",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .stApp { opacity: 1 !important; }
    [data-testid="stAppViewContainer"] { opacity: 1 !important; }
    [data-testid="stSidebar"] { opacity: 1 !important; }
    header[data-testid="stHeader"] { opacity: 1 !important; }
    * { transition: none !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🏢 부동산 매물 분석 현황판")
st.markdown("실시간 수집 데이터를 기반으로 한 매물 증감 및 분석 대시보드입니다.")

# --- Auto Refresh Logic (Poll every 5 mins) ---
refresh_interval_sec = 300 # 5 minutes
auto_refresh_html = f"""
<script>
    var timer = setInterval(function() {{
        window.location.reload();
    }}, {refresh_interval_sec * 1000});
</script>
"""
components.html(auto_refresh_html, height=0)


# --- Sidebar: Lazy Loading Complex Selection ---
st.sidebar.header("🔎 분석 필터")

if not IS_SUPABASE_READY:
    st.sidebar.error("⚠️ 클라우드 설정 필요")
    st.sidebar.info("""
    **Supabase 연결 정보가 없습니다.**
    
    Streamlit Cloud의 **Manage App > Secrets** 메뉴에 다음 설정을 추가해주세요.
    
    ```toml
    [supabase]
    url = "YOUR_SUPABASE_URL"
    key = "YOUR_SUPABASE_KEY"
    ```
    """)
    st.stop()

# 1. Fetch List (Lightweight)
all_complexes = get_complex_list()
selected_complex = []

if len(all_complexes) > 0:
    # Default to first
    selected_complex_name = st.sidebar.selectbox("단지 선택", all_complexes, index=0)
    selected_complex = [selected_complex_name] # Keep as list for compatibility with load_data
else:
    st.sidebar.warning("단지 정보가 없습니다.")
    st.stop()

if not selected_complex:
    st.info("👈 왼쪽 사이드바에서 분석할 단지를 선택해주세요.")
    st.stop()

# 2. Load Data (Access Deep History for Selection)
with st.spinner(f"'{', '.join(selected_complex)}' 데이터 로딩 중 (최대 100,000건)..."):
    data = load_data(target_complexes=selected_complex)

if not data:
    st.warning("선택한 단지의 데이터가 없습니다.")
    st.stop()

df = pd.DataFrame(data)

# --- Data Cleaning (User Request) ---
# Exclude anomaly: DMC View Xi (108064) @ 2025-12-14 23:40
if not df.empty and 'timestamp' in df.columns and 'atclNm' in df.columns:
    # Filter specific timestamps for DMC Park View Xi (User Requests: 2025-12-14 23:40, 2025-12-15 00:40)
    anomalies = ['2025-12-14T23:40', '2025-12-15T00:40']
    
    # Construct mask (atclNm == DMC AND timestamp matches any anomaly)
    mask_dmc = (df['atclNm'] == 'DMC파크뷰자이')
    mask_ts = df['timestamp'].str.contains('|'.join(anomalies), na=False)
    
    anomaly_mask = mask_dmc & mask_ts
    
    if anomaly_mask.any():
        df = df[~anomaly_mask]

# Ensure columns
for col in ["buildingName", "realtorName", "direction"]:
    if col not in df.columns:
        df[col] = "정보없음"

# Type enforcement for robust set operations
if 'articleNo' in df.columns:
    df['articleNo'] = df['articleNo'].astype(str)

df['price_eok'] = df['price_int'] / 100000000

# Apply Filter (Standard DataFrame Filter)
# Note: specific table (listings_{id}) is already queried, so strict filtering by atclNm is risky for migrated data.
# We bypass the name check to ensure all rows in the table are shown.
filtered_df = df 
unique_timestamps = sorted(filtered_df['timestamp'].unique(), reverse=True)


# --- Helper: Area Type Classifier ---
def get_area_type(size):
    try:
        s = float(size)
        if 50 <= s < 70: return '59'
        elif 70 <= s < 100: return '84'
        elif 100 <= s < 135: return '120'
        elif 135 <= s < 165: return '152'
        elif 165 <= s < 200: return '175'
        else: return '기타'
    except:
        return '기타'

# --- Helper: Render Dashboard ---
def render_dashboard_view(view_df, current_ts, all_timestamps, key_suffix=""):
    """
    Renders the metrics, charts, and table for a specific timestamp.
    """
    if not current_ts:
        st.error("데이터가 없습니다.")
        return

    ts_display = pd.to_datetime(current_ts).strftime("%Y년 %m월 %d일 %H:%M")
    
    # Snapshot at current_ts
    snapshot_df = view_df[view_df['timestamp'] == current_ts].copy()
    snapshot_df['type'] = snapshot_df['spc2'].apply(get_area_type)
    
    # Previous Snapshot Logic (Net Increase Metric)
    count_diff = 0
    prev_snapshot_df = pd.DataFrame()
    
    try:
        curr_idx = all_timestamps.index(current_ts)
        prev_idx = curr_idx + 1
        if prev_idx < len(all_timestamps):
            prev_ts = all_timestamps[prev_idx]
            prev_snapshot_df = view_df[view_df['timestamp'] == prev_ts].copy()
            prev_snapshot_df['type'] = prev_snapshot_df['spc2'].apply(get_area_type)
            
            count_diff = len(snapshot_df) - len(prev_snapshot_df)
            
            # New/Deleted Sets for Real-Time Metric (Current Pulse)
            new_ids = set(snapshot_df['articleNo']) - set(prev_snapshot_df['articleNo'])
            deleted_ids = set(prev_snapshot_df['articleNo']) - set(snapshot_df['articleNo'])
        else:
            new_ids = set()
            deleted_ids = set()
    except ValueError:
        new_ids = set()
        deleted_ids = set()

    new_listing_count = len(new_ids)
    deleted_count = len(deleted_ids)
    avg_price = snapshot_df['price_int'].mean() if not snapshot_df.empty else 0

    # --- 1. Top Metrics (Overall) ---
    st.markdown(f"### 📊 전체 현황 <span style='font-size:0.8em; color:gray'>({ts_display} 기준)</span>", unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(f"전체 매물 수", f"{len(snapshot_df)}개")
    c2.metric(f"전체 평균 가격", f"{avg_price/100000000:.2f} 억")
    c3.metric("전체 증감", f"{count_diff:+}개", delta=count_diff)
    c4.metric("신규 진입", f"{new_listing_count}개")
    c5.metric("삭제됨", f"{deleted_count}개")

    # --- 2. Type-based Metrics (59, 84, 120, 152, 175) ---
    st.markdown("### 📐 타입별 현황 (59, 84, 120, 152, 175)")
    target_types = ['59', '84', '120', '152', '175']
    
    # Calculate metrics per type
    type_metrics = []
    for t in target_types:
        # Current
        curr_t = snapshot_df[snapshot_df['type'] == t]
        c_cnt = len(curr_t)
        c_avg = curr_t['price_int'].mean() if not curr_t.empty else 0
        
        # Prev
        p_cnt = 0
        if not prev_snapshot_df.empty:
            prev_t = prev_snapshot_df[prev_snapshot_df['type'] == t]
            p_cnt = len(prev_t)
        
        diff = c_cnt - p_cnt
        type_metrics.append((t, c_cnt, c_avg, diff))
    
    # Display Type Metrics in Columns
    cols = st.columns(len(target_types))
    for idx, (t, cnt, avg, diff) in enumerate(type_metrics):
        with cols[idx]:
            st.markdown(f"**{t} 타입**")
            st.metric("매물 수", f"{cnt}", delta=diff)
            # st.caption(f"평균: {avg/100000000:.2f}억") # Optional: clean display
            st.markdown(f"<span style='font-size:0.8em; color:gray'>평균: {avg/100000000:.2f}억</span>", unsafe_allow_html=True)

    st.markdown("---")

    # --- 3. Trend Chart (Generic) ---
    st.subheader(f"📈 매물 수집 증감 추이 (~{ts_display})")
    
    trend_view_df = view_df[view_df['timestamp'] <= current_ts]
    trend_agg = trend_view_df.groupby('timestamp').size().reset_index(name='count')
    trend_agg['timestamp_dt'] = pd.to_datetime(trend_agg['timestamp'], format='mixed', errors='coerce', utc=True)
    trend_agg = trend_agg.sort_values('timestamp_dt').tail(50) # Show more history as we have it now
    trend_agg['xaxis_label'] = trend_agg['timestamp_dt'].dt.strftime("%m/%d %H:%M")
    
    fig_line = px.line(trend_agg, x='xaxis_label', y='count', markers=True, 
                       labels={"xaxis_label": "일시", "count": "매물 수"})
    if not trend_agg.empty:
         y_min = max(0, trend_agg['count'].min() - 5)
         y_max = trend_agg['count'].max() + 5
         fig_line.update_yaxes(tickformat="d", dtick=1, range=[y_min, y_max])
    
    # use_container_width is standard for Plotly charts in Streamlit
    st.plotly_chart(fig_line, width="stretch", key=f"chart_trend_{key_suffix}")

    st.markdown("---")

    # --- 4. Lowest Price by Type ---
    st.subheader("📉 전용면적별 최저가 매물")
    
    if not snapshot_df.empty:
        # Group by Type and Find Min Price
        # We want to ensure we cover the target types if they exist
        lowest_list = []
        
        for t in target_types:
            type_df = snapshot_df[snapshot_df['type'] == t]
            if not type_df.empty:
                min_price = type_df['price_int'].min()
                # Get the row(s) with min price. For the summary table, take the first one or distinct ones.
                # User asked to group by these types.
                # Let's show the ONE cheapest representative for the summary table
                cheapest_rep = type_df[type_df['price_int'] == min_price].iloc[0]
                lowest_list.append(cheapest_rep)
        
        if lowest_list:
            lowest_df = pd.DataFrame(lowest_list)
            # Columns: 전용면적/가격/동/층수/향/중개사
            # 'spc2' is used for display as per user existing code
            disp_cols = ['spc2', 'tradePrice', 'buildingName', 'floorInfo', 'direction', 'realtorName']
            final_lowest = lowest_df[disp_cols].copy()
            final_lowest.columns = ['전용면적', '가격', '동', '층수', '향', '중개사']
            st.caption("타입별 최저가 대표 매물")
            st.dataframe(final_lowest, hide_index=True, width="stretch")
            
        # --- 5. All Lowest Price Listings ---
        st.markdown("#### 🏘️ 전용면적별 최저가 매물 부동산 전체")
        # Find ALL listings that match the min price for their type
        all_lowest_rows = []
        for t in target_types:
            type_df = snapshot_df[snapshot_df['type'] == t]
            if not type_df.empty:
                min_price = type_df['price_int'].min()
                matches = type_df[type_df['price_int'] == min_price].copy()
                matches['type'] = t
                all_lowest_rows.append(matches)
        
        if all_lowest_rows:
            full_lowest_df = pd.concat(all_lowest_rows)
            disp_cols = ['spc2', 'tradePrice', 'buildingName', 'floorInfo', 'direction', 'realtorName', 'type']
            f_lowest = full_lowest_df[disp_cols].copy()
            f_lowest = f_lowest.sort_values(['type', 'tradePrice'])
            f_lowest.columns = ['전용면적', '가격', '동', '층수', '향', '중개사', '타입']
            st.dataframe(f_lowest, hide_index=True, width="stretch")
            
            # --- 6. Top 5 Realtors (Lowest Price Count) ---
            st.markdown("#### 🏆 최저가 매물 최다 등록 부동산 (Top 5)")
            top_lp_realtors = full_lowest_df['realtorName'].value_counts().head(5).reset_index()
            top_lp_realtors.columns = ['부동산', '최저가 매물 수']
            st.dataframe(top_lp_realtors, hide_index=True, width="stretch")

    st.markdown("---")
    
    # --- 7. Weekly Activity (CUMULATIVE EVENTS + CHANGE LOG) ---
    st.subheader("📅 주간 부동산 활동 (Top 5 & 변동 로그)")
    st.caption("최근 1주일 (로그 상에 데이터가 있는 시간부터) 매 회차마다 발생한 신규/삭제 건수를 누적한 수치입니다.")

    # 1. Scope: Full History UP TO Current (to ensure we have prev for comparison)
    # But we want to 'Accumulate' only 7 days events.
    
    current_dt = pd.to_datetime(current_ts)
    seven_days_ago = current_dt - timedelta(days=7)
    
    history_up_to_now = view_df[view_df['timestamp'] <= current_ts].copy()
    
    # 2. Sequential Processing on FULL history allows computing diffs at the boundary
    sorted_ts = sorted(history_up_to_now['timestamp'].unique())
    
    cum_new_count = 0
    cum_del_count = 0
    realtor_new_counts = {}
    realtor_del_counts = {}
    change_events = []
    
    debug_logs = [] # Gather debug info
    
    if len(sorted_ts) > 1:
        # Group all data
        grouped = history_up_to_now.groupby('timestamp')
        ts_data_map = {}
        for ts, group in grouped:
            ts_data_map[ts] = dict(zip(group['articleNo'], group['realtorName']))
            
        prev_ts = sorted_ts[0]
        prev_items = ts_data_map[prev_ts]
        
        for i in range(1, len(sorted_ts)):
            curr_ts = sorted_ts[i]
            curr_dt = pd.to_datetime(curr_ts)
            
            curr_items = ts_data_map[curr_ts]
            
            # Check Filtering Condition: Is this event within Last 7 Days?
            if curr_dt > seven_days_ago:
                prev_ids = set(prev_items.keys())
                curr_ids = set(curr_items.keys())
                
                new_in_step = curr_ids - prev_ids
                del_in_step = prev_ids - curr_ids
                
                if new_in_step or del_in_step:
                    n_cnt = len(new_in_step)
                    d_cnt = len(del_in_step)
                    
                    # Anomaly Filter (User Request): Skip if change > 30 (likely refresh/glitch)
                    if n_cnt > 30 or d_cnt > 30:
                        debug_logs.append(f"[{curr_ts}] Skipped Anomaly (New: {n_cnt}, Del: {d_cnt})")
                    else:
                        cum_new_count += n_cnt
                        cum_del_count += d_cnt
                        
                        change_events.append({
                            "timestamp": curr_ts,
                            "prev_timestamp": prev_ts,
                            "new_count": n_cnt,
                            "del_count": d_cnt,
                            "new_ids": list(new_in_step),
                            "del_ids": list(del_in_step),
                            "display_ts": curr_dt.strftime("%m월 %d일 %H:%M")
                        })
                        
                        # Debug Log
                        debug_logs.append(f"[{curr_ts}] New: {n_cnt}, Del: {d_cnt}")
                        
                        for nid in new_in_step:
                            r_name = curr_items.get(nid, "알수없음")
                            realtor_new_counts[r_name] = realtor_new_counts.get(r_name, 0) + 1
                        
                        for did in del_in_step:
                            r_name = prev_items.get(did, "알수없음")
                            realtor_del_counts[r_name] = realtor_del_counts.get(r_name, 0) + 1
            else:
                pass 
                # debug_logs.append(f"[{curr_ts}] Skipped (Old: < {seven_days_ago})")

            # Update prev for next iteration
            prev_ts = curr_ts
            prev_items = curr_items

    # --- Summary Counts ---
    wc_total1, wc_total2 = st.columns(2)
    wc_total1.metric("1주일간 신규 등록 누적 건수", f"{cum_new_count}건")
    wc_total2.metric("1주일간 삭제된 누적 건수", f"{cum_del_count}건")
    
    # --- Top 5 Calculation ---
    if cum_new_count > 0 or cum_del_count > 0:
        c_new, c_del = st.columns(2)
        with c_new:
            st.markdown("##### ✨ 주간 최다 등록 부동산 (누적)")
            if realtor_new_counts:
                new_df = pd.DataFrame(list(realtor_new_counts.items()), columns=['부동산', '등록 건수'])
                new_df = new_df.sort_values('등록 건수', ascending=False).head(5)
                st.dataframe(new_df, hide_index=True, width="stretch")
            else:
                st.info("-")

        with c_del:
            st.markdown("##### 🗑️ 주간 최다 삭제 부동산 (누적)")
            if realtor_del_counts:
                del_df = pd.DataFrame(list(realtor_del_counts.items()), columns=['부동산', '삭제 건수'])
                del_df = del_df.sort_values('삭제 건수', ascending=False).head(5)
                st.dataframe(del_df, hide_index=True, width="stretch")
            else:
                st.info("-")
    else:
        st.info("최근 1주일간 변동 데이터가 없습니다.")

    st.markdown("---")
    
    # --- Change Log Interactive Table ---
    st.subheader("📜 주간 변동 상세 로그")
    st.caption("변동(추가/삭제)이 발생한 시점을 클릭하면 상세 내용을 볼 수 있습니다.")

    if change_events:
        log_df = pd.DataFrame(change_events)
        log_disp_df = log_df[['display_ts', 'new_count', 'del_count']].copy()
        log_disp_df.columns = ['일시', '신규 등록 (건)', '삭제 (건)']
        # Show Newest First
        log_disp_df = log_disp_df.iloc[::-1].reset_index(drop=True)
        
        sel_c_log = st.dataframe(
            log_disp_df, 
            width="stretch", 
            on_select="rerun", 
            selection_mode="single-row",
            key=f"tbl_change_log_{key_suffix}"
            )
        
        if sel_c_log.selection.rows:
            sel_row_idx = sel_c_log.selection.rows[0]
            # Map back to original log_df (log_df is ascending, display is descending)
            actual_idx = len(change_events) - 1 - sel_row_idx
            selected_event = change_events[actual_idx]
            
            sel_ts_str = selected_event['display_ts']
            
            st.divider()
            st.markdown(f"#### 🔍 {sel_ts_str} 상세 변동 내역")
            
            # --- New Details ---
            if selected_event['new_ids']:
                st.markdown(f"**🔹 신규 등록 ({selected_event['new_count']}건)**")
                e_ts = selected_event['timestamp']
                e_snapshot = history_up_to_now[history_up_to_now['timestamp'] == e_ts]
                e_new = e_snapshot[e_snapshot['articleNo'].isin(selected_event['new_ids'])]
                
                disp_cols = ['spc2', 'tradePrice', 'floorInfo', 'direction', 'buildingName', 'realtorName']
                start_disp = e_new[disp_cols].copy()
                start_disp.columns = ['면적', '가격', '층수', '향', '동', '중개사']
                st.dataframe(start_disp, hide_index=True)
            
            # --- Deleted Details ---
            if selected_event['del_ids']:
                st.markdown(f"**🔻 삭제됨 ({selected_event['del_count']}건)**")
                p_ts = selected_event['prev_timestamp']
                p_snapshot = history_up_to_now[history_up_to_now['timestamp'] == p_ts]
                e_del = p_snapshot[p_snapshot['articleNo'].isin(selected_event['del_ids'])]
                
                disp_cols = ['spc2', 'tradePrice', 'floorInfo', 'direction', 'buildingName', 'realtorName']
                del_disp = e_del[disp_cols].copy()
                del_disp.columns = ['면적', '가격', '층수', '향', '동', '중개사']
                st.dataframe(del_disp, hide_index=True)

    else:
        st.info("변동 이력이 없습니다.")
    
    # --- DEBUG SECTION ---
    with st.expander("🛠️ 디버그 정보 (개발용)", expanded=False):
        st.write(f"**Current TS**: {current_ts}")
        st.write(f"**7 Days Ago Ref**: {seven_days_ago}")
        st.write(f"**Snapshot Count**: {len(sorted_ts)}")
        st.write(f"**ArticleNo Type**: {df['articleNo'].dtype}")
        
        if debug_logs:
            st.write("Detected Events:")
            st.code("\n".join(debug_logs))
        else:
            st.write("No events detected in loop.")


# --- Main Layout with Tabs ---
tab1, tab2, tab3 = st.tabs(["📈 최신 현황", "🕰️ 히스토리", "🔎 매물 상세 분석"])

with tab1:
    if unique_timestamps:
        latest_ts = unique_timestamps[0]
        render_dashboard_view(filtered_df, latest_ts, unique_timestamps, key_suffix="latest")
    else:
        st.warning("데이터가 없습니다.")

with tab2:
    st.info("과거 시점의 데이터를 조회합니다.")
    
    if unique_timestamps:
        # Hierarchical Selection: Date -> Time
        
        # 1. Parse Dates safely (Robust Logic)
        ts_idx = pd.to_datetime(unique_timestamps, format='mixed', errors='coerce', utc=True)
        # Convert to Naive (strip timezone) for display consistency
        ts_idx = ts_idx.tz_localize(None)
        
        # Zip with original strings to keep mapping and filter NaT
        valid_pairs = []
        for orig, dt in zip(unique_timestamps, ts_idx):
             if pd.notna(dt):
                 valid_pairs.append((orig, dt))
        
        if not valid_pairs:
             st.error("유효한 날짜 데이터가 없습니다.")
        else:
             # Extract Dates
             date_set = sorted(list(set([p[1].strftime("%Y년 %m월 %d일") for p in valid_pairs])), reverse=True)
             
             c_h1, c_h2 = st.columns(2)
             with c_h1:
                sel_date_str = st.selectbox("📅 날짜 선택 (년-월-일)", date_set, key="hist_date_sel")
             
             if sel_date_str:
                 # Filter by date
                 filtered_pairs = [p for p in valid_pairs if p[1].strftime("%Y년 %m월 %d일") == sel_date_str]
                 # Sort by time Descending
                 filtered_pairs.sort(key=lambda x: x[1], reverse=True)
                 
                 filtered_ts_strs = [p[0] for p in filtered_pairs]
                 
                 with c_h2:
                     # Fixed 20-min slots for 24 hours
                     fixed_slots = []
                     for h in range(24):
                         for m in [0, 20, 40]:
                             fixed_slots.append(f"{h:02d}:{m:02d}")
                             
                     # Identify available times
                     available_times = set([p[1].strftime("%H:%M") for p in filtered_pairs])
                     
                     def format_slot(slot):
                         if slot in available_times:
                             return f"🔴 {slot} (데이터 있음)"
                         else:
                             return f"⚪ {slot} (수집 안됨)"

                     sel_time_slot = st.selectbox("⏰ 시간 선택 (수집 주기)", fixed_slots, format_func=format_slot)
                 
                 if sel_time_slot:
                      # Find matching data
                      matched_ts = None
                      # Prefer exact match? or just first that matches HH:MM
                      for p in filtered_pairs:
                          if p[1].strftime("%H:%M") == sel_time_slot:
                              matched_ts = p[0]
                              break
                      
                      if matched_ts:
                          st.divider()
                          render_dashboard_view(filtered_df, matched_ts, unique_timestamps, key_suffix="history")
                      else:
                          st.info(f"선택하신 시간({sel_time_slot})에 수집된 데이터가 없습니다.")
        
        with st.expander("🐞 데이터 기간 진단"):
            st.write(f"총 스냅샷 수: {len(unique_timestamps)}")
            if valid_pairs:
                min_dt = min([p[1] for p in valid_pairs])
                max_dt = max([p[1] for p in valid_pairs])
                st.write(f"데이터 범위: {min_dt} ~ {max_dt}")
                
            st.write(f"원본 타임스탬프 샘플(Top 5): {unique_timestamps[:5]}")
            if len(unique_timestamps) > 5:
                st.write(f"원본 타임스탬프 샘플(Tail 5): {unique_timestamps[-5:]}")

            if 'atclNm' in df.columns:
                 st.write("데이터 내 단지명(atclNm) 분포:")
                 st.write(df['atclNm'].value_counts())
    else:
        st.warning("데이터가 없습니다.")

with tab3:
    st.header("🕵️ 상세 분석 (최신 기준)")
    # Defaults to latest for now
    if unique_timestamps:
        latest_ts = unique_timestamps[0]
        latest_df = filtered_df[filtered_df['timestamp'] == latest_ts].copy()
        
        subtab1, subtab2 = st.tabs(["🏢 부동산(중개사)별", "🏙️ 동(Building)별"])
        
        with subtab1:
            if not latest_df.empty:
                realtor_counts = latest_df['realtorName'].value_counts().reset_index()
                realtor_counts.columns = ['realtorName', 'count']
                
                sel_r = st.dataframe(realtor_counts.head(20), width="stretch", on_select="rerun", selection_mode="single-row", key="tbl_realtor")
                
                if sel_r.selection.rows:
                    s_idx = sel_r.selection.rows[0]
                    s_real = realtor_counts.iloc[s_idx]['realtorName']
                    
                    st.divider()
                    st.markdown(f"#### '{s_real}' 상세")
                    
                    r_trend = filtered_df[filtered_df['realtorName'] == s_real].groupby('timestamp').size().reset_index(name='count')
                    r_trend['ts'] = pd.to_datetime(r_trend['timestamp'], format='mixed', errors='coerce', utc=True)
                    r_trend = r_trend.sort_values('ts')
                    
                    fig_r = px.line(r_trend, x='timestamp', y='count', markers=True, title="매물 등록 추이")
                    st.plotly_chart(fig_r, width="stretch", key="chart_realtor_trend")
                    
                    st.dataframe(latest_df[latest_df['realtorName'] == s_real], width="stretch", hide_index=True, key="tbl_realtor_detail")

        with subtab2:
            if not latest_df.empty:
                b_counts = latest_df['buildingName'].value_counts().reset_index()
                b_counts.columns = ['buildingName', 'count']
                
                sel_b = st.dataframe(b_counts, width="stretch", on_select="rerun", selection_mode="single-row", key="tbl_building")
                
                if sel_b.selection.rows:
                    s_idx_b = sel_b.selection.rows[0]
                    s_build = b_counts.iloc[s_idx_b]['buildingName']
                    
                    st.divider()
                    st.markdown(f"#### '{s_build}' 상세")
                    
                    b_trend = filtered_df[filtered_df['buildingName'] == s_build].groupby('timestamp').size().reset_index(name='count')
                    b_trend['ts'] = pd.to_datetime(b_trend['timestamp'], format='mixed', errors='coerce', utc=True)
                    b_trend = b_trend.sort_values('ts')
                    
                    fig_b = px.line(b_trend, x='timestamp', y='count', markers=True, title="매물 등록 추이")
                    st.plotly_chart(fig_b, width="stretch", key="chart_building_trend")
                    
                    st.dataframe(latest_df[latest_df['buildingName'] == s_build], width="stretch", hide_index=True, key="tbl_building_detail")
    
    # --- Moved All Data Table Here ---
    st.markdown("---")
    st.subheader("📋 전체 매물 데이터 (최신)")
    if unique_timestamps:
        st.dataframe(latest_df.sort_values(by="tradePrice", ascending=False), width="stretch", key="tbl_all_details")
    
    # Export
    csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("💾 CSV 다운로드", csv, "naver_land_data.csv", "text/csv")
