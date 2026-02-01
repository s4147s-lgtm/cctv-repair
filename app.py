import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime

# ========== 페이지 설정 ==========
st.set_page_config(
    page_title="📹 CCTV 수리내역",
    page_icon="📹",
    layout="wide"
)

# ========== Supabase 연결 ==========
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# ========== 스타일 ==========
st.markdown("""
<style>
    .main {font-family: 'Malgun Gothic', sans-serif;}
    .stSelectbox label {font-weight: bold;}
    .result-count {
        font-size: 1.3em; 
        color: #1f77b4; 
        font-weight: bold;
        padding: 10px;
        background: #e7f3ff;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# ========== 필터 옵션 로드 ==========
@st.cache_data(ttl=300)
def load_options():
    """콤보박스용 옵션 (5분 캐시)"""
    all_data = supabase.table("repairs").select("*").execute().data
    
    regions = sorted(set([d['region'] for d in all_data if d.get('region')]))
    sites = sorted(set([d['site_name'] for d in all_data if d.get('site_name')]))
    cameras = sorted(set([d['camera_type'] for d in all_data if d.get('camera_type')]))
    inspectors = sorted(set([d['inspector'] for d in all_data if d.get('inspector')]))
    years = sorted(set([d['repair_year'] for d in all_data if d.get('repair_year')]), reverse=True)
    
    return regions, sites, cameras, inspectors, years

# ========== 메인 ==========
st.title("📹 CCTV 수리내역 관리")

# 탭
tab1, tab2, tab3 = st.tabs(["🔍 조회", "➕ 등록", "📊 통계"])

# ========== 탭1: 조회 ==========
with tab1:
    st.header("🔍 수리내역 조회")
    
    regions, sites, cameras, inspectors, years = load_options()
    
    # 필터 UI
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        sel_region = st.selectbox("📍 지역", ["전체"] + regions)
    with col2:
        sel_site = st.selectbox("🏢 현장명", ["전체"] + sites)
    with col3:
        sel_year = st.selectbox("📅 년도", ["전체"] + [str(y) for y in years])
    with col4:
        sel_month = st.selectbox("📅 월", ["전체"] + [f"{m}월" for m in range(1, 13)])
    
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        sel_camera = st.selectbox("📷 카메라종류", ["전체"] + cameras)
    with col6:
        sel_inspector = st.selectbox("👤 점검자", ["전체"] + inspectors)
    with col7:
        use_or = st.checkbox("OR 검색", value=False)
    with col8:
        st.write("")
        st.write("")
        search_btn = st.button("🔍 검색", type="primary", use_container_width=True)
    
    # 검색 실행
    if search_btn:
        query = supabase.table("repairs").select("*", count="exact")
        
        # 조건 적용
        conditions = []
        if sel_region != "전체":
            if not use_or:
                query = query.eq("region", sel_region)
            else:
                conditions.append(f"region.eq.{sel_region}")
        
        if sel_site != "전체":
            if not use_or:
                query = query.eq("site_name", sel_site)
            else:
                conditions.append(f"site_name.eq.{sel_site}")
        
        if sel_year != "전체":
            if not use_or:
                query = query.eq("repair_year", int(sel_year))
            else:
                conditions.append(f"repair_year.eq.{sel_year}")
        
        if sel_month != "전체":
            month_num = int(sel_month.replace("월", ""))
            if not use_or:
                query = query.eq("repair_month", month_num)
            else:
                conditions.append(f"repair_month.eq.{month_num}")
        
        if sel_camera != "전체":
            if not use_or:
                query = query.eq("camera_type", sel_camera)
            else:
                conditions.append(f"camera_type.eq.{sel_camera}")
        
        if sel_inspector != "전체":
            if not use_or:
                query = query.eq("inspector", sel_inspector)
            else:
                conditions.append(f"inspector.eq.{sel_inspector}")
        
        # OR 검색 적용
        if use_or and conditions:
            query = query.or_(",".join(conditions))
        
        result = query.order("created_at", desc=True).execute()
        
        # 결과 표시
        st.markdown(f"<div class='result-count'>📊 검색 결과: {len(result.data):,}건</div>", 
                   unsafe_allow_html=True)
        
        if result.data:
            df = pd.DataFrame(result.data)
            df_display = df[['region', 'site_name', 'repair_year', 'repair_month', 
                           'repair_detail', 'camera_type', 'inspector', 'created_at']].copy()
            df_display.columns = ['지역', '현장명', '년도', '월', '고장수리내역', 
                                 '카메라종류', '점검자', '등록일시']
            
            st.dataframe(df_display, use_container_width=True, height=500)
            
            # 엑셀 다운로드
            csv = df_display.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "📥 CSV 다운로드",
                csv,
                f"수리내역_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv"
            )

# ========== 탭2: 등록 ==========
with tab2:
    st.header("➕ 수리내역 등록")
    
    regions, sites, cameras, inspectors, _ = load_options()
    
    with st.form("repair_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            region_opt = st.selectbox("📍 지역", ["직접입력"] + regions, key="reg_region")
            if region_opt == "직접입력":
                new_region = st.text_input("새 지역 입력")
            else:
                new_region = region_opt
            
            site_opt = st.selectbox("🏢 현장명", ["직접입력"] + sites, key="reg_site")
            if site_opt == "직접입력":
                new_site = st.text_input("새 현장명 입력")
            else:
                new_site = site_opt
            
            col_y, col_m = st.columns(2)
            with col_y:
                new_year = st.selectbox("년도", list(range(2024, 2019, -1)))
            with col_m:
                new_month = st.selectbox("월", list(range(1, 13)))
        
        with col2:
            camera_opt = st.selectbox("📷 카메라종류", ["직접입력"] + cameras, key="reg_camera")
            if camera_opt == "직접입력":
                new_camera = st.text_input("새 카메라종류")
            else:
                new_camera = camera_opt
            
            inspector_opt = st.selectbox("👤 점검자", ["직접입력"] + inspectors, key="reg_inspector")
            if inspector_opt == "직접입력":
                new_inspector = st.text_input("새 점검자")
            else:
                new_inspector = inspector_opt
        
        new_detail = st.text_area("🔧 고장수리내역", height=150)
        
        submitted = st.form_submit_button("✅ 등록", type="primary", use_container_width=True)
        
        if submitted:
            if not new_site or not new_region:
                st.error("지역과 현장명은 필수입니다!")
            else:
                supabase.table("repairs").insert({
                    "region": new_region,
                    "site_name": new_site,
                    "repair_year": new_year,
                    "repair_month": new_month,
                    "repair_detail": new_detail,
                    "camera_type": new_camera,
                    "inspector": new_inspector
                }).execute()
                
                st.success("✅ 등록 완료!")
                st.balloons()
                load_options.clear()

# ========== 탭3: 통계 ==========
with tab3:
    st.header("📊 통계")
    
    all_data = supabase.table("repairs").select("*").execute()
    
    if all_data.data:
        df = pd.DataFrame(all_data.data)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("총 수리건수", f"{len(df):,}건")
        with col2:
            st.metric("현장수", f"{df['site_name'].nunique():,}개")
        with col3:
            st.metric("지역수", f"{df['region'].nunique():,}개")
        with col4:
            st.metric("점검자수", f"{df['inspector'].nunique():,}명")
        
        st.subheader("📍 지역별 현황")
        region_counts = df['region'].value_counts()
        st.bar_chart(region_counts)
        
        st.subheader("📷 카메라종류별 현황")
        camera_counts = df['camera_type'].value_counts()
        st.bar_chart(camera_counts)
