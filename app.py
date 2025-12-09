import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import time
from fpdf import FPDF # PDF 생성용

# -----------------------------------------------------
# 1. 시스템 설정 및 폰트 설정
# -----------------------------------------------------
st.set_page_config(page_title="베스트 화학 통합 관리 시스템", layout="wide")

# Windows 한글 폰트 경로 (PDF 생성용)
FONT_PATH = "C:/Windows/Fonts/malgun.ttf" # 맑은 고딕

# -----------------------------------------------------
# 2. PDF 발주서 생성 클래스 (HWP 양식 모방)
# -----------------------------------------------------
class PDF(FPDF):
    def header(self):
        # 폰트 등록
        if os.path.exists(FONT_PATH):
            self.add_font("Malgun", "", FONT_PATH, uni=True)
            self.set_font("Malgun", "", 10)
        
        # [제목]
        self.set_font_size(24)
        self.cell(0, 15, "발   주   서", align="C", ln=True)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Malgun", "", 8)
        self.cell(0, 10, f'Page {self.page_no()}', align="C")

def generate_order_pdf(supplier_info, order_items):
    pdf = PDF()
    pdf.add_page()
    
    # 폰트 설정 (맑은 고딕)
    if os.path.exists(FONT_PATH):
        pdf.set_font("Malgun", "", 11)
    else:
        st.error("Windows 폰트 파일(malgun.ttf)을 찾을 수 없습니다. PDF 한글이 깨질 수 있습니다.")

    # 1. 상단 정보 (수신/발신) - HWP 레이아웃 구현
    # 표 그리기 (테두리 있음)
    pdf.set_line_width(0.5)
    
    # [발신인 칸]
    pdf.set_fill_color(240, 240, 240) # 회색 배경
    pdf.cell(30, 10, "  발  신  인", border=1, fill=True)
    pdf.cell(70, 10, "  베스트화학기계공업(주)", border=1)
    
    # [수신인 칸]
    pdf.cell(30, 10, "  수  신  인", border=1, fill=True)
    pdf.cell(60, 10, f"  {supplier_info['name']}", border=1, ln=True)
    
    # [상세 정보]
    pdf.cell(30, 10, "  F   A   X", border=1, fill=True)
    pdf.cell(70, 10, "  032) 684-8318", border=1) # 우리 회사 팩스
    pdf.cell(30, 10, "  F   A   X", border=1, fill=True)
    pdf.cell(60, 10, "  (거래처 팩스번호)", border=1, ln=True) # 나중에 DB에서 가져오게 수정 가능
    
    pdf.cell(30, 10, "  발  주  일", border=1, fill=True)
    pdf.cell(160, 10, f"  {datetime.now().strftime('%Y년 %m월 %d일')}", border=1, ln=True)

    pdf.ln(10)
    
    # 2. 인사말
    pdf.multi_cell(0, 8, "※ 베스트입니다. 다음과 같이 발주하고자 합니다.\n   오늘도 행복한 하루 보내세요. 감사합니다. ^^")
    pdf.ln(5)

    # 3. 자재 목록 (표)
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Malgun", "", 10)
    
    # 헤더
    pdf.cell(15, 10, "No", border=1, align="C", fill=True)
    pdf.cell(70, 10, "품  명", border=1, align="C", fill=True)
    pdf.cell(50, 10, "규  격", border=1, align="C", fill=True)
    pdf.cell(20, 10, "수 량", border=1, align="C", fill=True)
    pdf.cell(35, 10, "비 고", border=1, align="C", fill=True, ln=True)
    
    # 내용 채우기
    total_qty = 0
    for idx, item in enumerate(order_items):
        qty = int(item['qty'])
        total_qty += qty
        
        pdf.cell(15, 8, str(idx+1), border=1, align="C")
        pdf.cell(70, 8, str(item['name']), border=1, align="L")
        pdf.cell(50, 8, str(item['spec']), border=1, align="C")
        pdf.cell(20, 8, str(qty), border=1, align="C")
        pdf.cell(35, 8, str(item.get('note', '')), border=1, align="L", ln=True)

    # 합계
    pdf.cell(135, 8, "합    계", border=1, align="C")
    pdf.cell(20, 8, str(total_qty), border=1, align="C")
    pdf.cell(35, 8, "", border=1, ln=True)

    pdf.ln(10)
    
    # 4. 하단 직인
    pdf.set_font("Malgun", "", 14)
    pdf.cell(0, 10, "베스트화학기계공업(주)   (인)", align="R", ln=True)
    
    # 임시 파일 저장
    file_name = f"발주서_{supplier_info['name']}_{datetime.now().strftime('%Y%m%d')}.pdf"
    pdf.output(file_name)
    return file_name

# -----------------------------------------------------
# 3. 구글 시트 연결 (기존 로직 유지)
# -----------------------------------------------------
@st.cache_resource
def init_connection():
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if os.path.exists("service_account.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
        client = gspread.authorize(creds)
        return client
    return None

# ⚠️ 실제 시트 주소 확인 필수
REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1UQ6_OysueJ07m6Qc5ncfE1NxPCLjc255r6MeFdl0OHQ/edit?gid=1122897158#gid=1122897158"

client = init_connection()
if client and REAL_SHEET_URL:
    try:
        sh = client.open_by_url(REAL_SHEET_URL)
        ws_mat = sh.worksheet("자재마스터")
        ws_ord = sh.worksheet("발주내역")
    except:
        st.error("구글 시트 연결 실패. URL이나 시트 이름을 확인하세요.")
        st.stop()
else:
    st.error("인증 파일 오류.")
    st.stop()

# -----------------------------------------------------
# 4. 화면 UI
# -----------------------------------------------------
st.title("🏭 베스트 화학 기계 공업 통합 ERP")
tab1, tab2, tab3 = st.tabs(["📑 견적 관리", "📦 자재 발주(구매)", "✅ 입고 확인(창고)"])

# [탭 1] 견적 (생략)
with tab1:
    st.info("견적 시스템 영역입니다.")

# [탭 2] 자재 발주 (PDF 생성 및 팩스 기능 추가)
with tab2:
    st.header("📦 자재 발주서 생성")

    # DB 로드
    df_mat = pd.DataFrame(ws_mat.get_all_records())

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("1. 발주할 자재 선택")
        # 거래처 먼저 선택
        suppliers = df_mat['매입처'].unique().tolist()
        selected_supplier = st.selectbox("거래처 선택", suppliers)
        
        # 해당 거래처 품목만 필터링
        filtered_items = df_mat[df_mat['매입처'] == selected_supplier]
        selected_item_name = st.selectbox("품명 선택", filtered_items['품명'].unique())
        
        # 상세 정보
        item_row = filtered_items[filtered_items['품명'] == selected_item_name].iloc[0]
        st.info(f"규격: {item_row['규격']} | 단가: {item_row['단가']:,}원")
        
        qty = st.number_input("수량", min_value=1, value=10)
        note = st.text_input("비고 (특이사항)")
        
        # 장바구니 담기 (세션 스테이트 활용)
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
            st.success("추가되었습니다.")

    with col2:
        st.subheader(f"2. {selected_supplier} 발주 목록")
        
        # 현재 장바구니 보여주기
        cart_df = pd.DataFrame(st.session_state['cart'])
        if not cart_df.empty:
            # 현재 선택한 거래처 것만 필터링해서 보여줌
            current_cart = cart_df[cart_df['supplier'] == selected_supplier]
            st.dataframe(current_cart[['name', 'spec', 'qty', 'note']], hide_index=True)
            
            if not current_cart.empty:
                st.markdown("---")
                # [기능 1] 발주서 PDF 생성
                if st.button("📄 발주서 PDF 생성 (미리보기)"):
                    pdf_file = generate_order_pdf({'name': selected_supplier}, current_cart.to_dict('records'))
                    
                    with open(pdf_file, "rb") as f:
                        st.download_button(
                            label="📥 PDF 다운로드",
                            data=f,
                            file_name=pdf_file,
                            mime="application/pdf"
                        )
                
                # [기능 2] 팩스 전송 및 DB 저장
                if st.button("📠 팩스 전송 및 발주 확정", type="primary"):
                    # A. PDF 생성 (팩스용)
                    pdf_file = generate_order_pdf({'name': selected_supplier}, current_cart.to_dict('records'))
                    
                    # B. 팩스 전송 시뮬레이션
                    with st.spinner(f"032-684-8318 -> {selected_supplier} 팩스 전송 중..."):
                        time.sleep(2) # 전송하는 척
                        st.toast(f"✅ {selected_supplier}로 팩스 전송 완료!", icon="📠")
                    
                    # C. 구글 시트(발주내역)에 저장
                    now_str = datetime.now().strftime("%Y-%m-%d")
                    order_id = datetime.now().strftime("%y%m%d%H%M")
                    
                    new_rows = []
                    for _, row in current_cart.iterrows():
                        new_rows.append([
                            order_id, now_str, row['supplier'], 
                            row['name'], row['qty'], "발주완료", row['note'], 
                            row['code'] # 자재코드도 저장 (나중에 입고처리를 위해)
                        ])
                    
                    ws_ord.append_rows(new_rows)
                    
                    # 장바구니 비우기
                    st.session_state['cart'] = [item for item in st.session_state['cart'] if item['supplier'] != selected_supplier]
                    st.success("DB 저장 완료. 입고 대기 상태로 전환됩니다.")
                    time.sleep(1)
                    st.rerun()

# [탭 3] 입고 처리 (핵심 기능)
with tab3:
    st.header("✅ 자재 입고 확인")
    
    # 1. 발주내역 중 '발주완료' 상태인 것만 불러오기
    all_orders = ws_ord.get_all_records()
    df_ord = pd.DataFrame(all_orders)
    
    if df_ord.empty:
        st.info("발주 내역이 없습니다.")
    else:
        # 상태가 '발주완료'인 것만 필터링
        pending_orders = df_ord[df_ord['상태'] == "발주완료"].copy()
        
        if pending_orders.empty:
            st.success("모든 자재가 입고 처리되었습니다.")
        else:
            st.subheader("입고 대기 목록")
            
            # 체크박스 추가 (Data Editor 활용)
            pending_orders['입고확인'] = False # 체크박스 컬럼 추가
            
            # 화면에 표시할 컬럼 정리
            display_cols = ['입고확인', '발주ID', '날짜', '거래처', '품명', '수량', '비고', '자재코드'] # 자재코드는 숨겨도 되지만 로직상 필요
            
            edited_df = st.data_editor(
                pending_orders[display_cols],
                column_config={
                    "입고확인": st.column_config.CheckboxColumn("입고 선택", default=False)
                },
                disabled=['발주ID', '날짜', '거래처', '품명', '수량'], # 다른 건 수정 불가
                hide_index=True,
                use_container_width=True
            )
            
            # [기능 3] 입고 처리 버튼
            if st.button("🚚 선택한 항목 입고 처리"):
                # 체크된 항목만 가져오기
                to_receive = edited_df[edited_df['입고확인'] == True]
                
                if to_receive.empty:
                    st.warning("입고할 항목을 체크해주세요.")
                else:
                    with st.spinner("재고 수량 업데이트 중..."):
                        # 로직:
                        # 1. 발주내역 시트 -> 상태를 '입고완료'로 변경
                        # 2. 자재마스터 시트 -> 현재고를 +수량 만큼 증가
                        
                        # 최신 자재 데이터 가져오기
                        mat_data = ws_mat.get_all_records()
                        
                        # gspread의 find 기능을 쓰면 느리므로, 한 번에 읽어서 처리
                        # 셀 업데이트 리스트 준비
                        cell_updates_ord = [] # 발주내역 수정용
                        
                        # 자재마스터 수량 수정을 위한 딕셔너리
                        stock_updates = {} # { 'MAT-001': 50 } 형태 (코드: 현재고)
                        
                        # 자재마스터에서 현재고 위치 찾기용 맵
                        mat_row_map = {row['자재코드']: i+2 for i, row in enumerate(mat_data)} 
                        # i+2인 이유: i는 0부터 시작, 시트는 1부터 시작 + 헤더 1줄
                        
                        count = 0
                        for index, row in to_receive.iterrows():
                            # A. 발주내역 상태 변경 ('발주완료' -> '입고완료')
                            # 원본 df_ord에서 해당 행의 위치(row index)를 찾아야 함
                            # 시트 행 번호 = (전체 데이터에서의 인덱스) + 2 (헤더)
                            real_row_idx = index + 2 
                            # '상태' 컬럼이 F열(6번째)라고 가정 (시트 구조에 따라 다를 수 있음)
                            # 안전하게 컬럼명으로 인덱스 찾기
                            status_col_idx = df_ord.columns.get_loc("상태") + 1
                            
                            ws_ord.update_cell(real_row_idx, status_col_idx, "입고완료")
                            
                            # B. 자재마스터 재고 증가 계산
                            mat_code = row['자재코드']
                            qty_in = int(row['수량'])
                            
                            if mat_code in mat_row_map:
                                # 기존 재고 찾기
                                current_stock = 0
                                for m_row in mat_data:
                                    if m_row['자재코드'] == mat_code:
                                        current_stock = int(str(m_row['현재고']).replace(',','')) if m_row['현재고'] else 0
                                        break
                                
                                # 누적 업데이트 (같은 자재를 여러 번 발주했을 경우 대비)
                                if mat_code in stock_updates:
                                    stock_updates[mat_code] += qty_in
                                else:
                                    stock_updates[mat_code] = current_stock + qty_in
                            
                            count += 1
                        
                        # 자재마스터 실제 업데이트
                        for code, new_qty in stock_updates.items():
                            row_num = mat_row_map[code]
                            col_num = 7 # 현재고 컬럼 위치 (G열) - 헤더 순서 확인 필요!
                            # 헤더: 자재코드, 품명, 규격, 단위, 단가, 매입처, 현재고(7번째)
                            ws_mat.update_cell(row_num, col_num, new_qty)
                            
                    st.success(f"총 {count}건 입고 처리 완료! 재고가 증가했습니다.")
                    time.sleep(1)
                    st.rerun()
