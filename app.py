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

# Default complex ID (e.g., Eunma Apt: 1116, Mapo Raemian Purgio: 104253)
complex_id = st.sidebar.text_input("단지 식별 번호 (hscpNo)", value="108064", help="네이버 부동산 단지 페이지 URL에서 확인 가능합니다.")
trade_type_map = {"매매 (Sale)": "A1", "전세 (Jeonse)": "B1", "월세 (Rent)": "B2"}
trade_type_label = st.sidebar.selectbox("매물 종류", list(trade_type_map.keys()))
trade_type_code = trade_type_map[trade_type_label]

if st.sidebar.button("🚀 매물 수집 시작"):
    with st.spinner(f"단지 ID {complex_id} 데이터 수집 중..."):
        try:
            crawler = NaverLandCrawler()
            new_data = crawler.fetch_listings(complex_no=complex_id, trade_type=trade_type_code)
            
            if new_data:
                save_data(new_data)
                st.sidebar.success(f"{len(new_data)}건의 매물을 수집했습니다!")
            else:
                st.sidebar.warning("매물을 찾을 수 없거나 API가 변경되었습니다.")
        except Exception as e:
            st.sidebar.error(f"오류 발생: {e}")

# Auto Collection Logic
st.sidebar.markdown("---")
st.sidebar.header("🔄 자동 수집")
auto_collect = st.sidebar.checkbox("자동 수집 모드 활성화")
interval_min = st.sidebar.number_input("수집 주기 (분)", min_value=1, value=30, step=1)

if auto_collect:
    placeholder = st.sidebar.empty()
    placeholder.info(f"자동 모드 동작 중... ({interval_min}분 주기)")
    
    # Check if we should run (simplified logic: just run and sleep, limiting interactivity)
    # Ideally, we would track last_run in session_state, but for a blocking script:
    with st.spinner(f"자동 수집 중... (주기: {interval_min}분)"):
        try:
            crawler = NaverLandCrawler()
            # Auto collect using the input complex ID
            new_data = crawler.fetch_listings(complex_no=complex_id, trade_type=trade_type_code)
            if new_data:
                save_data(new_data)
                st.toast(f"자동 수집 완료: {len(new_data)}건")
        except Exception as e:
            st.error(f"자동 수집 오류: {e}")
            
    # Wait loop
    for i in range(interval_min * 60, 0, -1):
        placeholder.info(f"다음 수집까지 {i}초 남음...")
        time.sleep(1)
    st.rerun()

# Main Content
st.markdown("---")

# Load Data
data = load_data()

if not data:
    st.info("수집된 데이터가 없습니다. 왼쪽 사이드바에서 수집을 시작해주세요.")
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

    # Metrics Logic (Snapshot based)
    
    # 1. Identify the 'Latest' snapshot time for the selected filtered data
    unique_timestamps = sorted(filtered_df['timestamp'].unique(), reverse=True)
    
    if not unique_timestamps:
        latest_count = 0
        avg_price = 0
        new_listing_count = 0
    else:
        latest_ts = unique_timestamps[0]
        latest_snapshot = filtered_df[filtered_df['timestamp'] == latest_ts]
        
        # Metric 1: Current Active Listings (Latest Snapshot Count)
        latest_count = len(latest_snapshot)
        
        # Metric 2: Avg Price of Latest Snapshot
        avg_price = latest_snapshot['price_int'].mean()
        
        # Metric 3: New Listings (Latest vs Previous)
        if len(unique_timestamps) > 1:
            prev_ts = unique_timestamps[1]
            prev_snapshot = filtered_df[filtered_df['timestamp'] == prev_ts]
            
            # Find listings in Latest that were NOT in Previous (by articleNo)
            new_items = latest_snapshot[~latest_snapshot['articleNo'].isin(prev_snapshot['articleNo'])]
            new_listing_count = len(new_items)
        else:
            # If only one snapshot exists, everything is "new" or 0 depending on definition. 
            # Usually users want to know what changed. If first run, maybe N/A or just count.
            # Let's show 0 as baseline or count. User asked "added listings compared to previous".
            # If no previous, 0 is safer representation of "change".
            new_listing_count = 0

    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("현재 매물 수 (최신)", latest_count)
    with m2:
        # Format large number
        st.metric("평균 가격 (최신)", f"{avg_price/100000000:.2f} 억" if avg_price else "0 억")
    with m3:
        st.metric("신규 매물 (이전 대비)", f"+{new_listing_count}" if new_listing_count > 0 else str(new_listing_count))

    # Charts
    st.subheader("📊 데이터 시각화 분석")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("### 가격대 분포")
        # Histogram with custom binning or just x-axis format
        # Use price_eok for 억 unit
        fig_hist = px.histogram(filtered_df, x="price_eok", nbins=20, title="가격대 분포 (단위: 억원)", 
                                labels={"price_eok": "가격 (억원)"})
        # Update x-axis to show 1 decimal
        fig_hist.update_layout(xaxis=dict(tickformat=".1f", ticksuffix="억"))
        st.plotly_chart(fig_hist, width="stretch")
        
    with c2:
        st.markdown("### 가격 vs 면적 (미끼매물 탐지)")
        # Scatter
        fig_scatter = px.scatter(filtered_df, x="spc2", y="price_eok", color="floorInfo", 
                                 hover_data=["atclNm", "buildingName", "tradePrice", "realtorName"], 
                                 title="전용면적 vs 가격 (단위: 억원)",
                                 labels={"price_eok": "가격 (억원)", "spc2": "전용면적 (m²)"})
        # Update y-axis to show 1 decimal
        fig_scatter.update_layout(yaxis=dict(tickformat=".0f", ticksuffix="억"))
        st.plotly_chart(fig_scatter, width="stretch")

    # New Chart: Area Distribution (Histogram standard)
    st.markdown("### 면적별 매물 수")
    # Use histogram matching price distribution style
    fig_area = px.histogram(filtered_df, x='spc2', title="면적별 매물 수", 
                      labels={"spc2": "전용면적 (m²)"}).update_yaxes(title="매물 수")
    st.plotly_chart(fig_area, width="stretch")

    # Timeline of Collections
    st.markdown("### 📈 시간대별 수집 매물 수 변화")
    if 'timestamp' in filtered_df.columns:
        # Group by EXACT timestamp (Snapshot)
        trend_df = filtered_df.groupby('timestamp').size().reset_index(name='count')
        # Sort by timestamp
        trend_df = trend_df.sort_values('timestamp')
        
        fig_line = px.line(trend_df, x='timestamp', y='count', markers=True, 
                           title="매물 수집 시점별 매물 수 변화",
                           labels={"timestamp": "수집 일시", "count": "매물 수 (개)"})
        st.plotly_chart(fig_line, width="stretch")

    # Advanced Analysis: Realtor & Building
    st.markdown("---")
    st.subheader("🕵️ 부동산 및 동별 상세 분석")
    st.info("표에서 행을 클릭하면 해당 항목의 **시간대별 매물 수 변화**를 아래 그래프로 확인할 수 있습니다.")
    
    t1, t2 = st.tabs(["부동산(중개사)별 분석", "동(Building)별 분석"])
    
    # 1. Realtor Analysis
    with t1:
        if 'latest_snapshot' in locals() and not latest_snapshot.empty:
            # Count by Realtor in Latest Snapshot
            realtor_counts = latest_snapshot['realtorName'].value_counts().reset_index()
            realtor_counts.columns = ['중개사명', '매물수']
            
            # Interactive Dataframe
            st.markdown("##### 중개사별 보유 매물 현황 (최신)")
            selection_realtor = st.dataframe(realtor_counts, width="stretch", 
                                           on_select="rerun", selection_mode="single-row",
                                           hide_index=True)
            
            # Drill down chart
            if selection_realtor and selection_realtor["selection"]["rows"]:
                selected_idx = selection_realtor["selection"]["rows"][0]
                target_realtor = realtor_counts.iloc[selected_idx]['중개사명']
                
                st.markdown(f"**📉 '{target_realtor}' 매물 수 변화 추이**")
                
                # Filter history for this realtor
                realtor_history = filtered_df[filtered_df['realtorName'] == target_realtor]
                # Group by timestamp
                r_trend = realtor_history.groupby('timestamp').size().reset_index(name='count')
                
                fig_r = px.line(r_trend, x='timestamp', y='count', markers=True,
                                labels={"timestamp": "수집 일시", "count": "매물 수"})
                st.plotly_chart(fig_r, width="stretch")
                
                # Show Listing Details for this Realtor
                st.markdown(f"**📋 '{target_realtor}' 매물 목록 (최신)**")
                # Filter from latest_snapshot
                realtor_listings = latest_snapshot[latest_snapshot['realtorName'] == target_realtor]
                # Columns to show
                display_cols = ['articleNo', 'spc2', 'buildingName', 'floorInfo', 'tradePrice', 'direction', 'atclFetrDesc']
                # Check if columns exist
                available_cols = [c for c in display_cols if c in realtor_listings.columns]
                
                st.dataframe(realtor_listings[available_cols], width="stretch", hide_index=True)
        else:
            st.warning("분석할 최신 데이터가 없습니다.")

    # 2. Building Analysis
    with t2:
        if 'latest_snapshot' in locals() and not latest_snapshot.empty:
            # Count by Building in Latest Snapshot
            build_counts = latest_snapshot['buildingName'].value_counts().reset_index()
            build_counts.columns = ['동(Building)', '매물수']
            
            # Interactive Dataframe
            st.markdown("##### 동별 매물 현황 (최신)")
            selection_build = st.dataframe(build_counts, width="stretch", 
                                           on_select="rerun", selection_mode="single-row", 
                                           hide_index=True)
            
            # Drill down chart
            if selection_build and selection_build["selection"]["rows"]:
                selected_idx = selection_build["selection"]["rows"][0]
                target_build = build_counts.iloc[selected_idx]['동(Building)']
                
                st.markdown(f"**📉 '{target_build}' 매물 수 변화 추이**")
                
                # Filter history
                build_history = filtered_df[filtered_df['buildingName'] == target_build]
                b_trend = build_history.groupby('timestamp').size().reset_index(name='count')
                
                fig_b = px.line(b_trend, x='timestamp', y='count', markers=True,
                                labels={"timestamp": "수집 일시", "count": "매물 수"})
                st.plotly_chart(fig_b, width="stretch")
                
                # Show Listing Details for this Building
                st.markdown(f"**📋 '{target_build}' 매물 목록 (최신)**")
                # Filter from latest_snapshot
                build_listings = latest_snapshot[latest_snapshot['buildingName'] == target_build]
                # Columns to show
                display_cols_b = ['articleNo', 'buildingName', 'floorInfo', 'spc2', 'tradePrice', 'direction', 'realtorName', 'atclFetrDesc']
                # Check if columns exist
                available_cols_b = [c for c in display_cols_b if c in build_listings.columns]
                
                st.dataframe(build_listings[available_cols_b], width="stretch", hide_index=True)
        else:
            st.warning("분석할 최신 데이터가 없습니다.")

    # Main Grid (Keep at bottom)

    # Raw Data Grid
    st.subheader("📋 상세 수집 기록 (최신 데이터 기준)")
    if 'latest_snapshot' in locals() and not latest_snapshot.empty:
        display_df = latest_snapshot.sort_values(by="tradePrice", ascending=False).reset_index(drop=True)
        # 1-based index
        display_df.index = display_df.index + 1
        st.dataframe(display_df, width="stretch")
    else:
        st.markdown("표시할 최신 데이터가 없습니다.")
    
    # Export
    # Convert DF to CSV for download
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
    import os
    if os.path.exists("data.json"):
        os.remove("data.json")
        st.cache_data.clear() # Clear cache if using it, though we use load_data direct
        st.sidebar.success("모든 데이터가 삭제되었습니다! 페이지를 새로고침하세요.")
        st.rerun()
    else:
        st.sidebar.warning("삭제할 데이터 파일이 없습니다.")
