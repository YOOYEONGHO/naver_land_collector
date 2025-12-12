import streamlit as st
import pandas as pd
import plotly.express as px
import time
import streamlit.components.v1 as components
from utils import load_data

# Page Config
st.set_page_config(
    page_title="네이버 부동산 허위매물 분석 대시보드",
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
st.markdown("실시간 수집 데이터를 기반으로 한 매물 증감 및 이상 징후 분석 대시보드입니다.")

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


# --- Helper Function: Render Dashboard ---
def render_dashboard_view(view_df, current_ts, all_timestamps, key_suffix=""):
    """
    Renders the metrics, charts, and table for a specific timestamp.
    
    Args:
        view_df (pd.DataFrame): Dataframe filtered by complex (all history).
        current_ts (str): The specific timestamp to render.
        all_timestamps (list): List of all sorted timestamps (desc) for trend calc.
        key_suffix (str): Unique key suffix for widgets.
    """
    if not current_ts:
        st.error("데이터가 없습니다.")
        return

    ts_display = pd.to_datetime(current_ts).strftime("%Y/%m/%d %H:%M")
    
    # Snapshot at current_ts
    snapshot_df = view_df[view_df['timestamp'] == current_ts]
    latest_count = len(snapshot_df)
    avg_price = snapshot_df['price_int'].mean()
    
    # Calculate Diff vs Previous relative to current_ts
    # Find index of current_ts in all_timestamps
    try:
        curr_idx = all_timestamps.index(current_ts)
        # Prev is next index because sorted reverse=True (Newest first)
        prev_idx = curr_idx + 1
        
        if prev_idx < len(all_timestamps):
            prev_ts = all_timestamps[prev_idx]
            prev_snapshot = view_df[view_df['timestamp'] == prev_ts]
            
            count_diff = latest_count - len(prev_snapshot)
            
            # New Arrivals
            new_ids = set(snapshot_df['articleNo']) - set(prev_snapshot['articleNo'])
            new_listing_count = len(new_ids)
            
            # Deleted items
            deleted_ids = set(prev_snapshot['articleNo']) - set(snapshot_df['articleNo'])
            deleted_count = len(deleted_ids)
        else:
            count_diff = 0
            new_listing_count = 0
            deleted_count = 0
            new_ids = set()
            deleted_ids = set()
    except ValueError:
        # timestamp not found?
        count_diff = 0
        new_listing_count = 0
        deleted_count = 0
        new_ids = set()
        deleted_ids = set()

    # Metrics Row
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(f"매물 수 ({ts_display})", f"{latest_count}개")
    col2.metric(f"평균 가격", f"{avg_price/100000000:.2f} 억" if avg_price else "0 억")
    col3.metric("증감 (이전 대비)", f"{count_diff:+}개", delta=count_diff)
    col4.metric("신규 진입", f"{new_listing_count}개")
    col5.metric("삭제됨", f"{deleted_count}개")

    # --- Details for New/Deleted ---
    if new_listing_count > 0:
        with st.expander(f"🆕 신규 진입 매물 ({new_listing_count}개) 상세보기"):
            new_entries_df = snapshot_df[snapshot_df['articleNo'].isin(new_ids)].copy()
            # Select relevant columns for display
            disp_cols = ['spc2', 'tradePrice', 'floorInfo', 'direction', 'buildingName', 'realtorName']
            show_df = new_entries_df[disp_cols]
            show_df.columns = ['면적', '가격', '층수', '향', '동', '중개사']
            st.dataframe(show_df, hide_index=True)

    if deleted_count > 0:
        with st.expander(f"🗑️ 삭제된 매물 ({deleted_count}개) 상세보기"):
            # Get details from previous snapshot
            del_entries_df = prev_snapshot[prev_snapshot['articleNo'].isin(deleted_ids)].copy()
            disp_cols = ['spc2', 'tradePrice', 'floorInfo', 'direction', 'buildingName', 'realtorName']
            show_df = del_entries_df[disp_cols]
            show_df.columns = ['면적', '가격', '층수', '향', '동', '중개사']
            st.dataframe(show_df, hide_index=True)

    st.markdown("---")

    # --- Lowest Price Table ---
    st.subheader(f"📉 전용면적별 최저가 매물 ({ts_display})")
    if not snapshot_df.empty:
        idx = snapshot_df.groupby('spc2')['price_int'].idxmin()
        lowest_price_df = snapshot_df.loc[idx].sort_values('spc2')
        
        display_cols = ['spc2', 'tradePrice', 'floorInfo', 'direction', 'buildingName', 'realtorName']
        display_df = lowest_price_df[display_cols].copy()
        display_df.columns = ['전용면적', '가격', '층수', '향', '동', '중개사']
        st.dataframe(display_df, width="stretch", hide_index=True, key=f"tbl_lowest_{key_suffix}")

    st.markdown("---")

    # --- Charts ---
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        step = 100000000
        min_p = int(snapshot_df['price_int'].min()) if not snapshot_df.empty else 0
        max_p = int(snapshot_df['price_int'].max()) if not snapshot_df.empty else 0
        
        if max_p > min_p:
            tick_vals = list(range(min_p, max_p + step, step))
            def format_kr(x):
                 eok = x // 100000000
                 chun = (x % 100000000) // 10000
                 if chun == 0: return f"{eok}억"
                 elif chun == 5000: return f"{eok}억 5천"
                 else: return f"{x/100000000:.1f}억"
            tick_text = [format_kr(x) for x in tick_vals]
        else:
            tick_vals = []
            tick_text = []

        fig_hist = px.histogram(snapshot_df, x="price_int", nbins=20, title=f"매물 가격 분포 ({ts_display})")
        fig_hist.update_xaxes(tickformat=".1f", ticksuffix="억", title="가격 (원)", 
                              tickvals=tick_vals, ticktext=tick_text)
        st.plotly_chart(fig_hist, use_container_width=True, key=f"chart_price_dist_{key_suffix}")
        
    with col_c2:
        fig_area = px.histogram(snapshot_df, x="spc2", nbins=10, title="면적별 매물 분포")
        fig_area.update_xaxes(title="전용면적 (m²)")
        fig_area.update_yaxes(title="매물 수")
        st.plotly_chart(fig_area, use_container_width=True, key=f"chart_area_dist_{key_suffix}")

    # Trend Chart (Up to current_ts)
    # We filter data <= current_ts (to simulate history if we are in past)
    # But for 'Recent 10 trends', usually we want to see context leading up to this point.
    
    # Filter trend dataframe up to selected timestamp
    trend_view_df = view_df[view_df['timestamp'] <= current_ts]
    trend_agg = trend_view_df.groupby('timestamp').size().reset_index(name='count')
    trend_agg['timestamp_dt'] = pd.to_datetime(trend_agg['timestamp'])
    
    # Take last 10 points ending at current_ts
    trend_agg = trend_agg.sort_values('timestamp_dt').tail(10)
    
    trend_agg['xaxis_label'] = trend_agg['timestamp_dt'].dt.strftime("%Y/%m/%d %H:%M")
    
    fig_line = px.line(trend_agg, x='xaxis_label', y='count', markers=True, 
                       title=f"매물 수집 증감 추이 (~{ts_display})",
                       labels={"xaxis_label": "일시", "count": "매물 수"})
    
    if not trend_agg.empty:
        y_min = max(0, trend_agg['count'].min() - 10)
        y_max = trend_agg['count'].max() + 10
        fig_line.update_yaxes(tickformat="d", dtick=1, range=[y_min, y_max])
        
    fig_line.update_xaxes(type='category')
    
    # Highlight the current point
    # We can add a marker or just standard line is fine.
    
    st.plotly_chart(fig_line, use_container_width=True, key=f"chart_total_trend_{key_suffix}")

    st.markdown("---")
    st.subheader(f"📋 전체 매물 데이터 ({ts_display})")
    st.dataframe(snapshot_df.sort_values(by="tradePrice", ascending=False), width="stretch", key=f"tbl_all_{key_suffix}")


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
        # Selectbox for history
        # Format for display: "YYYY-MM-DD HH:MM (Count: N)"
        
        # Helper to format options
        timestamp_options = unique_timestamps
        
        sel_ts = st.selectbox("조회할 시점 선택", timestamp_options, key="hist_ts_selector")
        
        if sel_ts:
            render_dashboard_view(filtered_df, sel_ts, unique_timestamps, key_suffix="history")
    else:
        st.warning("데이터가 없습니다.")

with tab3:
    st.header("🕵️ 상세 분석 (최신 기준)")
    # Defaults to latest for now, or we could allow history here too, but user asked for "Dashboard" history.
    # We will keep this as "Analytics" typically on latest or all data.
    # Let's use latest_df for consistency with previous behavior.
    
    if unique_timestamps:
        latest_ts = unique_timestamps[0]
        latest_df = filtered_df[filtered_df['timestamp'] == latest_ts]
        
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
                    
                    # For trends in detail view, we show ALL history for that realtor
                    r_trend = filtered_df[filtered_df['realtorName'] == s_real].groupby('timestamp').size().reset_index(name='count')
                    r_trend['ts'] = pd.to_datetime(r_trend['timestamp'])
                    r_trend = r_trend.sort_values('ts')
                    
                    fig_r = px.line(r_trend, x='timestamp', y='count', markers=True, title="매물 등록 추이")
                    fig_r.update_yaxes(tickformat="d", dtick=1)
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
                    fig_b.update_yaxes(tickformat="d", dtick=1)
                    st.plotly_chart(fig_b, use_container_width=True, key="chart_building_trend")
                    
                    st.dataframe(latest_df[latest_df['buildingName'] == s_build], width="stretch", hide_index=True, key="tbl_building_detail")

    # Export (Always available in Detailed tab)
    csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("💾 CSV 다운로드", csv, "naver_land_data.csv", "text/csv")
