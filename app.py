import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import time
import urllib.request # 인터넷에서 파일 다운로드용
from fpdf import FPDF

# -----------------------------------------------------
# 1. 시스템 설정 및 한글 폰트 자동 준비
# -----------------------------------------------------
st.set_page_config(page_title="베스트 화학 통합 관리 시스템", layout="wide")

# 폰트 파일명
FONT_FILE = "NanumGothic.ttf"

# [핵심] 폰트가 없으면 자동으로 다운로드 받는 함수
def ensure_font_exists():
    if not os.path.exists(FONT_FILE):
        # 네이버 나눔글꼴(오픈소스) 다운로드 링크
        url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
        try:
            with st.spinner("한글 폰트 다운로드 중... (최초 1회만 실행됨)"):
                urllib.request.urlretrieve(url, FONT_FILE)
            st.success("폰트 다운로드 완료!")
        except Exception as e:
            st.error(f"폰트 다운로드 실패: {e}")
            return False
    return True

# -----------------------------------------------------
# 2. PDF 발주서 생성 클래스 (업로드한 HWP 양식 반영)
# -----------------------------------------------------
class PDF(FPDF):
    def header(self):
        # 폰트 등록
        if os.path.exists(FONT_FILE):
            self.add_font("NanumGothic", "", FONT_FILE, uni=True)
            self.set_font("NanumGothic", "", 10)
        else:
            self.set_font("Arial", "", 10) # 폰트 없으면 영문이라도 나오게
        
        # [제목] 큰 글씨
        self.set_font_size(24)
        try:
            self.cell(0, 15, "발   주   서", align="C", ln=True)
        except:
            self.cell(0, 15, "ORDER SHEET", align="C", ln=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        if os.path.exists(FONT_FILE):
            self.set_font("NanumGothic", "", 8)
        else:
            self.set_font("Arial", "", 8)
        self.cell(0, 10, f'Page {self.page_no()}', align="C")

def generate_order_pdf(supplier_info, order_items):
    # 폰트 파일 준비 확인
    if not ensure_font_exists():
        st.error("한글 폰트가 없어서 PDF를 생성할 수 없습니다.")
        return None

    pdf = PDF()
    pdf.add_page()
    pdf.set_font("NanumGothic", "", 11)

    # --- [상단: 수신/발신 정보 박스] ---
    # 업로드하신 HWP 양식과 최대한 비슷하게 표를 그립니다.
    
    # 1. 발신인 (우리 회사)
    pdf.set_fill_color(240, 240, 240) # 연한 회색 배경
    pdf.cell(30, 10, "  발  신  인", border=1, fill=True)
    pdf.cell(160, 10, "  베스트화학기계공업(주)   (담당: 김송이 대리)", border=1, ln=True)
    
    # 2. 수신인 (거래처)
    pdf.cell(30, 10, "  수  신  인", border=1, fill=True)
    pdf.cell(60, 10, f"  {supplier_info['name']}", border=1)
    
    # 3. 팩스 번호
    pdf.cell(30, 10, "  F   A   X", border=1, fill=True)
    # 거래처 팩스번호가 있으면 넣고 없으면 빈칸
    supplier_fax = supplier_info.get('fax', '') 
    pdf.cell(70, 10, f"  {supplier_fax}", border=1, ln=True)
    
    # 4. 발주 날짜
    pdf.cell(30, 10, "  발  주  일", border=1, fill=True)
    pdf.cell(160, 10, f"  {datetime.now().strftime('%Y년 %m월 %d일')}", border=1, ln=True)

    pdf.ln(8)
    
    # --- [인사말] ---
    pdf.multi_cell(0, 6, "※ 베스트입니다. 다음과 같이 발주하고자 합니다.\n   오늘도 행복한 하루 보내세요. 감사합니다. ^^")
    pdf.ln(5)

    # --- [자재 목록 표] ---
    pdf.set_fill_color(220, 220, 220) # 헤더 배경색
    
    # 헤더
    pdf.cell(15, 8, "No", border=1, align="C", fill=True)
    pdf.cell(70, 8, "품  명", border=1, align="C", fill=True)
    pdf.cell(50, 8, "규  격", border=1, align="C", fill=True)
    pdf.cell(20, 8, "수 량", border=1, align="C", fill=True)
    pdf.cell(35, 8, "비 고", border=1, align="C", fill=True, ln=True)
    
    # 내용
    total_qty = 0
    for idx, item in enumerate(order_items):
        qty = int(item['qty'])
        total_qty += qty
        
        pdf.cell(15, 8, str(idx+1), border=1, align="C")
        pdf.cell(70, 8, str(item['name']), border=1, align="L") # 품명은 왼쪽 정렬
        pdf.cell(50, 8, str(item['spec']), border=1, align="C") # 규격은 가운데
        pdf.cell(20, 8, str(qty), border=1, align="C")
        pdf.cell(35, 8, str(item.get('note', '')), border=1, align="L", ln=True)

    # 합계 행
    pdf.cell(135, 8, "합    계", border=1, align="C")
    pdf.cell(20, 8, str(total_qty), border=1, align="C")
    pdf.cell(35, 8, "", border=1, ln=True)

    pdf.ln(15)
    
    # --- [하단 직인] ---
    pdf.set_font_size(16)
    pdf.cell(0, 10, "베스트화학기계공업(주)   (인)", align="R", ln=True)
    
    # 파일명 생성
    file_name = f"발주서_{supplier_info['name']}_{datetime.now().strftime('%y%m%d')}.pdf"
    pdf.output(file_name)
    return file_name

# -----------------------------------------------------
# 3. 구글 시트 연결
# -----------------------------------------------------
@st.cache_resource
# [수정된 연결 함수] - 훨씬 똑똑해졌습니다!
@st.cache_resource
def init_connection():
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    creds_dict = None
    
    # 1. 스트림릿 클라우드 비밀 금고(Secrets) 확인
    # Case A: 정석대로 [gcp_service_account] 제목을 붙인 경우
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        # st.write("Debug: Secrets 섹션 발견됨") # 디버깅용
        
    # Case B: 제목 없이 내용만 붙여넣은 경우 (흔한 실수 방지)
    elif "private_key" in st.secrets:
        creds_dict = st.secrets
        # st.write("Debug: Secrets 루트에서 키 발견됨") # 디버깅용

    # 2. 내 컴퓨터 파일 확인 (로컬 실행용)
    elif os.path.exists("service_account.json"):
        creds_dict = json.load(open("service_account.json"))
        # st.write("Debug: 로컬 json 파일 발견됨") # 디버깅용

    # 3. 결과 처리
    if creds_dict is not None:
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
            client = gspread.authorize(creds)
            return client
        except Exception as e:
            st.error(f"🚨 인증 정보는 찾았지만 연결에 실패했습니다: {e}")
            return None
    else:
        # 4. 정말 아무것도 없을 때 (사용자에게 힌트 주기)
        st.error("🚨 인증 정보를 찾을 수 없습니다!")
        st.info("💡 힌트: Streamlit Cloud -> Settings -> Secrets 에 내용을 붙여넣으셨나요?")
        
        # 현재 Secrets에 뭐가 들어있는지 살짝 보여줌 (보안상 키 이름만)
        if hasattr(st, 'secrets'):
            st.code(f"현재 감지된 키 목록: {list(st.secrets.keys())}")
            
        return None

# ⚠️ 사장님 진짜 시트 주소
REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1UQ6_OysueJ07m6Qc5ncfE1NxPCLjc255r6MeFdl0OHQ/edit?gid=1122897158#gid=1122897158"

client = init_connection()
if client and REAL_SHEET_URL:
    try:
        sh = client.open_by_url(REAL_SHEET_URL)
        ws_mat = sh.worksheet("자재마스터")
        ws_ord = sh.worksheet("발주내역")
    except:
        st.error("구글 시트 연결 실패. URL을 확인하세요.")
        st.stop()
else:
    st.error("인증 파일(service_account.json)이 없습니다.")
    st.stop()

# -----------------------------------------------------
# 4. 화면 UI
# -----------------------------------------------------
st.title("🏭 베스트 화학 기계 공업 통합 ERP")
tab1, tab2, tab3 = st.tabs(["📑 견적 관리", "📦 자재 발주(구매)", "✅ 입고 확인(창고)"])

# [탭 1] (생략)
with tab1:
    st.info("견적 시스템 영역입니다.")

# [탭 2] 자재 발주
with tab2:
    st.header("📦 자재 발주 및 발송")

    # DB 로드
    df_mat = pd.DataFrame(ws_mat.get_all_records())

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 자재 선택")
        suppliers = df_mat['매입처'].unique().tolist()
        selected_supplier = st.selectbox("거래처", suppliers)
        
        filtered_items = df_mat[df_mat['매입처'] == selected_supplier]
        selected_item_name = st.selectbox("품명", filtered_items['품명'].unique())
        
        item_row = filtered_items[filtered_items['품명'] == selected_item_name].iloc[0]
        st.caption(f"규격: {item_row['규격']} | 코드: {item_row['자재코드']}")
        
        qty = st.number_input("수량", min_value=1, value=10)
        note = st.text_input("비고")
        
        if 'cart' not in st.session_state: st.session_state['cart'] = []
        
        if st.button("장바구니 담기 ⬇️"):
            st.session_state['cart'].append({
                'code': item_row['자재코드'],
                'name': selected_item_name,
                'spec': item_row['규격'],
                'qty': qty,
                'supplier': selected_supplier,
                'note': note
            })
            st.success("담았습니다.")

    with col2:
        st.subheader(f"2. 발주서 미리보기 ({selected_supplier})")
        
        cart_df = pd.DataFrame(st.session_state['cart'])
        if not cart_df.empty:
            current_cart = cart_df[cart_df['supplier'] == selected_supplier]
            st.dataframe(current_cart[['name', 'spec', 'qty', 'note']], hide_index=True)
            
            if not current_cart.empty:
                st.markdown("---")
                
                # [기능 1] 발주서 생성
                if st.button("📄 발주서 PDF 생성"):
                    pdf_file = generate_order_pdf({'name': selected_supplier}, current_cart.to_dict('records'))
                    
                    if pdf_file:
                        with open(pdf_file, "rb") as f:
                            st.download_button("📥 PDF 다운로드", f, file_name=pdf_file, mime="application/pdf")

                # [기능 2] 팩스 전송 및 저장
                if st.button("📠 팩스 전송 및 확정", type="primary"):
                    with st.spinner("팩스 전송 및 DB 저장 중..."):
                        # PDF 생성 (기록용)
                        generate_order_pdf({'name': selected_supplier}, current_cart.to_dict('records'))
                        time.sleep(1) # 전송 시뮬레이션
                        
                        # 시트 저장
                        now_str = datetime.now().strftime("%Y-%m-%d")
                        order_id = datetime.now().strftime("%y%m%d%H%M")
                        new_rows = []
                        for _, row in current_cart.iterrows():
                            new_rows.append([
                                order_id, now_str, row['supplier'], 
                                row['name'], row['qty'], "발주완료", row['note'], row['code']
                            ])
                        ws_ord.append_rows(new_rows)
                        
                        # 장바구니 비우기
                        st.session_state['cart'] = [item for item in st.session_state['cart'] if item['supplier'] != selected_supplier]
                        st.success("✅ 발주가 완료되었습니다!")
                        time.sleep(1)
                        st.rerun()

# [탭 3] 입고 처리
with tab3:
    st.header("✅ 자재 입고 처리")
    
    all_orders = ws_ord.get_all_records()
    df_ord = pd.DataFrame(all_orders)
    
    if not df_ord.empty:
        pending_orders = df_ord[df_ord['상태'] == "발주완료"].copy()
        
        if pending_orders.empty:
            st.success("입고 대기 중인 건이 없습니다.")
        else:
            pending_orders['입고확인'] = False
            
            edited_df = st.data_editor(
                pending_orders[['입고확인', '날짜', '거래처', '품명', '수량', '자재코드']],
                column_config={"입고확인": st.column_config.CheckboxColumn("선택", default=False)},
                disabled=['날짜', '거래처', '품명', '수량'],
                hide_index=True,
                use_container_width=True
            )
            
            if st.button("🚚 선택 항목 입고 잡기"):
                to_receive = edited_df[edited_df['입고확인'] == True]
                if to_receive.empty:
                    st.warning("항목을 체크해주세요.")
                else:
                    with st.spinner("재고 반영 중..."):
                        mat_data = ws_mat.get_all_records()
                        mat_row_map = {str(row['자재코드']): i+2 for i, row in enumerate(mat_data)}
                        stock_updates = {}
                        
                        for index, row in to_receive.iterrows():
                            # 상태 변경
                            real_row_idx = index + 2
                            status_col_idx = df_ord.columns.get_loc("상태") + 1
                            ws_ord.update_cell(real_row_idx, status_col_idx, "입고완료")
                            
                            # 재고 계산
                            code = str(row['자재코드'])
                            qty = int(row['수량'])
                            
                            if code in mat_row_map:
                                current_stock = 0
                                for m_row in mat_data:
                                    if str(m_row['자재코드']) == code:
                                        try:
                                            current_stock = int(str(m_row['현재고']).replace(',',''))
                                        except: current_stock = 0
                                        break
                                
                                if code in stock_updates: stock_updates[code] += qty
                                else: stock_updates[code] = current_stock + qty
                        
                        # 재고 업데이트
                        for code, new_qty in stock_updates.items():
                            if code in mat_row_map:
                                ws_mat.update_cell(mat_row_map[code], 7, new_qty) # 7=현재고 컬럼
                                
                    st.success("입고 처리 완료! 재고가 증가했습니다.")
                    time.sleep(1)
                    st.rerun()

