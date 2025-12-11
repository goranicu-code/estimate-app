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
# 2. PDF 생성 클래스 (발주서용)
# -----------------------------------------------------
class PDF(FPDF):
    def header(self):
        if os.path.exists(FONT_FILE):
            self.add_font("NanumGothic", "", FONT_FILE, uni=True)
            self.set_font("NanumGothic", "", 10)
        else: self.set_font("Arial", "", 10)
        
        self.set_font_size(24)
        try: self.cell(0, 15, "발   주   서", align="C", ln=True)
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
    pdf.cell(30, 10, "  F   A   X", border=1, fill=True)
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

REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1UQ6_OysueJ07m6Qc5ncfE1NxPCLjc255r6MeFdl0OHQ/edit?gid=2044618684#gid=2044618684"

client = init_connection()
if not client:
    st.error("인증 실패")
    st.stop()
    
try:
    sh = client.open_by_url(REAL_SHEET_URL)
    ws_mat = sh.worksheet("자재마스터")
    ws_ord = sh.worksheet("발주내역")
    # 견적 DB 시트 연결 (없으면 생성)
    try: ws_quote = sh.worksheet("견적DB")
    except: 
        ws_quote = sh.add_worksheet(title="견적DB", rows=100, cols=20)
        ws_quote.append_row(["견적ID", "날짜", "설비", "용량", "메인", "서브", "방폭", "재질", "옵션", "총액"])
except:
    st.error("구글 시트 연결 실패")
    st.stop()

# -----------------------------------------------------
# 4. 스마트 자재코드 생성 함수
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
# 5. 견적 데이터 매핑 (복구된 로직)
# -----------------------------------------------------
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

# -----------------------------------------------------
# 6. 화면 UI 메인
# -----------------------------------------------------
st.title("🏭 베스트 화학 통합 ERP")
tab1, tab2, tab3 = st.tabs(["📑 견적 관리(영업)", "📦 자재 발주(구매)", "✅ 입고 확인(창고)"])

# [탭 1] 견적 시스템 (복구 완료!)
with tab1:
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
    
    # [가견적 산출] 버튼
    if st.button("📝 가견적 산출 (미리보기)", type="primary"):
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
        
        # 상세 내역(BOM) 가견적 생성
        initial_bom = [
            {"항목": "Main Motor", "규격": main_hp, "단가": 0, "수량": 1, "비고": "자동선택"},
            {"항목": "Sub Motor", "규격": sub_hp, "단가": 0, "수량": 1, "비고": "자동선택"},
            {"항목": "Body Vessel", "규격": f"{capacity} ({material})", "단가": 0, "수량": 1, "비고": "제관"},
            {"항목": "Control Panel", "규격": explosion_type, "단가": 0, "수량": 1, "비고": "전장"},
        ]
        st.session_state['quote_detail_df'] = pd.DataFrame(initial_bom)

    # 견적 결과 표시
    if 'quote_data' in st.session_state and st.session_state['quote_data']:
        st.divider()
        st.subheader(f"📋 견적서 작성 (ID: {st.session_state['quote_data']['견적ID']})")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.info("요약 정보")
            st.json(st.session_state['quote_data'])
        
        with col2:
            st.write("👇 **단가 및 수량 수정**")
            if 'quote_detail_df' in st.session_state:
                edited_df = st.data_editor(
                    st.session_state['quote_detail_df'],
                    num_rows="dynamic",
                    use_container_width=True
                )
                total_estimate = (edited_df['단가'] * edited_df['수량']).sum()
                st.metric("총 예상 견적가", f"{total_estimate:,} 원")

                if st.button("💾 견적 DB에 최종 저장"):
                    q = st.session_state['quote_data']
                    row_data = [
                        q['견적ID'], q['날짜'], q['설비'], q['용량'], q['메인'], q['서브'], 
                        q['방폭'], q['재질'], q['옵션'], int(total_estimate)
                    ]
                    ws_quote.append_row(row_data)
                    st.success("✅ 견적 DB에 저장되었습니다!")
                    st.balloons()

# [탭 2] 자재 발주
with tab2:
    st.header("📦 자재 발주 및 신규 등록")

    data_mat = ws_mat.get_all_records()
    df_mat = pd.DataFrame(data_mat)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 자재 선택 및 입력")
        
        # 데이터 안전 정렬
        suppliers_raw = list(set([str(d.get('매입처', '')).strip() for d in data_mat if str(d.get('매입처', '')).strip()]))
        suppliers = sorted(suppliers_raw)
        suppliers.insert(0, "➕ 신규 거래처 입력")
        
        sel_supplier = st.selectbox("거래처", suppliers)
        final_supplier = st.text_input("거래처명 직접 입력") if sel_supplier == "➕ 신규 거래처 입력" else sel_supplier

        # 품명 선택
        items_options = []
        if sel_supplier != "➕ 신규 거래처 입력":
            items_raw = list(set([str(d.get('품명', '')) for d in data_mat if str(d.get('매입처', '')).strip() == final_supplier]))
            items_options = sorted(items_raw)
        
        items_options.insert(0, "➕ 신규 품명 입력")
        sel_item = st.selectbox("품명", items_options)
        final_item = st.text_input("품명 직접 입력") if sel_item == "➕ 신규 품명 입력" else sel_item

        # 규격 선택
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

        # 장바구니
        if 'cart' not in st.session_state: st.session_state['cart'] = []

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
                    new_mat_row = [mat_code, final_item, final_spec, "", price, final_supplier, 0]
                    ws_mat.append_row(new_mat_row)
                    st.toast(f"✨ 새 자재 [{final_item}]가 자재마스터에 자동 등록되었습니다!")
                
                st.session_state['cart'].append({
                    'code': mat_code,
                    'name': final_item,
                    'spec': final_spec,
                    'qty': qty,
                    'supplier': final_supplier,
                    'note': note,
                    'is_new': is_new
                })
                st.success("장바구니에 담았습니다.")

    with col2:
        st.subheader("2. 발주 대기 목록")
        cart_df = pd.DataFrame(st.session_state['cart'])
        
        if not cart_df.empty:
            st.dataframe(cart_df[['supplier', 'name', 'spec', 'qty', 'note']], hide_index=True)
            
            unique_suppliers = cart_df['supplier'].unique()
            
            for sup in unique_suppliers:
                st.markdown(f"--- \n **🏢 {sup} 발주 처리**")
                current_cart = cart_df[cart_df['supplier'] == sup]
                
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(f"📄 PDF 생성 ({sup})"):
                        pdf_file = generate_order_pdf({'name': sup}, current_cart.to_dict('records'))
                        if pdf_file:
                            with open(pdf_file, "rb") as f:
                                st.download_button("📥 다운로드", f, file_name=pdf_file, mime="application/pdf")
                with c2:
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
                            st.success(f"{sup} 발주 완료! '발주내역' 시트를 확인하세요.")
                            time.sleep(1)
                            st.rerun()
        
        if st.button("🗑️ 장바구니 비우기"):
            st.session_state['cart'] = []
            st.rerun()

# [탭 3] 입고 확인
with tab3:
    st.header("✅ 자재 입고 처리")
    
    raw_data = ws_ord.get_all_values()
    
    if len(raw_data) < 2:
        st.info("발주 내역이 없습니다.")
    else:
        headers = ["발주ID", "날짜", "거래처", "품명", "수량", "상태", "비고", "자재코드"]
        clean_rows = []
        for row in raw_data[1:]:
            if len(row) < 8:
                row += [""] * (8 - len(row))
            clean_rows.append(row[:8])
            
        df_ord = pd.DataFrame(clean_rows, columns=headers)
        df_ord['상태'] = df_ord['상태'].astype(str).str.strip()
        
        pending = df_ord[df_ord['상태'] == "발주완료"].copy()
        
        if pending.empty:
            st.info("입고 대기 중인 건이 없습니다. (모두 입고완료 상태이거나 데이터가 없음)")
        else:
            pending['입고확인'] = False
            
            cols_to_show = ['입고확인', '발주ID', '날짜', '거래처', '품명', '수량', '비고', '자재코드']
            edited_df = st.data_editor(
                pending[cols_to_show],
                column_config={
                    "입고확인": st.column_config.CheckboxColumn("선택", default=False),
                    "발주ID": st.column_config.TextColumn("발주번호", disabled=True),
                },
                disabled=['발주ID', '날짜', '거래처', '품명', '수량', '비고', '자재코드'],
                hide_index=True, use_container_width=True
            )
            
            if st.button("🚚 입고 처리"):
                to_recv = edited_df[edited_df['입고확인'] == True]
                if not to_recv.empty:
                    mat_data = ws_mat.get_all_records()
                    mat_map = {str(r['자재코드']): i+2 for i, r in enumerate(mat_data)}
                    
                    count = 0
                    for idx, row in to_recv.iterrows():
                        target_id = str(row['발주ID'])
                        cell = ws_ord.find(target_id)
                        if cell:
                            ws_ord.update_cell(cell.row, 6, "입고완료")
                            
                            code = str(row['자재코드'])
                            try: qty = int(row['수량'])
                            except: qty = 0
                            
                            if code in mat_map:
                                cur_stock = 0
                                try: 
                                    val = ws_mat.cell(mat_map[code], 7).value 
                                    cur_stock = int(str(val).replace(',','')) if val else 0
                                except: pass
                                ws_mat.update_cell(mat_map[code], 7, cur_stock + qty)
                            count += 1
                            
                    st.success(f"{count}건 입고 완료! 재고에 반영되었습니다.")
                    time.sleep(1)
                    st.rerun()
