import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import time
import urllib.request
import re
from fpdf import FPDF

# -----------------------------------------------------
# 1. 시스템 설정 및 폰트
# -----------------------------------------------------
st.set_page_config(page_title="베스트 화학 통합 ERP", layout="wide")

FONT_FILE = "NanumGothic.ttf"

def ensure_font_exists():
    if not os.path.exists(FONT_FILE):
        url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
        try:
            with st.spinner("한글 폰트 다운로드 중..."):
                urllib.request.urlretrieve(url, FONT_FILE)
        except: return False
    return True

# -----------------------------------------------------
# 2. PDF 생성 클래스
# -----------------------------------------------------
class PDF(FPDF):
    def header(self):
        if os.path.exists(FONT_FILE):
            self.add_font("NanumGothic", "", FONT_FILE, uni=True)
            self.set_font("NanumGothic", "", 10)
        else: self.set_font("Arial", "", 10)
        
        self.set_font_size(24)
        try: self.cell(0, 15, "발    주    서", align="C", ln=True)
        except: self.cell(0, 15, "ORDER SHEET", align="C", ln=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        if os.path.exists(FONT_FILE): self.set_font("NanumGothic", "", 8)
        else: self.set_font("Arial", "", 8)
        self.cell(0, 10, f'Page {self.page_no()}', align="C")

def generate_order_pdf(supplier_info, order_items):
    if not ensure_font_exists(): return None
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("NanumGothic", "", 11)

    # 상단 정보
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(30, 10, "  발  신  인", border=1, fill=True)
    pdf.cell(160, 10, "  베스트화학기계공업(주)   (담당: 김송이 과장)", border=1, ln=True)
    pdf.cell(30, 10, "  수  신  인", border=1, fill=True)
    pdf.cell(60, 10, f"  {supplier_info['name']}", border=1)
    pdf.cell(30, 10, "  F    A    X", border=1, fill=True)
    pdf.cell(70, 10, f"  {supplier_info.get('fax', '')}", border=1, ln=True)
    pdf.cell(30, 10, "  발  주  일", border=1, fill=True)
    pdf.cell(160, 10, f"  {datetime.now().strftime('%Y년 %m월 %d일')}", border=1, ln=True)
    pdf.ln(8)
    
    pdf.multi_cell(0, 6, "※ 베스트입니다. 다음과 같이 발주하고자 합니다.\n   오늘도 행복한 하루 보내세요. 감사합니다. ^^")
    pdf.ln(5)

    # 자재 목록
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(15, 8, "No", border=1, align="C", fill=True)
    pdf.cell(70, 8, "품  명", border=1, align="C", fill=True)
    pdf.cell(50, 8, "규  격", border=1, align="C", fill=True)
    pdf.cell(20, 8, "수 량", border=1, align="C", fill=True)
    pdf.cell(35, 8, "비 고", border=1, align="C", fill=True, ln=True)
    
    total_qty = 0
    for idx, item in enumerate(order_items):
        qty = int(item['qty'])
        total_qty += qty
        pdf.cell(15, 8, str(idx+1), border=1, align="C")
        pdf.cell(70, 8, str(item['name']), border=1, align="L")
        pdf.cell(50, 8, str(item['spec']), border=1, align="C")
        pdf.cell(20, 8, str(qty), border=1, align="C")
        pdf.cell(35, 8, str(item.get('note', '')), border=1, align="L", ln=True)

    pdf.cell(135, 8, "합    계", border=1, align="C")
    pdf.cell(20, 8, str(total_qty), border=1, align="C")
    pdf.cell(35, 8, "", border=1, ln=True)
    pdf.ln(15)
    
    pdf.set_font_size(16)
    pdf.cell(0, 10, "베스트화학기계공업(주)   (인)", align="R", ln=True)
    
    file_name = f"발주서_{supplier_info['name']}_{datetime.now().strftime('%y%m%d')}.pdf"
    pdf.output(file_name)
    return file_name

# -----------------------------------------------------
# 3. 구글 시트 연결
# -----------------------------------------------------
@st.cache_resource
def init_connection():
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = None
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
    elif "private_key" in st.secrets:
        creds_dict = st.secrets
    elif os.path.exists("service_account.json"):
        import json
        creds_dict = json.load(open("service_account.json"))

    if creds_dict:
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
            return gspread.authorize(creds)
        except: return None
    return None

REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1UQ6_OysueJ07m6Qc5ncfE1NxPCLjc255r6MeFdl0OHQ/edit?gid=1122897158#gid=1122897158"

client = init_connection()
if not client:
    st.error("인증 실패")
    st.stop()
    
try:
    sh = client.open_by_url(REAL_SHEET_URL)
    ws_mat = sh.worksheet("자재마스터")
    ws_ord = sh.worksheet("발주내역")
    try: ws_quote = sh.worksheet("견적DB")
    except: 
        ws_quote = sh.add_worksheet(title="견적DB", rows=100, cols=20)
        ws_quote.append_row(["견적ID", "날짜", "설비", "용량", "메인", "서브", "방폭", "재질", "옵션", "총액"])
except:
    st.error("구글 시트 연결 실패")
    st.stop()

# -----------------------------------------------------
# 4. 유틸리티 함수
# -----------------------------------------------------
PREFIX_MAP = {
    '모터': 'MTR', '감속기': 'MTR', '펌프': 'PMP', '베어링': 'BRG', '유니트': 'BRG',
    '밸브': 'VLV', '파이프': 'PIP', '엘보': 'PIP', '티': 'PIP', '소켓': 'PIP',
    '플랜지': 'FLG', '볼트': 'BLT', '너트': 'BLT', '인버터': 'ELC', '스위치': 'ELC',
    '판': 'RAW', '앵글': 'RAW', '환봉': 'RAW', 'SUS': 'RAW', '씰': 'SEL'
}

def generate_smart_code(supplier, name, spec):
    sup_code = supplier[:2] if supplier else "XX"
    item_code = "ETC"
    for k, v in PREFIX_MAP.items():
        if k in name:
            item_code = v
            break
    spec_clean = re.sub(r'[^a-zA-Z0-9가-힣]', '', str(spec))
    spec_code = spec_clean[:3].upper() if spec_clean else "000"
    return f"{sup_code}-{item_code}-{spec_code}"

# -----------------------------------------------------
# 5. 적용설비 매칭 로직 (NEW)
# -----------------------------------------------------
# -----------------------------------------------------
# 5. 적용설비 매칭 로직 (수정된 버전)
# -----------------------------------------------------
def check_applicability(tag_string, selection):
    """
    tag_string: 시트의 '적용설비' 값 (예: '탑밀30L-철@, 횡형밀@')
    selection: 사용자가 선택한 값 딕셔너리
    """
    if not tag_string or str(tag_string).strip() == "": return False
    
    # 태그를 쉼표로 분리 (공백 제거 포함)
    tags = [t.strip() for t in str(tag_string).split(',')]
    
    sel_equip = selection['equip']   # 예: 탑밀
    raw_capa = str(selection['capa']) # 예: 30 (숫자일 수 있음)
    
    # [핵심 수정 1] 숫자만 있는 용량(30) 뒤에 강제로 'L'을 붙여서 비교
    # 30 -> 30L, 1~4L -> 1~4L (그대로)
    if raw_capa.isdigit():
        sel_capa = raw_capa + "L"
    else:
        sel_capa = raw_capa

    sel_explo_raw = selection['explo'] # 예: 안전증방폭(eG3)
    sel_mat_raw = selection['mat']     # 예: SUS304 (스텐)
    
    # [핵심 수정 2] 매칭 키워드 확장 (유연성 확보)
    # 사용자가 '안전증방폭(eG3)'을 선택했다면 -> ['방폭', 'eG3', 'EG3', '안전증'] 키워드를 모두 가짐
    current_options = []
    
    # 1. 방폭 관련 키워드 생성
    if "비방폭" in sel_explo_raw:
        current_options.append("비방폭")
    else:
        current_options.append("방폭") # 기본적으로 방폭임
        if "eG3" in sel_explo_raw or "EG3" in sel_explo_raw:
            current_options.extend(["eG3", "EG3", "안전증"])
        if "d2G4" in sel_explo_raw:
            current_options.extend(["d2G4", "내압"])

    # 2. 재질 관련 키워드 생성
    if "SUS" in sel_mat_raw or "스텐" in sel_mat_raw:
        current_options.extend(["스텐", "SUS", "써스"])
    else:
        current_options.extend(["철", "SS400", "일반"])

    # --- 태그 검사 시작 ---
    for tag in tags:
        # 태그가 비어있으면 패스
        if not tag: continue

        # 1. '횡형밀' 특수 그룹 체크
        if "횡형밀" in tag:
            if sel_equip in ["베스트밀", "퍼펙트밀", "탑밀"]: 
                # 횡형밀이라도 뒤에 옵션(예: 횡형밀@-스텐@)이 붙을 수 있으므로 아래 로직을 태움
                pass 
            else:
                continue # 횡형밀이 아니면 다음 태그로

        # 태그 분해 (예: 탑밀30L-철@ -> ['탑밀30L', '철@'])
        tokens = [t.strip().replace("@", "") for t in tag.split('-')]
        head = tokens[0] # 설비명 부분
        
        # 2. 설비명 및 용량 일치 여부 확인
        is_equip_match = False
        
        # Case A: '횡형밀' 같은 그룹명인 경우 (이미 위에서 필터링 했으므로 통과)
        if "횡형밀" in head:
            is_equip_match = True
            
        # Case B: '탑밀' 처럼 용량 없이 설비명만 있는 경우 (@가 붙어있거나 텍스트만 일치)
        elif head == sel_equip:
            is_equip_match = True
            
        # Case C: '탑밀30L' 처럼 용량까지 지정된 경우
        # 아까 만든 sel_capa ("30L")와 결합해서 비교
        elif head == f"{sel_equip}{sel_capa}":
            is_equip_match = True
            
        # 설비 조건이 안 맞으면 이 태그는 탈락
        if not is_equip_match:
            continue

        # 3. 옵션(재질/방폭) 상세 일치 여부 확인
        # tokens[1:] 부터는 '철', '방폭', 'EG3' 같은 조건들임
        # 이 조건들이 위에서 만든 current_options 리스트에 다 들어있어야 함
        
        is_option_match = True
        if len(tokens) > 1:
            for req in tokens[1:]:
                # 태그에 적힌 조건(req)이 현재 내 상황(current_options)에 없으면 탈락
                # 대소문자 무시를 위해 upper() 사용 추천하지만, 일단 단순 비교
                match_found = False
                for my_opt in current_options:
                    if req.upper() == my_opt.upper():
                        match_found = True
                        break
                
                if not match_found:
                    is_option_match = False
                    break
        
        if is_option_match:
            return True # 하나라도 조건에 맞는 태그를 찾으면 즉시 성공!
            
    return False

# -----------------------------------------------------
# 6. 화면 UI 메인
# -----------------------------------------------------
st.title("🏭 베스트 화학 통합 ERP")
tab1, tab2, tab3 = st.tabs(["📑 견적 관리(영업)", "📦 자재 발주(구매)", "✅ 입고 확인(창고)"])

# [탭 1] 견적 시스템
# [탭 1] 견적 시스템
with tab1:
    st.header("📑 견적 관리 및 산출")
    st.subheader("1. 견적 상세 조건 입력")
    
    col_input1, col_input2 = st.columns(2)
    
    with col_input1:
        # 설비 종류 선택
        equip_type = st.selectbox("설비 종류", ["베스트밀", "퍼펙트밀", "탑밀", "바스켓밀", "믹서", "진공탈포기", "충진기"])
        
        # 용량 매핑 데이터
        CAPACITY_MAP = {
            "베스트밀": [5, 10, 30, 40, 50],
            "퍼펙트밀": [5, 10, 30, 40, 50],
            "탑밀": [20, 30, 40, 50],
            "바스켓밀": ["1~4L", "20~40L", "100L", "200L", "300L", "500L", "1000L", "3000L", "5000L"],
            "충진기": ["1구", "2구"]
        }
        
        capacity = None
        if equip_type in ["믹서", "진공탈포기"]:
            st.info("💡 믹서/탈포기는 메인 모터 기준")
        elif equip_type == "충진기":
            capacity = st.selectbox("충진구 수", CAPACITY_MAP["충진기"])
        else:
            capacity = st.selectbox("설비 용량", CAPACITY_MAP.get(equip_type, []))

    with col_input2:
        # 모터 마력 리스트
        ALL_MOTORS = ["없음", "1HP", "2HP", "3HP", "5HP", "10HP", "15HP", "20HP", "30HP", "40HP", "50HP", "60HP", "75HP", "100HP", "125HP", "200HP"]
        
        # 기본값 자동 선택 로직 (편의성)
        default_main_idx = 0
        if capacity == 30 and equip_type in ["베스트밀", "퍼펙트밀"]: default_main_idx = ALL_MOTORS.index("30HP")
        
        main_hp = st.selectbox("메인 모터", ALL_MOTORS, index=default_main_idx)
        sub_hp = st.selectbox("서브 모터", ALL_MOTORS)

    st.divider()
    
    # 옵션 선택
    c_opt1, c_opt2, c_opt3 = st.columns(3)
    with c_opt1:
        explosion_type = st.radio("방폭 타입", ["비방폭", "EG3", "d2G4 (내압방폭)"])
    with c_opt2:
        material_radio = st.radio("접액부 재질", ["일반 철 (SS400)", "스테인리스 (SUS304)"])
    with c_opt3:
        options = st.text_area("기타 옵션 (특이사항)")
    
    # ----------------------------------------------------------------
    # [가견적 산출 버튼 로직]
    # ----------------------------------------------------------------
    if st.button("📝 가견적 산출 (미리보기)", type="primary"):
        now = datetime.now()
        quote_id = now.strftime("%y%m%d%H%M") # 년월일시분
        
        # 1. 세션에 기본 정보 저장
        st.session_state['quote_data'] = {
            "견적ID": quote_id,
            "날짜": now.strftime("%Y-%m-%d"),
            "설비": equip_type,
            "용량": str(capacity) if capacity else "-",
            "메인": main_hp,
            "서브": sub_hp,
            "방폭": explosion_type,
            "재질": material_radio,
            "옵션": options
        }
        
        # 2. 기초 BOM(상세내역) 데이터프레임 생성
        # 실제 단가는 0으로 두고, 아래 에디터에서 사장님이 직접 입력하게 함
        initial_bom = [
            {"항목": "Main Motor", "규격": main_hp, "단가": 0, "수량": 1, "비고": "자동선택"},
            {"항목": "Sub Motor", "규격": sub_hp, "단가": 0, "수량": 1, "비고": "자동선택"},
            {"항목": "Body Vessel (가공/제관)", "규격": f"{capacity} ({material_radio})", "단가": 0, "수량": 1, "비고": "본체 및 프레임"},
            {"항목": "Control Panel (전장)", "규격": explosion_type, "단가": 0, "수량": 1, "비고": "인버터 포함"},
            {"항목": "기타 자재 (배관/볼트)", "규격": "-", "단가": 0, "수량": 1, "비고": "소모 자재 일체"},
            {"항목": "노무비 및 경비", "규격": "-", "단가": 0, "수량": 1, "비고": "조립/시운전"},
            {"항목": "이윤 및 기업관리비", "규격": "-", "단가": 0, "수량": 1, "비고": ""}
        ]
        st.session_state['quote_detail_df'] = pd.DataFrame(initial_bom)

    # ----------------------------------------------------------------
    # [결과 표시 및 수정 화면]
    # ----------------------------------------------------------------
    if 'quote_data' in st.session_state and st.session_state['quote_data']:
        st.divider()
        st.subheader(f"📋 견적서 작성 (ID: {st.session_state['quote_data']['견적ID']})")
        
        col_res1, col_res2 = st.columns([1, 2])
        
        # 왼쪽: 요약 정보 표시
        with col_res1:
            st.info("🔹 견적 요약")
            q = st.session_state['quote_data']
            st.write(f"**설비:** {q['설비']} {q['용량']}")
            st.write(f"**사양:** {q['방폭']} / {q['재질']}")
            st.write(f"**모터:** Main {q['메인']}, Sub {q['서브']}")
            st.text_area("옵션메모", q['옵션'], disabled=True)
        
        # 오른쪽: 상세 내역 에디터 (단가 입력용)
        with col_res2:
            st.write("👇 **아래 표에서 '단가'와 '수량'을 수정하세요.**")
            
            if 'quote_detail_df' in st.session_state:
                # 데이터 에디터 출력
                edited_df = st.data_editor(
                    st.session_state['quote_detail_df'],
                    num_rows="dynamic", # 행 추가/삭제 가능
                    column_config={
                        "단가": st.column_config.NumberColumn("단가 (원)", format="%d"),
                        "수량": st.column_config.NumberColumn("수량", format="%d"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # 총액 실시간 계산
                total_estimate = (edited_df['단가'] * edited_df['수량']).sum()
                st.metric("💰 총 견적 예상금액", f"{total_estimate:,.0f} 원")
                
                # [DB 저장 버튼]
                if st.button("💾 이대로 견적 DB에 저장", type="primary"):
                    # 1. 데이터 준비
                    q = st.session_state['quote_data']
                    row_data = [
                        q['견적ID'], 
                        q['날짜'], 
                        q['설비'], 
                        q['용량'], 
                        q['메인'], 
                        q['서브'], 
                        q['방폭'], 
                        q['재질'], 
                        q['옵션'], 
                        int(total_estimate) # 총액
                    ]
                    
                    # 2. 구글 시트(견적DB)에 추가
                    try:
                        ws_quote.append_row(row_data)
                        st.success("✅ 견적 내역이 성공적으로 저장되었습니다!")
                        st.balloons() # 축하 효과
                        
                        # (선택사항) 저장 후 초기화 하고 싶으면 아래 주석 해제
                        # del st.session_state['quote_data']
                        # del st.session_state['quote_detail_df']
                        # st.rerun()
                        
                    except Exception as e:
                        st.error(f"저장 중 오류 발생: {e}")
                        
# [탭 2] 자재 발주 (대폭 수정됨)
with tab2:
    st.header("📦 자재 발주 시스템")
    
    # DB 로딩
    data_mat = ws_mat.get_all_records()
    df_mat = pd.DataFrame(data_mat)
    
    # 발주 모드 선택
    order_mode = st.radio("발주 방식 선택", ["🔵 규격 설비 일괄 발주", "🟠 부품 및 비규격 개별 발주"], horizontal=True)
    st.divider()

    # 장바구니 초기화
    if 'cart' not in st.session_state: st.session_state['cart'] = []

    # -----------------------------------------------
    # MODE A: 규격 설비 일괄 발주
    # -----------------------------------------------
    if "규격 설비" in order_mode:
        st.info("💡 설비 사양을 선택하면 [적용설비]에 매칭된 자재를 자동으로 불러옵니다.")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sel_eq = st.selectbox("설비", ["베스트밀", "퍼펙트밀", "탑밀", "바스켓밀"], key="ord_eq")
        with c2:
            sel_cap = st.selectbox("용량", CAPACITY_MAP.get(sel_eq, []), key="ord_cap")
        with c3:
            sel_exp = st.selectbox("방폭여부", ["비방폭", "내압방폭(d2G4)", "안전증방폭(eG3)"], key="ord_exp")
        with c4:
            sel_mat = st.selectbox("재질", ["SS400 (철)", "SUS304 (스텐)"], key="ord_mat")
            
        if st.button("🔍 자재 리스트 불러오기", type="primary"):
            if "적용설비" not in df_mat.columns:
                st.error("자재마스터 시트에 '적용설비' 컬럼이 없습니다!")
            else:
                selection = {
                    "equip": sel_eq,
                    "capa": str(sel_cap),
                    "explo": sel_exp,
                    "mat": sel_mat
                }
                
                # 필터링 로직 적용
                df_mat['is_match'] = df_mat['적용설비'].apply(lambda x: check_applicability(x, selection))
                matched_df = df_mat[df_mat['is_match'] == True].copy()
                
                if matched_df.empty:
                    st.warning("조건에 맞는 자재가 없습니다. '적용설비' 컬럼을 확인해주세요.")
                else:
                    st.success(f"총 {len(matched_df)}개의 자재가 검색되었습니다.")
                    
                    # 데이터 에디터용 가공
                    matched_df['선택'] = True
                    matched_df['주문수량'] = 1
                    matched_df['비고'] = f"{sel_eq}{sel_cap}용"
                    
                    show_cols = ['선택', '매입처', '품명', '규격', '단가', '주문수량', '비고', '자재코드']
                    
                    st.session_state['editor_data'] = matched_df[show_cols]

        # 불러온 데이터 표시 및 장바구니 담기
        if 'editor_data' in st.session_state:
            edited_df = st.data_editor(
                st.session_state['editor_data'],
                column_config={
                    "선택": st.column_config.CheckboxColumn("발주", default=True),
                    "주문수량": st.column_config.NumberColumn("수량", min_value=1, step=1)
                },
                use_container_width=True,
                hide_index=True
            )
            
            if st.button("🛒 선택한 항목 장바구니에 담기"):
                selected_rows = edited_df[edited_df['선택'] == True]
                count = 0
                for _, row in selected_rows.iterrows():
                    st.session_state['cart'].append({
                        'code': row['자재코드'],
                        'name': row['품명'],
                        'spec': row['규격'],
                        'qty': row['주문수량'],
                        'supplier': row['매입처'],
                        'note': row['비고'],
                        'is_new': False
                    })
                    count += 1
                st.success(f"{count}개 품목을 장바구니에 담았습니다! 아래에서 발주서를 생성하세요.")
                del st.session_state['editor_data'] # 초기화
                st.rerun()

    # -----------------------------------------------
    # MODE B: 부품 및 비규격 개별 발주 (기존 로직)
    # -----------------------------------------------
    else:
        st.subheader("개별 부품 선택")
        col1, col2 = st.columns([1, 1])

        with col1:
            suppliers_raw = list(set([str(d.get('매입처', '')).strip() for d in data_mat if str(d.get('매입처', '')).strip()]))
            suppliers = sorted(suppliers_raw)
            suppliers.insert(0, "➕ 신규 거래처 입력")
            
            sel_supplier = st.selectbox("거래처", suppliers)
            final_supplier = st.text_input("거래처명 직접 입력") if sel_supplier == "➕ 신규 거래처 입력" else sel_supplier

            items_options = []
            if sel_supplier != "➕ 신규 거래처 입력":
                items_raw = list(set([str(d.get('품명', '')) for d in data_mat if str(d.get('매입처', '')).strip() == final_supplier]))
                items_options = sorted(items_raw)
            
            items_options.insert(0, "➕ 신규 품명 입력")
            sel_item = st.selectbox("품명", items_options)
            final_item = st.text_input("품명 직접 입력") if sel_item == "➕ 신규 품명 입력" else sel_item

            specs_options = []
            if sel_item != "➕ 신규 품명 입력":
                specs_raw = list(set([str(d.get('규격', '')) for d in data_mat if str(d.get('품명', '')) == final_item]))
                specs_options = sorted(specs_raw)
            
            specs_options.insert(0, "➕ 신규 규격 입력")
            sel_spec = st.selectbox("규격", specs_options)
            final_spec = st.text_input("규격 직접 입력") if sel_spec == "➕ 신규 규격 입력" else sel_spec
            
            # 단가 및 수량
            est_price = 0
            if sel_item != "➕ 신규 품명 입력" and sel_spec != "➕ 신규 규격 입력":
                try:
                    match = df_mat[
                        (df_mat['품명'].astype(str) == final_item) & 
                        (df_mat['규격'].astype(str) == final_spec)
                    ]
                    if not match.empty:
                        est_price = int(str(match.iloc[0]['단가']).replace(',',''))
                except: est_price = 0
            
            price = st.number_input("단가 (원)", value=est_price, step=100)
            qty = st.number_input("발주 수량", min_value=1, value=10)
            note = st.text_input("비고 (납기 등)")

            if st.button("장바구니 담기 ⬇️", type="primary"):
                if not final_supplier or not final_item:
                    st.error("거래처와 품명은 필수입니다.")
                else:
                    is_new = True
                    mat_code = ""
                    
                    try:
                        match = df_mat[
                            (df_mat['매입처'].astype(str) == final_supplier) & 
                            (df_mat['품명'].astype(str) == final_item) & 
                            (df_mat['규격'].astype(str) == final_spec)
                        ]
                    except: match = pd.DataFrame()

                    if not match.empty:
                        is_new = False
                        mat_code = match.iloc[0]['자재코드']
                    else:
                        is_new = True
                        base_code = generate_smart_code(final_supplier, final_item, final_spec)
                        mat_code = f"{base_code}-{datetime.now().strftime('%M%S')}" 
                        # 신규 등록은 일단 장바구니에서 처리하거나 여기서 바로 시트에 추가
                        new_mat_row = [mat_code, final_item, final_spec, "", price, final_supplier, 0, ""]
                        ws_mat.append_row(new_mat_row)
                        st.toast(f"✨ 자재마스터 등록 완료: {final_item}")
                    
                    st.session_state['cart'].append({
                        'code': mat_code, 'name': final_item, 'spec': final_spec,
                        'qty': qty, 'supplier': final_supplier, 'note': note, 'is_new': is_new
                    })
                    st.success("담기 완료")

    # -----------------------------------------------
    # 공통: 장바구니 및 발주 확정 영역
    # -----------------------------------------------
    st.divider()
    st.subheader("🛒 발주 대기 목록 (장바구니)")
    
    cart_df = pd.DataFrame(st.session_state['cart'])
    
    if not cart_df.empty:
        st.dataframe(cart_df[['supplier', 'name', 'spec', 'qty', 'note']], hide_index=True, use_container_width=True)
        
        unique_suppliers = cart_df['supplier'].unique()
        
        for sup in unique_suppliers:
            st.markdown(f"**🏢 {sup}**")
            current_cart = cart_df[cart_df['supplier'] == sup]
            
            col_act1, col_act2 = st.columns(2)
            with col_act1:
                if st.button(f"📄 PDF 생성 ({sup})"):
                    pdf_file = generate_order_pdf({'name': sup}, current_cart.to_dict('records'))
                    if pdf_file:
                        with open(pdf_file, "rb") as f:
                            st.download_button("📥 다운로드", f, file_name=pdf_file, mime="application/pdf")
            with col_act2:
                if st.button(f"📠 발주 확정 ({sup})", key=f"confirm_{sup}"):
                    with st.spinner("처리 중..."):
                        now_str = datetime.now().strftime("%Y-%m-%d")
                        order_id = datetime.now().strftime("%y%m%d%H%M")
                        
                        new_rows = []
                        for _, row in current_cart.iterrows():
                            new_rows.append([
                                order_id, now_str, row['supplier'], 
                                row['name'], row['qty'], "발주완료", row['note'], row['code']
                            ])
                        ws_ord.append_rows(new_rows)
                        
                        st.session_state['cart'] = [item for item in st.session_state['cart'] if item['supplier'] != sup]
                        st.success(f"{sup} 발주 완료!")
                        time.sleep(1)
                        st.rerun()
    
        if st.button("🗑️ 장바구니 비우기"):
            st.session_state['cart'] = []
            st.rerun()

# [탭 3] 입고 확인 (완전한 코드)
with tab3:
    st.header("✅ 자재 입고 처리 (재고 자동 반영)")
    
    # 1. 발주 내역 불러오기
    raw_data = ws_ord.get_all_values()
    
    if len(raw_data) < 2:
        st.info("📭 발주 내역이 없습니다.")
    else:
        # 헤더와 데이터 분리
        headers = ["발주ID", "날짜", "거래처", "품명", "수량", "상태", "비고", "자재코드"]
        
        # 데이터 정제 (열 개수가 안 맞을 경우 보정)
        clean_rows = []
        for row in raw_data[1:]:
            # 행 데이터가 헤더보다 짧으면 빈카드로 채움
            if len(row) < 8:
                row += [""] * (8 - len(row))
            clean_rows.append(row[:8])
            
        df_ord = pd.DataFrame(clean_rows, columns=headers)
        
        # '상태' 컬럼 공백 제거 (오류 방지)
        df_ord['상태'] = df_ord['상태'].astype(str).str.strip()
        
        # 2. '발주완료' 상태인 것만 필터링 (입고 대기 목록)
        pending = df_ord[df_ord['상태'] == "발주완료"].copy()
        
        if pending.empty:
            st.success("🎉 현재 대기 중인 입고 건이 없습니다. (모두 처리됨)")
        else:
            st.write(f"총 **{len(pending)}**건의 입고 대기 항목이 있습니다.")
            
            # 체크박스 컬럼 추가
            pending.insert(0, "입고확인", False)
            
            # 화면에 보여줄 컬럼 지정
            cols_to_show = ['입고확인', '발주ID', '날짜', '거래처', '품명', '수량', '비고', '자재코드']
            
            # 데이터 에디터 (체크박스 기능)
            edited_df = st.data_editor(
                pending[cols_to_show],
                column_config={
                    "입고확인": st.column_config.CheckboxColumn("선택", default=False),
                    "발주ID": st.column_config.TextColumn("발주번호", disabled=True),
                    "수량": st.column_config.NumberColumn("수량", disabled=True),
                },
                disabled=['발주ID', '날짜', '거래처', '품명', '수량', '비고', '자재코드'], # 체크박스 외 수정 불가
                hide_index=True, 
                use_container_width=True
            )
            
            # 3. 입고 처리 버튼 로직
            if st.button("🚚 선택 항목 입고 처리 (재고 반영)", type="primary"):
                # 체크된 항목만 추출
                to_recv = edited_df[edited_df['입고확인'] == True]
                
                if to_recv.empty:
                    st.warning("입고 처리할 항목을 선택해주세요.")
                else:
                    progress_text = st.empty()
                    progress_text.text("데이터베이스 업데이트 중...")
                    
                    # 자재 마스터 데이터 로딩 (재고 업데이트 위치 찾기용)
                    mat_data = ws_mat.get_all_records()
                    # 자재코드 : 행번호 매핑 (gspread는 1부터 시작, 헤더 제외하면 +2)
                    mat_map = {str(r['자재코드']): i+2 for i, r in enumerate(mat_data)}
                    
                    success_count = 0
                    
                    for idx, row in to_recv.iterrows():
                        target_id = str(row['발주ID'])
                        mat_code = str(row['자재코드'])
                        
                        try:
                            qty = int(str(row['수량']).replace(',', ''))
                        except: 
                            qty = 0
                        
                        # A. 발주 내역 시트 업데이트 ('발주완료' -> '입고완료')
                        # 발주ID로 해당 행 찾기
                        cell = ws_ord.find(target_id)
                        if cell:
                            # 6번째 열이 '상태'라고 가정
                            ws_ord.update_cell(cell.row, 6, "입고완료")
                        
                        # B. 자재 마스터 시트 재고 수량 증가 (+)
                        if mat_code in mat_map:
                            row_num = mat_map[mat_code]
                            # 현재 재고 가져오기 (7번째 열이 '현재재고'라고 가정)
                            current_val = ws_mat.cell(row_num, 7).value
                            
                            try:
                                current_stock = int(str(current_val).replace(',', '')) if current_val else 0
                            except:
                                current_stock = 0
                                
                            new_stock = current_stock + qty
                            ws_mat.update_cell(row_num, 7, new_stock)
                            
                        success_count += 1
                    
                    progress_text.empty()
                    st.success(f"✅ 총 {success_count}건 입고 완료! 재고 수량이 증가했습니다.")
                    time.sleep(1.5)
                    st.rerun()



