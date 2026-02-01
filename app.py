import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
import google.generativeai as genai
import json
import re
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

# ========== Gemini 초기화 ==========
@st.cache_resource
def init_gemini():
    api_key = st.secrets["gemini"]["api_key"]
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")

gemini_model = init_gemini()

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
    .home-card {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 50px 20px;
        border: 2px solid #e0e0e0;
        border-radius: 18px;
        background: #ffffff;
        text-align: center;
        transition: all 0.2s;
    }
    .home-card:hover {
        border-color: #1f77b4;
        background: #f0f7ff;
        box-shadow: 0 4px 16px rgba(31,119,180,0.18);
    }
    .home-card .icon { font-size: 3.2em; margin-bottom: 12px; }
    .home-card .label { font-size: 1.25em; font-weight: bold; color: #222; }
    .home-card .desc { font-size: 0.84em; color: #888; margin-top: 6px; }
    .ai-result-box {
        background: #f0faf5;
        border: 1px solid #b2dfcc;
        border-radius: 12px;
        padding: 22px 24px;
        margin-top: 18px;
    }
    .ai-result-box h4 { color: #2e7d5e; margin-top: 0; font-size: 1.1em; }
    .db-row {
        background: #fffde7;
        border: 1px solid #fff176;
        border-radius: 8px;
        padding: 18px 22px;
        margin-top: 10px;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.93em;
        line-height: 2;
    }
    .db-row .field { color: #e65100; font-weight: bold; }
    .db-row .value { color: #333; }
</style>
""", unsafe_allow_html=True)

# ========== 로그인 정보 (secrets 관리) ==========
USERS = {
    st.secrets["auth"]["admin_id"]: st.secrets["auth"]["admin_pw"]
}

# ========== 세션 초기화 ==========
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "page" not in st.session_state:
    st.session_state["page"] = "login"   # login / home / journal / viewer

# ========== 필터 옵션 로드 ==========
@st.cache_data(ttl=300)
def load_options():
    all_data = supabase.table("repairs").select("*").execute().data
    regions   = sorted(set([d['region']        for d in all_data if d.get('region')]))
    sites     = sorted(set([d['site_name']     for d in all_data if d.get('site_name')]))
    cameras   = sorted(set([d['camera_type']   for d in all_data if d.get('camera_type')]))
    inspectors= sorted(set([d['inspector']     for d in all_data if d.get('inspector')]))
    years     = sorted(set([d['repair_year']   for d in all_data if d.get('repair_year')]), reverse=True)
    return regions, sites, cameras, inspectors, years

# ========== Gemini AI 분석 ==========
def analyze_with_gemini(user_input: str, inspector_name: str) -> dict:
    now = datetime.now()
    prompt = f"""당신은 CCTV 수리 일지를 분석하는 전문가입니다.
아래 사용자 입력을 읽고, 다음 JSON 형식으로 정확히 변환하세요.

규칙:
- region: 지역명 (예: 전주, 대전 등)
- site_name: 현장명
- repair_year: 오늘 날짜의 연도 = {now.year} (사용자가 다른 연도를 명시했으면 그 연도)
- repair_month: 오늘 날짜의 월 = {now.month} (사용자가 다른 월을 명시했으면 그 월)
- repair_detail: 수리 내용을 간결하고 명확하게 정리
- camera_type: 카메라 종류가 언급되었으면 그것, 아니면 빈 문자열 ""
- inspector: "{inspector_name}"로 고정

반드시 유효한 JSON만 출력하세요. 다른 텍스트는 포함하지 마세요.

사용자 입력:
"{user_input}"

출력 형식:
{{
  "region": "",
  "site_name": "",
  "repair_year": 0,
  "repair_month": 0,
  "repair_detail": "",
  "camera_type": "",
  "inspector": ""
}}"""

    response = gemini_model.generate_content(prompt)
    raw = response.text.strip()
    raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    return json.loads(raw)

# ========================================================================
# 페이지 함수들
# ========================================================================

# ─── 로그인 ───
def page_login():
    col = st.columns(3)
    with col[1]:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 📹 CCTV 수리내역 관리 시스템", unsafe_allow_html=True)
        st.markdown("---")
        login_id = st.text_input("ID", placeholder="관리자 ID", key="login_id")
        login_pw = st.text_input("PW", type="password", placeholder="비밀번호", key="login_pw")
        login_btn = st.button("로그인", type="primary", use_container_width=True, key="login_btn")

        if login_btn:
            if login_id in USERS and USERS[login_id] == login_pw:
                st.session_state["logged_in"] = True
                st.session_state["username"]  = login_id
                st.session_state["page"]      = "home"
                st.rerun()
            else:
                st.error("ID 또는 비밀번호가 올바르지 않습니다.")

# ─── 홈 ───
def page_home():
    st.markdown(f"<br>👋 **{st.session_state['username']}** 님, 안녕하세요!", unsafe_allow_html=True)
    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="home-card">
            <div class="icon">📝</div>
            <div class="label">일지 기록</div>
            <div class="desc">AI가 자동으로 분석·정리</div>
        </div>""", unsafe_allow_html=True)
        if st.button("📝 일지 기록", use_container_width=True, key="home_journal"):
            st.session_state["page"] = "journal"
            st.rerun()

    with col2:
        st.markdown("""
        <div class="home-card">
            <div class="icon">🔍</div>
            <div class="label">뷰어 모드</div>
            <div class="desc">수리내역 검색·조회</div>
        </div>""", unsafe_allow_html=True)
        if st.button("🔍 뷰어 모드", use_container_width=True, key="home_viewer"):
            st.session_state["page"] = "viewer"
            st.rerun()

# ─── 일지 기록 ───
def page_journal():
    # 세션 키 초기화
    for k in ("ai_result", "ai_summary", "ai_saved"):
        if k not in st.session_state:
            st.session_state[k] = None if k != "ai_saved" else False

    # 헤더 + 뒤로 버튼
    hcol1, hcol2 = st.columns([1, 5])
    with hcol1:
        if st.button("← 뒤로", key="journal_back"):
            for k in ("ai_result", "ai_summary", "ai_saved"):
                st.session_state[k] = None if k != "ai_saved" else False
            st.session_state["page"] = "home"
            st.rerun()
    with hcol2:
        st.header("📝 일지 기록")

    # ── 입력 단계 ──
    if st.session_state["ai_result"] is None:
        st.markdown("수리 내용을 자유형식으로 기술하세요. AI가 자동으로 분석·정리하겠습니다.")
        user_input = st.text_area(
            "일지 내용",
            placeholder="예) 전주 테스트배드에서 차번 점검 조명교체",
            height=160,
            key="journal_input"
        )
        send_btn = st.button("🤖 AI 기록 전송", type="primary", key="journal_send")

        if send_btn:
            if not user_input.strip():
                st.error("일지 내용을 입력해주세요.")
            else:
                with st.spinner("AI 분석 중..."):
                    try:
                        result = analyze_with_gemini(user_input.strip(), st.session_state["username"])
                        st.session_state["ai_result"]  = result
                        st.session_state["ai_summary"] = user_input.strip()
                        st.session_state["ai_saved"]   = False
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI 분석 실패: {e}")

    # ── 결과 단계 ──
    else:
        result = st.session_state["ai_result"]
        now    = datetime.now()

        # 분석완료 박스
        st.markdown('<div class="ai-result-box"><h4>✅ 분석완료</h4>', unsafe_allow_html=True)

        fields = [
            ("region (varchar)",        result.get("region", "")),
            ("site_name (varchar)",     result.get("site_name", "")),
            ("repair_year (int4)",      f"{result.get('repair_year', now.year)}년"),
            ("repair_month (int4)",     f"{result.get('repair_month', now.month)}월"),
            ("repair_detail (text)",    result.get("repair_detail", "")),
            ("camera_type (varchar)",   result.get("camera_type", "") or "공백"),
            ("inspector (varchar)",     result.get("inspector", st.session_state["username"])),
            ("created_at (timestamp)",  now.strftime("%Y-%m-%d %H:%M:%S")),
        ]

        db_html = '<div class="db-row">{\n'
        for i, (field, value) in enumerate(fields):
            comma = "," if i < len(fields) - 1 else ""
            db_html += f'&nbsp;&nbsp;<span class="field">{field}</span> : <span class="value">{value}{comma}</span><br>'
        db_html += '}</div>'
        st.markdown(db_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 저장 / 뒤로 버튼
        bcol1, bcol2 = st.columns([2, 1])
        with bcol1:
            if st.session_state["ai_saved"]:
                st.success("✅ Supabase에 저장 완료!")
            else:
                if st.button("💾 저장", type="primary", use_container_width=True, key="journal_save"):
                    try:
                        supabase.table("repairs").insert({
                            "region":       result.get("region", ""),
                            "site_name":    result.get("site_name", ""),
                            "repair_year":  result.get("repair_year", now.year),
                            "repair_month": result.get("repair_month", now.month),
                            "repair_detail":result.get("repair_detail", ""),
                            "camera_type":  result.get("camera_type", ""),
                            "inspector":    result.get("inspector", st.session_state["username"]),
                        }).execute()
                        st.session_state["ai_saved"] = True
                        load_options.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"저장 실패: {e}")
        with bcol2:
            if st.button("← 뒤로", use_container_width=True, key="journal_back2"):
                for k in ("ai_result", "ai_summary", "ai_saved"):
                    st.session_state[k] = None if k != "ai_saved" else False
                st.session_state["page"] = "home"
                st.rerun()

# ─── 뷰어 모드 ───
def page_viewer():
    hcol1, hcol2 = st.columns([1, 5])
    with hcol1:
        if st.button("← 뒤로", key="viewer_back"):
            st.session_state["page"] = "home"
            st.rerun()
    with hcol2:
        st.header("🔍 수리내역 관리")

    tab1, tab2, tab3, tab4 = st.tabs(["🔍 조회", "➕ 등록", "✏️ 수정/삭제", "📊 통계"])

    # ── 탭1: 조회 ──
    with tab1:
        regions, sites, cameras, inspectors, years = load_options()

        col1, col2, col3, col4 = st.columns(4)
        with col1: sel_region   = st.selectbox("📍 지역",       ["전체"] + regions,                          key="v_region")
        with col2: sel_site     = st.selectbox("🏢 현장명",     ["전체"] + sites,                            key="v_site")
        with col3: sel_year     = st.selectbox("📅 년도",       ["전체"] + [str(y) for y in years],          key="v_year")
        with col4: sel_month    = st.selectbox("📅 월",         ["전체"] + [f"{m}월" for m in range(1,13)],  key="v_month")

        col5, col6, col7, col8 = st.columns(4)
        with col5: sel_camera   = st.selectbox("📷 카메라종류", ["전체"] + cameras,    key="v_camera")
        with col6: sel_inspector= st.selectbox("👤 점검자",     ["전체"] + inspectors, key="v_inspector")
        with col7: use_or       = st.checkbox("OR 검색", value=False, key="v_or")
        with col8:
            st.write(""); st.write("")
            search_btn = st.button("🔍 검색", type="primary", use_container_width=True, key="v_search")

        if search_btn:
            query      = supabase.table("repairs").select("*", count="exact")
            conditions = []

            filters = [
                (sel_region,    "region",       lambda v: v),
                (sel_site,      "site_name",    lambda v: v),
                (sel_year,      "repair_year",  lambda v: int(v)),
                (sel_camera,    "camera_type",  lambda v: v),
                (sel_inspector, "inspector",    lambda v: v),
            ]
            for val, col_name, conv in filters:
                if val != "전체":
                    if not use_or:
                        query = query.eq(col_name, conv(val))
                    else:
                        conditions.append(f"{col_name}.eq.{val}")

            if sel_month != "전체":
                month_num = int(sel_month.replace("월", ""))
                if not use_or:
                    query = query.eq("repair_month", month_num)
                else:
                    conditions.append(f"repair_month.eq.{month_num}")

            if use_or and conditions:
                query = query.or_(",".join(conditions))

            result = query.order("created_at", desc=True).execute()
            st.markdown(f"<div class='result-count'>📊 검색 결과: {len(result.data):,}건</div>", unsafe_allow_html=True)

            if result.data:
                df = pd.DataFrame(result.data)
                st.session_state["search_df"] = df.copy()

                df_d = df[['region','site_name','repair_year','repair_month',
                           'repair_detail','camera_type','inspector','created_at']].copy()
                df_d.columns = ['지역','현장명','년도','월','고장수리내역','카메라종류','점검자','등록일시']
                st.dataframe(df_d, use_container_width=True, height=500)

                csv = df_d.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 CSV 다운로드", csv,
                    f"수리내역_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", "text/csv", key="v_csv_dl")

    # ── 탭2: 등록 ──
    with tab2:
        st.header("➕ 수리내역 등록")
        regions, sites, cameras, inspectors, _ = load_options()

        with st.form("repair_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                region_opt = st.selectbox("📍 지역",   ["직접입력"] + regions,   key="reg_region")
                new_region = st.text_input("새 지역 입력") if region_opt == "직접입력" else region_opt

                site_opt   = st.selectbox("🏢 현장명", ["직접입력"] + sites,     key="reg_site")
                new_site   = st.text_input("새 현장명 입력") if site_opt == "직접입력" else site_opt

                cy, cm = st.columns(2)
                with cy: new_year  = st.selectbox("년도", list(range(datetime.now().year, datetime.now().year-6, -1)))
                with cm: new_month = st.selectbox("월",   list(range(1, 13)))

            with col2:
                cam_opt   = st.selectbox("📷 카메라종류", ["직접입력"] + cameras,    key="reg_camera")
                new_camera= st.text_input("새 카메라종류") if cam_opt == "직접입력" else cam_opt

                insp_opt  = st.selectbox("👤 점검자",    ["직접입력"] + inspectors, key="reg_inspector")
                new_insp  = st.text_input("새 점검자")   if insp_opt == "직접입력" else insp_opt

            new_detail = st.text_area("🔧 고장수리내역", height=150)
            submitted  = st.form_submit_button("✅ 등록", type="primary", use_container_width=True)

            if submitted:
                if not new_site or not new_region:
                    st.error("지역과 현장명은 필수입니다!")
                else:
                    supabase.table("repairs").insert({
                        "region": new_region, "site_name": new_site,
                        "repair_year": new_year, "repair_month": new_month,
                        "repair_detail": new_detail, "camera_type": new_camera,
                        "inspector": new_insp
                    }).execute()
                    st.success("✅ 등록 완료!")
                    st.balloons()
                    load_options.clear()

    # ── 탭3: 수정/삭제 ──
    with tab3:
        st.header("✏️ 수리내역 수정 / 삭제")
        regions, sites, cameras, inspectors, years = load_options()

        if "search_df" in st.session_state and not st.session_state["search_df"].empty:
            edit_df = st.session_state["search_df"].copy()
            st.info("💡 조회탭의 검색 결과를 표시합니다.")
        else:
            edit_df = pd.DataFrame(supabase.table("repairs").select("*").order("created_at", desc=True).execute().data)

        st.subheader("🔎 검색")
        ec1, ec2, ec3, ec4 = st.columns(4)
        with ec1: e_region   = st.selectbox("지역",   ["전체"] + regions,    key="edit_region")
        with ec2: e_site     = st.selectbox("현장명", ["전체"] + sites,      key="edit_site")
        with ec3: e_insp     = st.selectbox("점검자", ["전체"] + inspectors, key="edit_inspector")
        with ec4:
            st.write("")
            e_search = st.button("🔎 검색", type="primary", use_container_width=True, key="edit_search_btn")

        if e_search:
            q = supabase.table("repairs").select("*")
            if e_region != "전체": q = q.eq("region", e_region)
            if e_site   != "전체": q = q.eq("site_name", e_site)
            if e_insp   != "전체": q = q.eq("inspector", e_insp)
            edit_df = pd.DataFrame(q.order("created_at", desc=True).execute().data)

        if not edit_df.empty:
            ev = edit_df[['region','site_name','repair_year','repair_month',
                          'camera_type','inspector','repair_detail']].copy()
            ev.columns = ['지역','현장명','년도','월','카메라종류','점검자','고장수리내역']
            ev.index   = ev.index + 1
            st.subheader("📋 수정할 행 선택")
            st.dataframe(ev, use_container_width=True, height=300)

            sel_idx      = st.number_input("수정/삭제할 행 번호", min_value=1, max_value=len(edit_df), step=1, key="edit_sel_idx")
            selected_row = edit_df.iloc[sel_idx - 1]
            row_id       = selected_row["id"]

            st.divider()
            st.subheader(f"✏️ 수정 폼 (행 {sel_idx})")

            with st.form("edit_form", clear_on_submit=False):
                el, er = st.columns(2)
                with el:
                    # 지역
                    rc = ["직접입력"] + regions
                    ri = rc.index(selected_row["region"]) if selected_row["region"] in rc else 0
                    ero = st.selectbox("📍 지역", rc, index=ri, key="ef_region")
                    edit_region = st.text_input("새 지역 입력", value="" if ri==0 else selected_row["region"], key="ef_region_txt") if ero=="직접입력" else ero

                    # 현장명
                    sc = ["직접입력"] + sites
                    si = sc.index(selected_row["site_name"]) if selected_row["site_name"] in sc else 0
                    eso = st.selectbox("🏢 현장명", sc, index=si, key="ef_site")
                    edit_site = st.text_input("새 현장명 입력", value="" if si==0 else selected_row["site_name"], key="ef_site_txt") if eso=="직접입력" else eso

                    # 년도/월
                    yl = list(range(datetime.now().year, datetime.now().year-6, -1))
                    yi = yl.index(selected_row["repair_year"]) if selected_row["repair_year"] in yl else 0
                    eyl, eml = st.columns(2)
                    with eyl: edit_year  = st.selectbox("년도", yl, index=yi, key="ef_year")
                    with eml:
                        ml = list(range(1,13))
                        mi = ml.index(selected_row["repair_month"]) if selected_row["repair_month"] in ml else 0
                        edit_month = st.selectbox("월", ml, index=mi, key="ef_month")

                with er:
                    # 카메라
                    cc = ["직접입력"] + cameras
                    ci = cc.index(selected_row["camera_type"]) if selected_row["camera_type"] in cc else 0
                    eco = st.selectbox("📷 카메라종류", cc, index=ci, key="ef_camera")
                    edit_camera = st.text_input("새 카메라종류", value="" if ci==0 else selected_row["camera_type"], key="ef_camera_txt") if eco=="직접입력" else eco

                    # 점검자
                    ic = ["직접입력"] + inspectors
                    ii = ic.index(selected_row["inspector"]) if selected_row["inspector"] in ic else 0
                    eio = st.selectbox("👤 점검자", ic, index=ii, key="ef_inspector")
                    edit_inspector = st.text_input("새 점검자", value="" if ii==0 else selected_row["inspector"], key="ef_inspector_txt") if eio=="직접입력" else eio

                edit_detail  = st.text_area("🔧 고장수리내역", value=selected_row.get("repair_detail",""), height=150, key="ef_detail")
                edit_submit  = st.form_submit_button("✅ 수정 저장", type="primary", use_container_width=True)

            if edit_submit:
                if not edit_region or not edit_site:
                    st.error("지역과 현장명은 필수입니다!")
                else:
                    supabase.table("repairs").update({
                        "region": edit_region, "site_name": edit_site,
                        "repair_year": edit_year, "repair_month": edit_month,
                        "repair_detail": edit_detail, "camera_type": edit_camera,
                        "inspector": edit_inspector
                    }).eq("id", row_id).execute()
                    st.success("✅ 수정 완료!")
                    load_options.clear()
                    if "search_df" in st.session_state: del st.session_state["search_df"]
                    st.rerun()

            # 삭제
            st.divider()
            st.subheader(f"🗑️ 삭제 (행 {sel_idx})")
            st.warning(f"삭제할 내용: **{selected_row['region']} | {selected_row['site_name']} | {selected_row['repair_year']}년 {selected_row['repair_month']}월 | {selected_row['inspector']}**")
            del_confirm = st.checkbox("위 내용을 삭제할 것을 확인합니다.", key="del_confirm")
            del_btn     = st.button("🗑️ 삭제", type="secondary", disabled=not del_confirm, key="del_btn")
            if del_btn:
                supabase.table("repairs").delete().eq("id", row_id).execute()
                st.success("✅ 삭제 완료!")
                load_options.clear()
                if "search_df" in st.session_state: del st.session_state["search_df"]
                st.rerun()
        else:
            st.info("검색 결과가 없습니다.")

    # ── 탭4: 통계 ──
    with tab4:
        st.header("📊 통계")
        all_data = supabase.table("repairs").select("*").execute()
        if all_data.data:
            df = pd.DataFrame(all_data.data)
            c1,c2,c3,c4 = st.columns(4)
            with c1: st.metric("총 수리건수", f"{len(df):,}건")
            with c2: st.metric("현장수",      f"{df['site_name'].nunique():,}개")
            with c3: st.metric("지역수",      f"{df['region'].nunique():,}개")
            with c4: st.metric("점검자수",    f"{df['inspector'].nunique():,}명")

            st.subheader("📍 지역별 현황")
            rc = df['region'].value_counts().reset_index();  rc.columns=['지역','건수']
            f1 = px.bar(rc, x='지역', y='건수', text='건수')
            f1.update_layout(xaxis_title=None, yaxis_title="건수", xaxis_tickangle=0,
                           xaxis_tickfont_size=13, yaxis_tickfont_size=12, margin=dict(b=60), height=400)
            f1.update_traces(textposition="outside")
            st.plotly_chart(f1, use_container_width=True)

            st.subheader("📷 카메라종류별 현황")
            cc = df['camera_type'].value_counts().reset_index();  cc.columns=['카메라종류','건수']
            f2 = px.bar(cc, x='카메라종류', y='건수', text='건수')
            f2.update_layout(xaxis_title=None, yaxis_title="건수", xaxis_tickangle=0,
                           xaxis_tickfont_size=13, yaxis_tickfont_size=12, margin=dict(b=60), height=400)
            f2.update_traces(textposition="outside")
            st.plotly_chart(f2, use_container_width=True)

# ========== 사이드바 (로그인 후) ==========
def show_sidebar():
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state['username']}**")
        st.divider()
        if st.session_state["page"] != "home":
            if st.button("🏠 홈", use_container_width=True, key="sidebar_home"):
                for k in ("ai_result","ai_summary","ai_saved"):
                    st.session_state[k] = None if k != "ai_saved" else False
                st.session_state["page"] = "home"
                st.rerun()
        if st.button("🚪 로그아웃", use_container_width=True, key="sidebar_logout"):
            for k in ("logged_in","username","page","ai_result","ai_summary","ai_saved","search_df"):
                st.session_state.pop(k, None)
            st.rerun()

# ========== 라우팅 ==========
if not st.session_state["logged_in"]:
    page_login()
else:
    show_sidebar()
    page = st.session_state["page"]
    if   page == "home":    page_home()
    elif page == "journal": page_journal()
    elif page == "viewer":  page_viewer()
