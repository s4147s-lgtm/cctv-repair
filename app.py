import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
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
tab1, tab2, tab3, tab4 = st.tabs(["🔍 조회", "➕ 등록", "✏️ 수정/삭제", "📊 통계"])

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
            
            # 수정탭과 공유하기 위해 세션에 저장 (id 포함)
            st.session_state["search_df"] = df.copy()
            
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
                new_year = st.selectbox("년도", list(range(datetime.now().year, datetime.now().year - 6, -1)))
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

# ========== 탭3: 수정/삭제 ==========
with tab3:
    st.header("✏️ 수리내역 수정 / 삭제")
    
    regions, sites, cameras, inspectors, years = load_options()
    
    # 조회탭에서 검색한 데이터가 있으면 활용, 아니면 전체 로드
    if "search_df" in st.session_state and not st.session_state["search_df"].empty:
        edit_df = st.session_state["search_df"].copy()
        st.info("💡 조회탭의 검색 결과를 표시합니다. 다른 데이터를 찾으려면 아래 검색을 사용하세요.")
    else:
        edit_df = pd.DataFrame(supabase.table("repairs").select("*").order("created_at", desc=True).execute().data)
    
    # 수정탭 내부 검색
    st.subheader("🔎 검색")
    ecol1, ecol2, ecol3, ecol4 = st.columns(4)
    with ecol1:
        e_region = st.selectbox("지역", ["전체"] + regions, key="edit_region")
    with ecol2:
        e_site = st.selectbox("현장명", ["전체"] + sites, key="edit_site")
    with ecol3:
        e_inspector = st.selectbox("점검자", ["전체"] + inspectors, key="edit_inspector")
    with ecol4:
        st.write("")
        e_search = st.button("🔎 검색", type="primary", use_container_width=True, key="edit_search_btn")
    
    if e_search:
        q = supabase.table("repairs").select("*")
        if e_region != "전체":
            q = q.eq("region", e_region)
        if e_site != "전체":
            q = q.eq("site_name", e_site)
        if e_inspector != "전체":
            q = q.eq("inspector", e_inspector)
        edit_df = pd.DataFrame(q.order("created_at", desc=True).execute().data)
    
    if not edit_df.empty:
        # 행 선택용 표시 (번호 + 핵심 정보)
        edit_df_view = edit_df[['region', 'site_name', 'repair_year', 'repair_month',
                                'camera_type', 'inspector', 'repair_detail']].copy()
        edit_df_view.columns = ['지역', '현장명', '년도', '월', '카메라종류', '점검자', '고장수리내역']
        edit_df_view.index = edit_df_view.index + 1  # 1부터 시작
        
        st.subheader("📋 수정할 행 선택")
        st.dataframe(edit_df_view, use_container_width=True, height=300)
        
        sel_idx = st.number_input("수정/삭제할 행 번호", min_value=1, max_value=len(edit_df), step=1, key="edit_sel_idx")
        
        # 선택한 행의 원본 데이터
        selected_row = edit_df.iloc[sel_idx - 1]
        row_id = selected_row["id"]
        
        st.divider()
        
        # ─── 수정 폼 ───
        st.subheader(f"✏️ 수정 폼 (행 {sel_idx})")
        
        with st.form("edit_form", clear_on_submit=False):
            ecol_l, ecol_r = st.columns(2)
            
            with ecol_l:
                # 지역
                region_choices = ["직접입력"] + regions
                r_idx = region_choices.index(selected_row["region"]) if selected_row["region"] in region_choices else 0
                edit_region_opt = st.selectbox("📍 지역", region_choices, index=r_idx, key="ef_region")
                if edit_region_opt == "직접입력":
                    edit_region = st.text_input("새 지역 입력", value="" if r_idx == 0 else selected_row["region"], key="ef_region_txt")
                else:
                    edit_region = edit_region_opt
                
                # 현장명
                site_choices = ["직접입력"] + sites
                s_idx = site_choices.index(selected_row["site_name"]) if selected_row["site_name"] in site_choices else 0
                edit_site_opt = st.selectbox("🏢 현장명", site_choices, index=s_idx, key="ef_site")
                if edit_site_opt == "직접입력":
                    edit_site = st.text_input("새 현장명 입력", value="" if s_idx == 0 else selected_row["site_name"], key="ef_site_txt")
                else:
                    edit_site = edit_site_opt
                
                # 년도 / 월
                year_list = list(range(datetime.now().year, datetime.now().year - 6, -1))
                y_idx = year_list.index(selected_row["repair_year"]) if selected_row["repair_year"] in year_list else 0
                ecol_yl, ecol_ml = st.columns(2)
                with ecol_yl:
                    edit_year = st.selectbox("년도", year_list, index=y_idx, key="ef_year")
                with ecol_ml:
                    month_list = list(range(1, 13))
                    m_idx = month_list.index(selected_row["repair_month"]) if selected_row["repair_month"] in month_list else 0
                    edit_month = st.selectbox("월", month_list, index=m_idx, key="ef_month")
            
            with ecol_r:
                # 카메라종류
                cam_choices = ["직접입력"] + cameras
                c_idx = cam_choices.index(selected_row["camera_type"]) if selected_row["camera_type"] in cam_choices else 0
                edit_cam_opt = st.selectbox("📷 카메라종류", cam_choices, index=c_idx, key="ef_camera")
                if edit_cam_opt == "직접입력":
                    edit_camera = st.text_input("새 카메라종류", value="" if c_idx == 0 else selected_row["camera_type"], key="ef_camera_txt")
                else:
                    edit_camera = edit_cam_opt
                
                # 점검자
                insp_choices = ["직접입력"] + inspectors
                i_idx = insp_choices.index(selected_row["inspector"]) if selected_row["inspector"] in insp_choices else 0
                edit_insp_opt = st.selectbox("👤 점검자", insp_choices, index=i_idx, key="ef_inspector")
                if edit_insp_opt == "직접입력":
                    edit_inspector = st.text_input("새 점검자", value="" if i_idx == 0 else selected_row["inspector"], key="ef_inspector_txt")
                else:
                    edit_inspector = edit_insp_opt
            
            # 고장수리내역
            edit_detail = st.text_area("🔧 고장수리내역", value=selected_row.get("repair_detail", ""), height=150, key="ef_detail")
            
            edit_submit = st.form_submit_button("✅ 수정 저장", type="primary", use_container_width=True)
        
        if edit_submit:
            if not edit_region or not edit_site:
                st.error("지역과 현장명은 필수입니다!")
            else:
                supabase.table("repairs").update({
                    "region": edit_region,
                    "site_name": edit_site,
                    "repair_year": edit_year,
                    "repair_month": edit_month,
                    "repair_detail": edit_detail,
                    "camera_type": edit_camera,
                    "inspector": edit_inspector
                }).eq("id", row_id).execute()
                
                st.success("✅ 수정 완료!")
                load_options.clear()
                if "search_df" in st.session_state:
                    del st.session_state["search_df"]
                st.rerun()
        
        # ─── 삭제 영역 ───
        st.divider()
        st.subheader(f"🗑️ 삭제 (행 {sel_idx})")
        st.warning(f"삭제할 내용: **{selected_row['region']} | {selected_row['site_name']} | {selected_row['repair_year']}년 {selected_row['repair_month']}월 | {selected_row['inspector']}**")
        
        del_confirm = st.checkbox("위 내용을 삭제할 것을 확인합니다.", key="del_confirm")
        del_btn = st.button("🗑️ 삭제", type="secondary", disabled=not del_confirm, use_container_width=False, key="del_btn")
        
        if del_btn:
            supabase.table("repairs").delete().eq("id", row_id).execute()
            st.success("✅ 삭제 완료!")
            load_options.clear()
            if "search_df" in st.session_state:
                del st.session_state["search_df"]
            st.rerun()
    else:
        st.info("검색 결과가 없습니다.")

# ========== 탭4: 통계 ==========
with tab4:
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
        region_counts = df['region'].value_counts().reset_index()
        region_counts.columns = ['지역', '건수']
        fig1 = px.bar(region_counts, x='지역', y='건수', text='건수')
        fig1.update_layout(
            xaxis_title=None,
            yaxis_title="건수",
            xaxis_tickangle=0,
            xaxis_tickfont_size=13,
            yaxis_tickfont_size=12,
            margin=dict(b=60),
            height=400
        )
        fig1.update_traces(textposition="outside")
        st.plotly_chart(fig1, use_container_width=True)
        
        st.subheader("📷 카메라종류별 현황")
        camera_counts = df['camera_type'].value_counts().reset_index()
        camera_counts.columns = ['카메라종류', '건수']
        fig2 = px.bar(camera_counts, x='카메라종류', y='건수', text='건수')
        fig2.update_layout(
            xaxis_title=None,
            yaxis_title="건수",
            xaxis_tickangle=0,
            xaxis_tickfont_size=13,
            yaxis_tickfont_size=12,
            margin=dict(b=60),
            height=400
        )
        fig2.update_traces(textposition="outside")
        st.plotly_chart(fig2, use_container_width=True)
