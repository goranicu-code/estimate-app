import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import time

# -----------------------------------------------------
# 1. 메인 설정
# -----------------------------------------------------
st.set_page_config(page_title="베스트 화학 통합 관리 시스템", layout="wide")

# -----------------------------------------------------
# 2. 구글 시트 연결 및 기초 데이터 로드 함수
# -----------------------------------------------------
# 캐싱을 통해 매번 로딩하지 않고 속도를 높입니다.
@st.cache_resource
def init_connection():
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # 스트림릿 클라우드용 vs 로컬용 인증 처리
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    elif os.path.exists("service_account.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
    else:
        return None
        
    client = gspread.authorize(creds)
    return client

def get_data(client, sheet_url):
    try:
        sh = client.open_by_url(sheet_url)
        return sh
    except Exception as e:
        return None

# --- [중요] 사장님의 실제 구글 시트 주소 ---
REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1UQ6_OysueJ07m6Qc5ncfE1NxPCLjc255r6MeFdl0OHQ/edit?gid=1630059230#gid=1630059230"

client = init_connection()

if client is None:
    st.error("🚨 인증 키(service_account.json)가 없거나 Secrets 설정이 안 되어 있습니다.")
    st.stop()

sh = get_data(client, REAL_SHEET_URL)
if sh is None:
    st.error("🚨 구글 시트를 찾을 수 없습니다. URL을 확인해주세요.")
    st.stop()

# -----------------------------------------------------
# 3. 시트 초기화 (없으면 자동 생성)
# -----------------------------------------------------
def check_and_create_sheets(sh):
    # 1. 자재마스터 시트 확인
    try:
        ws_mat = sh.worksheet("자재마스터")
    except:
        ws_mat = sh.add_worksheet(title="자재마스터", rows=100, cols=10)
        # 헤더 생성 및 기초 데이터 예시 추가
        ws_mat.append_row(["자재코드", "품명", "규격", "단가", "거래처", "현재고", "안전재고"])
        ws_mat.append_row(["MTR-001", "10HP 방폭 모터", "10HP, 4P, 380V", 450000, "국제감속기", 2, 5])
        ws_mat.append_row(["SUS-001", "SUS304 파이프", "50A, Sch10", 12000, "경원파이프", 50, 100])
        st.toast("✅ '자재마스터' 시트가 새로 생성되었습니다.")

    # 2. 발주내역 시트 확인
    try:
        ws_ord = sh.worksheet("발주내역")
    except:
        ws_ord = sh.add_worksheet(title="발주내역", rows=100, cols=10)
        ws_ord.append_row(["발주ID", "날짜", "거래처", "품명", "수량", "상태", "비고"])
        st.toast("✅ '발주내역' 시트가 새로 생성되었습니다.")
    
    return ws_mat, ws_ord

# 시트 객체 가져오기
ws_mat, ws_ord = check_and_create_sheets(sh)

# -----------------------------------------------------
# 4. 화면 UI 구성
# -----------------------------------------------------
st.title("🏭 베스트 화학 기계 공업 통합 ERP")
st.markdown(f"연동된 시트: `{sh.title}`")
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["📑 견적 관리(영업)", "📦 자재 발주(구매)", "📊 자재/재고 관리(DB)"])

# =====================================================
# [탭 1] 견적 관리 (기존 기능)
# =====================================================
with tab1:
    # --- 인증 설정 ---
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    # 키 파일 확인 로직
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    elif os.path.exists("service_account.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
    else:
        st.error("🚨 인증 키를 찾을 수 없습니다! (Secrets 설정 또는 json 파일 확인)")
        st.stop()

    client = gspread.authorize(creds) 
    REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1UQ6_OysueJ07m6Qc5ncfE1NxPCLjc255r6MeFdl0OHQ/edit?gid=1630059230#gid=1630059230"

    # --- 데이터 매핑 ---
    CAPACITY_MAP = {
        "베스트밀": [5, 10, 30, 40, 50],
        "퍼펙트밀": [5, 10, 30, 40, 50],
        "탑밀": [20, 30, 40, 50],
        "바스켓밀": ["1~4L", "20~40L", "100L", "200L", "300L", "500L", "1000L", "3000L", "5000L"],
        "충진기": ["1구", "2구"]
    }
    MAIN_MOTOR_AUTO_MAP = {
        "베스트밀": {5: "10HP", 10: "15HP", 20: "20HP", 30: "30HP", 40: "40HP", 50: "50HP"},
        "퍼펙트밀": {5: "10HP", 10: "15HP", 20: "20HP", 30: "30HP", 40: "40HP", 50: "50HP"},
        "탑밀": {20: "30HP", 30: "40HP", 40: "50HP", 50: "60HP"},
        "바스켓밀": {"1~4L": "2HP", "20~40L": "5HP", "100L": "20HP", "200L": "30HP", "300L": "40HP", "500L": "50HP", "1000L": "60HP", "3000L": "125HP", "5000L": "200HP"}
    }
    SUB_MOTOR_AUTO_MAP = {
        "베스트밀": {5: "1HP", 10: "2HP", 20: "2HP", 30: "2HP", 40: "2HP", 50: "3HP"},
        "퍼펙트밀": {5: "1HP", 10: "2HP", 20: "2HP", 30: "2HP", 40: "2HP", 50: "3HP"},
        "탑밀": {20: "2HP", 30: "2HP", 40: "2HP", 50: "3HP"},
        "바스켓밀": {"1~4L": "없음", "20~40L": "없음", "100L": "5HP", "200L": "10HP", "300L": "10HP", "500L": "15HP", "1000L": "20HP", "3000L": "50HP", "5000L": "100HP"}
    }
    ALL_MOTORS = ["없음", "1HP", "2HP", "3HP", "5HP", "10HP", "15HP", "20HP", "30HP", "40HP", "50HP", "60HP", "75HP", "100HP", "125HP", "200HP"]

    # --- UI 구성 ---
    st.subheader("1. 견적 상세 조건")
    
    col_input1, col_input2 = st.columns(2)
    
    with col_input1:
        equip_type = st.selectbox("설비 종류", ["베스트밀", "퍼펙트밀", "탑밀", "바스켓밀", "믹서", "진공탈포기", "충진기"])

        capacity = None
        if equip_type in ["믹서", "진공탈포기"]:
            st.info("💡 믹서/탈포기는 메인 모터 기준")
        elif equip_type == "충진기":
            capacity = st.selectbox("충진구 수", CAPACITY_MAP["충진기"])
        else:
            capacity = st.selectbox("설비 용량", CAPACITY_MAP.get(equip_type, []))

    # 자동 선택 로직
    default_main_index = 0
    default_sub_index = 0
    if capacity and equip_type in MAIN_MOTOR_AUTO_MAP:
        rec_main = MAIN_MOTOR_AUTO_MAP[equip_type].get(capacity, "없음")
        if rec_main in ALL_MOTORS: default_main_index = ALL_MOTORS.index(rec_main)
        rec_sub = SUB_MOTOR_AUTO_MAP.get(equip_type, {}).get(capacity, "없음")
        if rec_sub in ALL_MOTORS: default_sub_index = ALL_MOTORS.index(rec_sub)

    with col_input2:
        if equip_type == "충진기":
            main_hp = "없음"
        elif equip_type in ["믹서", "진공탈포기"]:
            main_hp = st.selectbox("메인 모터", ALL_MOTORS[1:])
        else:
            main_hp = st.selectbox("메인 모터", ALL_MOTORS, index=default_main_index)

        if equip_type in ["믹서", "진공탈포기", "이송펌프", "충진기"]:
            sub_hp = "없음"
        else:
            sub_hp = st.selectbox("서브 모터", ALL_MOTORS, index=default_sub_index)

    st.divider()
    
    c_opt1, c_opt2, c_opt3 = st.columns(3)
    with c_opt1:
        explosion_type = st.radio("방폭 타입", ["비방폭", "EG3", "d2G4 (내압방폭)"])
    with c_opt2:
        material = st.radio("접액부 재질", ["일반 철 (SS400)", "스테인리스 (SUS304)"])
    with c_opt3:
        options = st.text_area("기타 옵션")
    
    calc_btn = st.button("📝 가견적 산출 (미리보기)", type="primary")

    # --- 메인 화면 로직 ---
    if 'quote_data' not in st.session_state:
        st.session_state['quote_data'] = None
    if 'quote_detail_df' not in st.session_state:
        st.session_state['quote_detail_df'] = None

    if calc_btn:
        now = datetime.now()
        quote_id = now.strftime("%y%m%d%H%M")
        
        st.session_state['quote_data'] = {
            "견적ID": quote_id,
            "날짜": now.strftime("%Y-%m-%d"),
            "설비": equip_type,
            "용량": str(capacity) if capacity else "-",
            "메인": main_hp,
            "서브": sub_hp,
            "방폭": explosion_type,
            "재질": material,
            "옵션": options
        }
        
        initial_bom = [
            {"항목": "Main Motor", "규격": main_hp, "단가": 0, "수량": 1, "비고": "자동선택"},
            {"항목": "Sub Motor", "규격": sub_hp, "단가": 0, "수량": 1, "비고": "자동선택"},
            {"항목": "Body Vessel", "규격": f"{capacity} ({material})", "단가": 0, "수량": 1, "비고": "제관"},
            {"항목": "Control Panel", "규격": explosion_type, "단가": 0, "수량": 1, "비고": "전장"},
        ]
        st.session_state['quote_detail_df'] = pd.DataFrame(initial_bom)

    if st.session_state['quote_data'] is not None:
        st.subheader(f"📋 견적서 작성 및 검토 (ID: {st.session_state['quote_data']['견적ID']})")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.info("요약 정보")
            st.json(st.session_state['quote_data'])
        
        with col2:
            st.write("👇 **단가 및 수량 수정**")
            edited_df = st.data_editor(
                st.session_state['quote_detail_df'],
                num_rows="dynamic",
                use_container_width=True
            )
            total_estimate = (edited_df['단가'] * edited_df['수량']).sum()
            st.metric("총 예상 견적가", f"{total_estimate:,} 원")

        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 견적 DB에 최종 저장"):
                try:
                    sheet = client.open_by_url(REAL_SHEET_URL)
                    try:
                        ws_db = sheet.worksheet("견적DB")
                    except:
                        ws_db = sheet.add_worksheet(title="견적DB", rows=100, cols=20)
                        ws_db.append_row(["견적ID", "날짜", "설비", "용량", "메인", "서브", "방폭", "재질", "옵션", "총액", "링크"])
                    
                    q = st.session_state['quote_data']
                    quote_link = f"https://share.streamlit.io/...?quote_id={q['견적ID']}"

                    row_data = [
                        q['견적ID'], q['날짜'], q['설비'], q['용량'], q['메인'], q['서브'], 
                        q['방폭'], q['재질'], q['옵션'], int(total_estimate), 
                        quote_link
                    ]
                    ws_db.append_row(row_data)
                    st.success("✅ 구글 시트(견적DB)에 성공적으로 저장되었습니다!")
                    st.balloons()
                except Exception as e:
                    st.error(f"저장 실패: {e}")
        with c2:
            st.link_button("↗️ 견적 DB 페이지(구글시트)로 이동", REAL_SHEET_URL)
    else:
        st.info("👈 상단 조건 선택 후 [가견적 산출] 버튼을 눌러주세요.")

# =====================================================
# [탭 2] 자재 발주 시스템 (핵심 기능)
# =====================================================
with tab2:
    st.header("📦 자재 발주 및 입고 관리")

    # 1. 최신 자재 데이터 불러오기
    data_mat = ws_mat.get_all_records()
    df_mat = pd.DataFrame(data_mat)

    # 데이터가 비어있을 경우 예외처리
    if df_mat.empty:
        st.warning("자재마스터에 데이터가 없습니다. [자재/재고 관리] 탭에서 자재를 등록해주세요.")
    else:
        # 숫자형 변환 (에러 방지)
        df_mat['현재고'] = pd.to_numeric(df_mat['현재고'], errors='coerce').fillna(0)
        df_mat['안전재고'] = pd.to_numeric(df_mat['안전재고'], errors='coerce').fillna(0)

        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("⚠️ 발주 필요 품목 (재고 부족)")
            # 안전재고보다 현재고가 적은 것 필터링
            shortage_df = df_mat[df_mat['현재고'] <= df_mat['안전재고']]
            
            if not shortage_df.empty:
                st.dataframe(
                    shortage_df[['품명', '규격', '거래처', '현재고', '안전재고']], 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.success("현재 부족한 자재가 없습니다. 👍")

        with col2:
            st.subheader("📝 발주서 작성")
            
            # 자재 선택 박스
            item_list = df_mat['품명'].tolist()
            selected_item_name = st.selectbox("발주할 자재", item_list)
            
            # 선택한 자재의 상세 정보 가져오기
            selected_row = df_mat[df_mat['품명'] == selected_item_name].iloc[0]
            st.caption(f"거래처: {selected_row['거래처']} | 단가: {selected_row['단가']:,}원")
            
            qty = st.number_input("발주 수량", min_value=1, value=10)
            note = st.text_input("비고 (납기일 등)")

            if st.button("🚀 발주 확정 및 전송", type="primary"):
                now_str = datetime.now().strftime("%Y-%m-%d")
                order_id = datetime.now().strftime("%y%m%d%H%M")
                
                # 시트에 추가할 데이터
                new_order = [
                    order_id, now_str, selected_row['거래처'], 
                    selected_item_name, qty, "발주완료", note
                ]
                
                with st.spinner("발주 데이터를 저장 중입니다..."):
                    ws_ord.append_row(new_order)
                    time.sleep(1) # 시트 반영 대기
                    
                st.success(f"✅ {selected_item_name} {qty}개 발주가 완료되었습니다!")
                st.rerun() # 화면 새로고침하여 내역 업데이트

    st.divider()
    st.subheader("📋 최근 발주 내역")
    
    # 발주 내역 불러오기
    data_ord = ws_ord.get_all_records()
    if data_ord:
        df_ord = pd.DataFrame(data_ord)
        # 최신순 정렬 (데이터가 있을 때만)
        if not df_ord.empty:
            df_ord = df_ord.sort_values(by='발주ID', ascending=False)
        st.dataframe(df_ord, use_container_width=True, hide_index=True)
    else:
        st.info("아직 발주 내역이 없습니다.")

# =====================================================
# [탭 3] 자재 마스터 관리 (DB 수정)
# =====================================================
with tab3:
    st.header("📊 자재 마스터 관리")
    st.markdown("여기서 자재를 추가하거나 재고 수량을 직접 수정할 수 있습니다.")
    
    # 다시 로드 (탭 이동 시 최신 데이터 반영)
    data_mat_current = ws_mat.get_all_records()
    df_current = pd.DataFrame(data_mat_current)
    
    # 데이터 에디터 (엑셀처럼 수정 가능)
    edited_df = st.data_editor(
        df_current,
        num_rows="dynamic", # 행 추가 허용
        use_container_width=True,
        key="editor_material"
    )
    
    if st.button("💾 변경사항 구글 시트에 저장"):
        with st.spinner("구글 시트에 저장 중..."):
            # 1. 시트 데이터 클리어
            ws_mat.clear()
            # 2. 헤더 다시 쓰기
            ws_mat.append_row(edited_df.columns.tolist())
            # 3. 데이터 쓰기
            ws_mat.append_rows(edited_df.values.tolist())
        
        st.success("✅ 저장되었습니다!")




