import streamlit as st
import pandas as pd

# -----------------------------------------------------------
# 1. 구글 시트 연동 설정
# -----------------------------------------------------------
# [중요] 아까 복사한 '웹에 게시' 주소를 따옴표 안에 붙여넣으세요!
# 이렇게 바꾸세요! (st.secrets가 금고입니다)
SHEET_URL = st.secrets["private_sheet_url"]

st.set_page_config(page_title="화학설비 원스톱 시스템", layout="wide")
st.title("🏭 베스트 화학 기계 - 클라우드 단가표 연동 버전")

# 데이터 불러오기 함수 (캐시 기능: 60초마다 갱신)
@st.cache_data(ttl=60) 
def load_data():
    try:
        # 구글 시트(CSV)를 인터넷에서 바로 읽어옵니다
        df_price = pd.read_csv(SHEET_URL)
        return df_price
    except Exception as e:
        return None

# 데이터 로드
df_price = load_data()

# -----------------------------------------------------------
# 2. 에러 처리 (주소 잘못 넣었을 때)
# -----------------------------------------------------------
if df_price is None:
    st.error("🚨 구글 시트를 불러올 수 없습니다!")
    st.warning("1. 코드 위쪽 `SHEET_URL`에 주소를 제대로 넣었는지 확인하세요.")
    st.warning("2. 구글 시트 '웹에 게시' 설정이 '쉼표로 구분된 값(.csv)'인지 확인하세요.")
    st.stop() # 프로그램 중단

# -----------------------------------------------------------
# 3. 사이드바 입력
# -----------------------------------------------------------
with st.sidebar:
    st.header("📝 견적 조건 설정")
    equip_type = st.selectbox("설비 종류", ["바스켓 밀", "다이노 밀", "고속 믹서"])
    capacity = st.number_input("용량 (L)", value=500, step=100)
    is_explosion = st.checkbox("방폭 (Ex d)", value=True)
    
    st.divider()
    option_jacket = st.checkbox("자켓 (Heating/Cooling)")

    # 데이터 새로고침 버튼
    if st.button("🔄 최신 단가 가져오기"):
        st.cache_data.clear() # 캐시 삭제
        st.rerun()

    run_calc = st.button("💰 견적 산출하기", type="primary")

# -----------------------------------------------------------
# 4. 견적 계산 로직 (구글 시트 데이터 사용)
# -----------------------------------------------------------
def calculate_real_price(capa, explosion, jacket, db):
    bom_list = [] 
    total_price = 0
    
    # (1) 모터 선정 로직
    hp = "20HP" if capa <= 500 else "40HP"
    # 구글시트 품목명과 일치해야 함
    motor_name = f"메인모터(방폭)" if explosion else "메인모터" 
    
    try:
        # 구글 시트에서 조건에 맞는 행 찾기
        motor_row = db[ (db['품목'] == motor_name) & (db['규격'] == hp) ]
        if not motor_row.empty:
            price = motor_row.iloc[0]['단가']
            bom_list.append({"항목": f"모터 ({motor_name})", "규격": hp, "금액": price})
            total_price += price
        else:
             bom_list.append({"항목": f"모터 ({motor_name})", "규격": "단가표 없음", "금액": 0})
    except:
        pass

    # (2) 탱크(SUS) - 단가표의 'SUS304 Plate' 단가 사용
    try:
        # 품목명에 'SUS'가 포함된 첫 번째 자재의 단가를 가져옴
        sus_row = db[ db['품목'].str.contains("SUS") ].iloc[0]
        unit_price = sus_row['단가']
        weight = capa * 1.5 
        mat_cost = weight * unit_price
        bom_list.append({"항목": "제관 자재비 (Tank)", "규격": f"{weight}kg 예상", "금액": int(mat_cost)})
        total_price += mat_cost
    except:
        bom_list.append({"항목": "SUS 자재", "규격": "단가표 확인불가", "금액": 0})

    # (3) 옵션
    if option_jacket:
        bom_list.append({"항목": "자켓 가공비", "규격": "Double", "금액": 1500000})
        total_price += 1500000
    
    return total_price, pd.DataFrame(bom_list)

# -----------------------------------------------------------
# 5. 결과 화면
# -----------------------------------------------------------
if run_calc:
    final_price, df_bom = calculate_real_price(capacity, is_explosion, option_jacket, df_price)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🧾 상세 견적서")
        st.dataframe(df_bom, use_container_width=True)
        st.divider()
        st.metric("총 합계 금액", f"{int(final_price):,} 원")
        
    with col2:
        st.subheader("📋 현재 적용된 단가표 (Google Sheet)")
        st.caption("자재팀이 구글 시트를 수정하면 여기도 바뀝니다.")

        st.dataframe(df_price)
