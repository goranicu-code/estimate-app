import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# -----------------------------------------------------
# 1. 메인 설정 (반드시 맨 처음에 와야 함)
# -----------------------------------------------------
st.set_page_config(page_title="베스트 화학 기계 공업 통합 ERP", layout="wide")

# -----------------------------------------------------
# 2. 기초 데이터 세팅 (가상의 DB 역할)
# -----------------------------------------------------
if 'materials' not in st.session_state:
    data = {
        '자재코드': ['MTR-001', 'MTR-002', 'SUS-P01'],
        '품명': ['10HP 방폭 모터', '5HP 기어드 모터', 'SUS304 파이프 50A'],
        '재고': [2, 0, 50],
        '단가': [450000, 280000, 12000],
        '거래처': ['국제감속기', '국제감속기', '경원파이프']
    }
    st.session_state['materials'] = pd.DataFrame(data)

if 'orders' not in st.session_state:
    st.session_state['orders'] = pd.DataFrame(columns=['날짜', '거래처', '품명', '수량', '상태'])

# -----------------------------------------------------
# 3. 화면 구성
# -----------------------------------------------------
st.title("🏭 베스트 화학 기계 공업 통합 관리 시스템")
st.markdown("---")

# 탭 생성
tab1, tab2, tab3 = st.tabs(["📑 견적 관리(영업)", "📦 자재 발주(구매)", "📊 재고 관리(창고)"])

# =====================================================
# [탭 1] 견적 자동화 연결
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
    REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qHE0vmiPrF4dC0THfirzIBg_mYshXcGp/edit?gid=1280366000#gid=1280366000"

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
# [탭 2] 자재 발주
# =====================================================
with tab2:
    st.header("자재 발주 시스템")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("⚠️ 재고 부족/발주 필요 목록")
        df_mat = st.session_state['materials']
        low_stock = df_mat[df_mat['재고'] <= 2]
        st.dataframe(low_stock, use_container_width=True)
    
    with col2:
        st.subheader("발주 입력")
        target_item = st.selectbox("발주할 자재 선택", df_mat['품명'])
        order_qty = st.number_input("발주 수량", min_value=1, value=5)
        
        if st.button("발주서 생성 및 기록"):
            selected_row = df_mat[df_mat['품명'] == target_item].iloc[0]
            
            new_order = {
                '날짜': datetime.now().strftime("%Y-%m-%d"),
                '거래처': selected_row['거래처'],
                '품명': target_item,
                '수량': order_qty,
                '상태': '발주완료'
            }
