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
REAL_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qHE0vmiPrF4dC0THfirzIBg_mYshXcGp/edit?rtpof=true&gid=1630059230#gid=1630059230"

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
    st.header("견적 자동화")
    st.info("💡 이곳은 지난번에 만든 견적 산출 로직이 들어가는 곳입니다. (생략)")
    # (코드 길이를 줄이기 위해 생략했습니다. 지난번 코드를 여기에 넣으시면 됩니다.)

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

