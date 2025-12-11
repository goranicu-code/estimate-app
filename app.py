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

REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1UQ6_OysueJ07m6Qc5ncfE1NxPCLjc255r6MeFdl0OHQ/edit?gid=1122897158#gid=1122897158"

client = init_connection()
if not client:
    st.error("인증 실패")
    st.stop()
    
try:
    sh = client.open_by_url(REAL_SHEET_URL)
    ws_mat = sh.worksheet("자재마스터")
    ws_ord = sh.worksheet("발주내역")
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
# 5. 화면 UI
# -----------------------------------------------------
st.title("🏭 베스트 화학 통합 ERP")
tab1, tab2, tab3 = st.tabs(["📑 견적 관리", "📦 자재 발주(구매)", "✅ 입고 확인(창고)"])

with tab1:
    st.info("견적 시스템 영역")

# [탭 2] 자재 발주
with tab2:
    st.header("📦 자재 발주 및 신규 등록")

    data_mat = ws_mat.get_all_records()
    df_mat = pd.DataFrame(data_mat)

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 자재 선택 및 입력")
        
        # [수정된 부분] 안전하게 문자열로 변환 후 정렬
        # d['매입처']가 숫자여도 str()로 감싸서 문자로 만든 뒤 정렬함
        suppliers_raw = list(set([str(d.get('매입처', '')).strip() for d in data_mat if str(d.get('매입처', '')).strip()]))
        suppliers = sorted(suppliers_raw)
        suppliers.insert(0, "➕ 신규 거래처 입력")
        
        sel_supplier = st.selectbox("거래처", suppliers)
        
        final_supplier = sel_supplier
        if sel_supplier == "➕ 신규 거래처 입력":
            final_supplier = st.text_input("거래처명 직접 입력")

        # 품명 선택 (안전 정렬 적용)
        items_options = []
        if sel_supplier != "➕ 신규 거래처 입력":
            # 해당 거래처의 품명 리스트
            # 역시 str()로 감싸서 에러 방지
            items_raw = list(set([str(d.get('품명', '')) for d in data_mat if str(d.get('매입처', '')).strip() == final_supplier]))
            items_options = sorted(items_raw)
        
        items_options.insert(0, "➕ 신규 품명 입력")
        sel_item = st.selectbox("품명", items_options)
        
        final_item = sel_item
        if sel_item == "➕ 신규 품명 입력":
            final_item = st.text_input("품명 직접 입력")

        # 규격 선택 (안전 정렬 적용)
        specs_options = []
        if sel_item != "➕ 신규 품명 입력":
            # 해당 품명의 규격 리스트
            specs_raw = list(set([str(d.get('규격', '')) for d in data_mat if str(d.get('품명', '')) == final_item]))
            specs_options = sorted(specs_raw)
        
        specs_options.insert(0, "➕ 신규 규격 입력")
        sel_spec = st.selectbox("규격", specs_options)
        
        final_spec = sel_spec
        if sel_spec == "➕ 신규 규격 입력":
            final_spec = st.text_input("규격 직접 입력")
        
        # 단가 및 수량
        est_price = 0
        if sel_item != "➕ 신규 품명 입력" and sel_spec != "➕ 신규 규격 입력":
            # 안전한 필터링 (str 변환 후 비교)
            # 여기서는 편의상 df_mat 사용 (df_mat은 이미 로드될 때 타입 추론됨)
            # 하지만 안전하게 하기 위해 match 로직 수정
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
                
                # 기존 데이터와 비교 (문자열로 변환하여 안전 비교)
                # 데이터프레임 필터링 시 .astype(str) 사용
                try:
                    match = df_mat[
                        (df_mat['매입처'].astype(str) == final_supplier) & 
                        (df_mat['품명'].astype(str) == final_item) & 
                        (df_mat['규격'].astype(str) == final_spec)
                    ]
                except:
                    match = pd.DataFrame() # 에러나면 없는 셈 침

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
                            st.success(f"{sup} 발주 완료!")
                            time.sleep(1)
                            st.rerun()
        
        if st.button("🗑️ 장바구니 비우기"):
            st.session_state['cart'] = []
            st.rerun()

# [탭 3] 입고 확인
with tab3:
    st.header("✅ 자재 입고 처리")
    
    all_orders = ws_ord.get_all_records()
    df_ord = pd.DataFrame(all_orders)
    
    for col in ['발주ID', '날짜', '거래처', '품명', '수량', '상태', '비고', '자재코드']:
        if col not in df_ord.columns: df_ord[col] = ""

    if not df_ord.empty:
        pending = df_ord[df_ord['상태'] == "발주완료"].copy()
        
        if pending.empty:
            st.info("입고 대기 건이 없습니다.")
        else:
            pending['입고확인'] = False
            # Data Editor
            edited_df = st.data_editor(
                pending[['입고확인', '날짜', '거래처', '품명', '규격', '수량', '자재코드']] if '규격' in pending.columns else pending[['입고확인', '날짜', '거래처', '품명', '수량', '자재코드']],
                column_config={"입고확인": st.column_config.CheckboxColumn("선택", default=False)},
                disabled=['날짜', '거래처', '품명', '규격', '수량', '자재코드'],
                hide_index=True, use_container_width=True
            )
            
            if st.button("🚚 입고 처리"):
                to_recv = edited_df[edited_df['입고확인'] == True]
                if not to_recv.empty:
                    mat_data = ws_mat.get_all_records()
                    mat_map = {str(r['자재코드']): i+2 for i, r in enumerate(mat_data)}
                    
                    for idx, row in to_recv.iterrows():
                        real_row = idx + 2
                        ws_ord.update_cell(real_row, df_ord.columns.get_loc("상태")+1, "입고완료")
                        
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
                            
                    st.success("입고 완료!")
                    time.sleep(1)
                    st.rerun()
