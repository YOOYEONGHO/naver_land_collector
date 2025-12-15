import streamlit as st
import pandas as pd
import plotly.express as px
import time
import streamlit.components.v1 as components
from utils import load_data
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


# Load Data
data = load_data()

if not data:
    st.info("데이터가 아직 수집되지 않았습니다. 서버(svrapp.py)에서 수집을 시작해주세요.")
    st.stop()

df = pd.DataFrame(data)

# Ensure columns
for col in ["buildingName", "realtorName", "direction"]:
    if col not in df.columns:
        df[col] = "정보없음"

df['price_eok'] = df['price_int'] / 100000000

# --- Sidebar: Filters Only ---
st.sidebar.header("🔎 분석 필터")

complexes = df['atclNm'].unique()
default_selection = []

if len(complexes) > 0:
    # Default to latest updated complex
    latest_complex = df.sort_values("timestamp", ascending=False).iloc[0]['atclNm']
    default_selection = [latest_complex]

selected_complex = st.sidebar.multiselect("단지 선택", complexes, default=default_selection)

if not selected_complex:
    st.warning("왼쪽 사이드바에서 단지를 선택해주세요.")
    st.image("https://via.placeholder.com/800x400?text=Select+Complex", width=600)
    st.stop()

filtered_df = df[df['atclNm'].isin(selected_complex)]
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
    st.markdown("### 📊 전체 현황")
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

    # --- 3. Trend Chart (Moved Up) ---
    st.subheader(f"📈 매물 수집 증감 추이 (~{ts_display})")
    
    trend_view_df = view_df[view_df['timestamp'] <= current_ts]
    trend_agg = trend_view_df.groupby('timestamp').size().reset_index(name='count')
    trend_agg['timestamp_dt'] = pd.to_datetime(trend_agg['timestamp'])
    trend_agg = trend_agg.sort_values('timestamp_dt').tail(20) # Show bit more history
    trend_agg['xaxis_label'] = trend_agg['timestamp_dt'].dt.strftime("%m/%d %H:%M")
    
    fig_line = px.line(trend_agg, x='xaxis_label', y='count', markers=True, 
                       labels={"xaxis_label": "일시", "count": "매물 수"})
    if not trend_agg.empty:
         y_min = max(0, trend_agg['count'].min() - 5)
         y_max = trend_agg['count'].max() + 5
         fig_line.update_yaxes(tickformat="d", dtick=1, range=[y_min, y_max])
    
    st.plotly_chart(fig_line, use_container_width=True, key=f"chart_trend_{key_suffix}")

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
            st.dataframe(top_lp_realtors, hide_index=True, use_container_width=True)

    st.markdown("---")
    
    # --- 7. Weekly Activity (CUMULATIVE EVENTS) ---
    st.subheader("📅 주간 부동산 활동 (Top 5)")
    st.caption("최근 1주일간 매 회차(약 20분)마다 발생한 신규/삭제 건수를 모두 누적한 수치입니다.")

    # 1. Filter Period (Up to Current View)
    history_up_to_now = view_df[view_df['timestamp'] <= current_ts].copy()
    history_up_to_now['timestamp_dt'] = pd.to_datetime(history_up_to_now['timestamp'])
    
    current_dt = pd.to_datetime(current_ts)
    seven_days_ago = current_dt - timedelta(days=7)
    
    period_df = history_up_to_now[history_up_to_now['timestamp_dt'] > seven_days_ago]
    
    # 2. Sequential Processing
    # Sort unique timestamps ASCENDING
    sorted_ts = sorted(period_df['timestamp'].unique())
    
    cum_new_count = 0
    cum_del_count = 0
    
    realtor_new_counts = {}
    realtor_del_counts = {}
    
    # We Iterate from i=1. The snapshot at i=0 is the START STATE (Baseline).
    # New items appearing in snapshot[0] are NOT counted, as they were "already there".
    # Only changes from 0->1, 1->2... count.
    
    if len(sorted_ts) > 1:
        # Pre-group by timestamp to avoid repeatedly filtering the big DF
        grouped = period_df.groupby('timestamp')
        
        # Get set of IDs and Realtor mapping for each timestamp
        # Optimization: Build a dict of {ts: {id: realtor_name}}
        ts_data_map = {}
        for ts, group in grouped:
            # We use dict for fast lookup of realtor by ID
            ts_data_map[ts] = dict(zip(group['articleNo'], group['realtorName']))
            
        # Iterate
        prev_ts = sorted_ts[0]
        prev_items = ts_data_map[prev_ts] # dict {id: realtor}
        
        for i in range(1, len(sorted_ts)):
            curr_ts = sorted_ts[i]
            curr_items = ts_data_map[curr_ts]
            
            prev_ids = set(prev_items.keys())
            curr_ids = set(curr_items.keys())
            
            # Identify Changes
            new_in_step = curr_ids - prev_ids
            del_in_step = prev_ids - curr_ids
            
            # Accumulate Total Counts
            cum_new_count += len(new_in_step)
            cum_del_count += len(del_in_step)
            
            # Accumulate Realtor Counts
            # For New: Use Realtor info from Current
            for nid in new_in_step:
                r_name = curr_items.get(nid, "알수없음")
                realtor_new_counts[r_name] = realtor_new_counts.get(r_name, 0) + 1
            
            # For Deleted: Use Realtor info from Previous (when it existed)
            for did in del_in_step:
                r_name = prev_items.get(did, "알수없음")
                realtor_del_counts[r_name] = realtor_del_counts.get(r_name, 0) + 1
            
            # Move Next
            prev_ts = curr_ts
            prev_items = curr_items
            
    else:
        # Only 1 snapshot exists (Fresh start). No changes yet.
        pass


    # --- Summary Counts ---
    wc_total1, wc_total2 = st.columns(2)
    wc_total1.metric("1주일간 신규 등록 누적 건수", f"{cum_new_count}건")
    wc_total2.metric("1주일간 삭제된 누적 건수", f"{cum_del_count}건")
    
    # --- Top 5 Calculation ---
    if cum_new_count > 0 or cum_del_count > 0:
        c_new, c_del = st.columns(2)
        
        # New Top 5
        with c_new:
            st.markdown("##### ✨ 주간 최다 등록 부동산 (누적)")
            if realtor_new_counts:
                # Convert dict to df
                new_df = pd.DataFrame(list(realtor_new_counts.items()), columns=['부동산', '등록 건수'])
                new_df = new_df.sort_values('등록 건수', ascending=False).head(5)
                st.dataframe(new_df, hide_index=True, use_container_width=True)
            else:
                st.info("신규 등록 없음")

        # Deleted Top 5
        with c_del:
            st.markdown("##### 🗑️ 주간 최다 삭제 부동산 (누적)")
            if realtor_del_counts:
                del_df = pd.DataFrame(list(realtor_del_counts.items()), columns=['부동산', '삭제 건수'])
                del_df = del_df.sort_values('삭제 건수', ascending=False).head(5)
                st.dataframe(del_df, hide_index=True, use_container_width=True)
            else:
                st.info("삭제된 매물 없음")
    else:
        st.info("최근 1주일간 변동 데이터가 없습니다.")


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
        # Helper to format options for Korean Context
        ts_options_map = {ts: pd.to_datetime(ts).strftime("%Y년 %m월 %d일 %H:%M") for ts in unique_timestamps}
        
        sel_ts = st.selectbox("조회할 시점 선택", unique_timestamps, 
                              format_func=lambda x: ts_options_map[x],
                              key="hist_ts_selector")
        
        if sel_ts:
            render_dashboard_view(filtered_df, sel_ts, unique_timestamps, key_suffix="history")
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
                    r_trend['ts'] = pd.to_datetime(r_trend['timestamp'])
                    r_trend = r_trend.sort_values('ts')
                    
                    fig_r = px.line(r_trend, x='timestamp', y='count', markers=True, title="매물 등록 추이")
                    st.plotly_chart(fig_r, use_container_width=True, key="chart_realtor_trend")
                    
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
                    b_trend['ts'] = pd.to_datetime(b_trend['timestamp'])
                    b_trend = b_trend.sort_values('ts')
                    
                    fig_b = px.line(b_trend, x='timestamp', y='count', markers=True, title="매물 등록 추이")
                    st.plotly_chart(fig_b, use_container_width=True, key="chart_building_trend")
                    
                    st.dataframe(latest_df[latest_df['buildingName'] == s_build], width="stretch", hide_index=True, key="tbl_building_detail")
    
    # --- Moved All Data Table Here ---
    st.markdown("---")
    st.subheader("📋 전체 매물 데이터 (최신)")
    if unique_timestamps:
        st.dataframe(latest_df.sort_values(by="tradePrice", ascending=False), width="stretch", key="tbl_all_details")
    
    # Export
    csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("💾 CSV 다운로드", csv, "naver_land_data.csv", "text/csv")
