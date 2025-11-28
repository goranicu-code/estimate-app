import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# -----------------------------------------------------------
# 1. 기초 설정
# -----------------------------------------------------------
st.set_page_config(page_title="베스트 화학 기계 견적 시스템", layout="wide")

# --- 인증 설정 (PC와 클라우드 모두 작동하게 수정됨) ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# 1. 클라우드(Streamlit Secrets)에 키가 있는지 먼저 확인
if "gcp_service_account" in st.secrets:
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)

# 2. 없으면 내 PC의 파일(service_account.json)을 찾음
elif os.path.exists("service_account.json"):
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)

# 3. 둘 다 없으면 에러
else:
    st.error("🚨 인증 키를 찾을 수 없습니다! (Secrets 설정 또는 json 파일 확인)")
    st.stop()

# 인증 및 연결
client = gspread.authorize(creds) 

# 사장님의 구글 스프레드시트 주소 (여기에 실제 주소를 넣으세요!)
# 주의: 이 시트에 아까 그 '로봇 이메일'이 편집자로 초대되어 있어야 합니다.
REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qHE0vmiPrF4dC0THfirzIBg_mYshXcGp/edit?gid=1280366000#gid=1280366000"

# --- 데이터 매핑 (기존 로직 유지) ---
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

# -----------------------------------------------------------
# 2. UI 구성 (사이드바)
# -----------------------------------------------------------
st.title("🏭 베스트 화학 기계 - 견적 관리 시스템")

with st.sidebar:
    st.header("1. 견적 상세 조건")
    
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
    explosion_type = st.radio("방폭 타입", ["비방폭", "EG3", "d2G4 (내압방폭)"])
    material = st.radio("접액부 재질", ["일반 철 (SS400)", "스테인리스 (SUS304)"])
    options = st.text_area("기타 옵션")
    
    # [가견적 산출] 버튼
    st.divider()
    calc_btn = st.button("📝 가견적 산출 (미리보기)", type="primary")

# -----------------------------------------------------------
# 3. 메인 화면 (견적 수정 및 저장)
# -----------------------------------------------------------

# 세션 상태에 견적 데이터 저장 (새로고침 되어도 유지되게)
if 'quote_data' not in st.session_state:
    st.session_state['quote_data'] = None
if 'quote_detail_df' not in st.session_state:
    st.session_state['quote_detail_df'] = None

# (1) 가견적 산출 버튼을 눌렀을 때
if calc_btn:
    # A. 기본 정보 저장
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
    
    # B. 상세 내역(BOM) 가견적 생성
    initial_bom = [
        {"항목": "Main Motor", "규격": main_hp, "단가": 0, "수량": 1, "비고": "자동선택"},
        {"항목": "Sub Motor", "규격": sub_hp, "단가": 0, "수량": 1, "비고": "자동선택"},
        {"항목": "Body Vessel", "규격": f"{capacity} ({material})", "단가": 0, "수량": 1, "비고": "제관"},
        {"항목": "Control Panel", "규격": explosion_type, "단가": 0, "수량": 1, "비고": "전장"},
    ]
    st.session_state['quote_detail_df'] = pd.DataFrame(initial_bom)

# (2) 화면 표시 및 수정 (Data Editor)
if st.session_state['quote_data'] is not None:
    st.subheader(f"📋 견적서 작성 및 검토 (ID: {st.session_state['quote_data']['견적ID']})")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.info("좌측 조건에 따른 요약 정보입니다.")
        st.json(st.session_state['quote_data'])
    
    with col2:
        st.write("👇 **아래 표를 엑셀처럼 직접 수정할 수 있습니다.** (단가, 수량 변경 가능)")
        # 여기가 핵심: st.data_editor로 수정 가능하게 만듦
        edited_df = st.data_editor(
            st.session_state['quote_detail_df'],
            num_rows="dynamic", # 행 추가/삭제 가능
            use_container_width=True
        )
        
        # 합계 계산
        total_estimate = (edited_df['단가'] * edited_df['수량']).sum()
        st.metric("총 예상 견적가", f"{total_estimate:,} 원")

    st.divider()

    # (3) 저장 및 이동 버튼
    c1, c2 = st.columns(2)
    
    with c1:
        # DB 저장 버튼
        if st.button("💾 견적 DB에 최종 저장"):
            try:
                # 위에서 이미 로그인한 'client'를 바로 씁니다.
                sheet = client.open_by_url(REAL_SHEET_URL)
                
                # 1. '견적DB' 시트에 요약 정보 저장
                try:
                    ws_db = sheet.worksheet("견적DB")
                except:
                    # 시트 없으면 생성
                    ws_db = sheet.add_worksheet(title="견적DB", rows=100, cols=20)
                    ws_db.append_row(["견적ID", "날짜", "설비", "용량", "메인", "서브", "방폭", "재질", "옵션", "총액", "링크"])
                
                # 데이터 준비
                q = st.session_state['quote_data']
                # 링크 생성
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
        # 시트로 바로 이동하는 버튼
        st.link_button("↗️ 견적 DB 페이지(구글시트)로 이동", REAL_SHEET_URL)

else:
    st.info("👈 왼쪽에서 조건을 선택하고 [가견적 산출] 버튼을 눌러주세요.")
