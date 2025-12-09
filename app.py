import streamlit as st
import pandas as pd
import datetime

# -----------------------------------------------------
# 1. 기초 데이터 세팅 (가상의 DB 역할)
# -----------------------------------------------------
# 실제로는 엑셀 파일이나 구글 시트를 불러오게 연결할 겁니다.
if 'materials' not in st.session_state:
    # 임시 자재 데이터
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
# 2. 메인 화면 구성
# -----------------------------------------------------
st.set_page_config(page_title="베스트 화학 기계 공업 통합 ERP", layout="wide")

st.title("🏭 베스트 화학 기계 공업 통합 관리 시스템")
st.markdown("---")

# 탭 생성
tab1, tab2, tab3 = st.tabs(["📑 견적 관리(영업)", "📦 자재 발주(구매)", "📊 재고 관리(창고)"])

# =====================================================
# [탭 1] 지난번 개발한 견적 자동화 연결
# =====================================================
with tab1:
    st.header("견적 자동화 시스템")
    st.info("지난번에 만드신 견적 산출 로직이 이곳에 들어갑니다.")
    
    # (예시 기능)
    project_name = st.text_input("프로젝트 명 (예: 2톤 교반기)")
    if st.button("BOM 불러오기 및 견적 산출"):
        st.success(f"'{project_name}'에 대한 견적서가 생성되었습니다.")
        # 여기에 지난번 코드를 붙여넣으면 됩니다.

# =====================================================
# [탭 2] 자재 발주 (오늘의 핵심)
# =====================================================
with tab2:
    st.header("자재 발주 시스템")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("⚠️ 재고 부족/발주 필요 목록")
        df_mat = st.session_state['materials']
        # 재고가 2개 이하인 것만 필터링
        low_stock = df_mat[df_mat['재고'] <= 2]
        st.dataframe(low_stock, use_container_width=True)
    
    with col2:
        st.subheader("발주 입력")
        target_item = st.selectbox("발주할 자재 선택", df_mat['품명'])
        order_qty = st.number_input("발주 수량", min_value=1, value=5)
        
        if st.button("발주서 생성 및 기록"):
            # 선택한 자재의 정보 찾기
            selected_row = df_mat[df_mat['품명'] == target_item].iloc[0]
            
            # 발주 데이터 추가
            new_order = {
                '날짜': datetime.datetime.now().strftime("%Y-%m-%d"),
                '거래처': selected_row['거래처'],
                '품명': target_item,
                '수량': order_qty,
                '상태': '발주완료'
            }
            st.session_state['orders'] = pd.concat([st.session_state['orders'], pd.DataFrame([new_order])], ignore_index=True)
            st.success(f"{target_item} {order_qty}개 발주 처리가 완료되었습니다!")

    st.markdown("---")
    st.subheader("📋 발주 진행 현황")
    st.dataframe(st.session_state['orders'], use_container_width=True)

# =====================================================
# [탭 3] 재고 관리
# =====================================================
with tab3:
    st.header("실시간 자재 재고 현황")
    
    # 현재고 보여주기
    edited_df = st.data_editor(
        st.session_state['materials'],
        num_rows="dynamic",
        use_container_width=True,
        key="inventory_editor"
    )
    
    # 수정된 데이터 저장 버튼
    if st.button("재고 변동사항 저장"):
        st.session_state['materials'] = edited_df
        st.success("재고가 업데이트되었습니다.")
