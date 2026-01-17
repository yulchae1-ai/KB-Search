import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime, timedelta
import io
import time

# ---------------------------------------------------------
# 1. 크롤링 함수 (백엔드 로직)
# ---------------------------------------------------------
def crawl_kstat(hsk_code, unit_level):
    # --- 날짜 계산 로직 ---
    # 현재 시점 (예: 2026-01)
    now = datetime.now()
    current_year = now.year
    current_month = now.month
    
    # 이전 달 계산 (예: 2025-12)
    first_day_of_this_month = now.replace(day=1)
    last_month_date = first_day_of_this_month - timedelta(days=1)
    prev_year = last_month_date.year
    prev_month = last_month_date.month

    # K-Stat 입력용 날짜 문자열 포맷팅 (사이트 양식에 맞춰야 함, 예: 202601)
    str_current_ym = f"{current_year}{current_month:02d}"
    str_prev_ym = f"{prev_year}{prev_month:02d}"

    st.write(f"📅 조회 기준: {str_current_ym} (당월) ~ {str_prev_ym} (전월)")

    # --- Selenium 설정 (서버용 Headless) ---
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 화면 없이 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # 로컬 테스트가 아닌 서버 배포시 드라이버 설정이 까다로울 수 있어 webdriver-manager 사용 권장
    # 여기서는 기본 구조로 작성
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # 1. 사이트 접속 (품목별 수출입 화면 URL로 직접 이동 권장)
        # K-Stat URL은 예시입니다. 실제 접속하려는 정확한 '품목수출입' 탭의 URL을 넣으세요.
        url = "https://stat.kita.net/stat/kts/pum/PumCodeList.screen" 
        driver.get(url)
        time.sleep(3) # 페이지 로딩 대기

        # 2. HSK 코드 입력
        # 실제 사이트에서 F12를 눌러 입력창의 ID를 확인해야 합니다. (예: txt_hsk_no)
        # 아래는 가상의 ID입니다. Cursor에게 "이 사이트의 입력창 ID 찾아줘"라고 물어보며 수정하세요.
        input_hsk = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "search_hsk_code_id"))
        )
        input_hsk.clear()
        input_hsk.send_keys(hsk_code)

        # 3. 단위 선택 및 날짜 설정 (필요시 Select box 조작 로직 추가)
        # ... (생략: 사이트마다 방식이 달라 직접 클릭 혹은 JS 실행 필요)
        
        # 4. 조회 버튼 클릭
        search_btn = driver.find_element(By.ID, "btn_search_id")
        search_btn.click()
        
        # 5. 결과 기다리기 & 데이터 추출
        time.sleep(5) # 데이터 로딩 대기
        
        # 테이블 데이터 가져오기 (BeautifulSoup을 섞어 쓰면 더 편함)
        # 여기서는 간단히 당월/전월 수출액을 찾는다고 가정
        
        # [가상 로직] 페이지 소스에서 데이터 추출
        # 실제로는 driver.page_source를 파싱해서 정확한 값을 찾아야 합니다.
        scraped_data = [
            {"구분": "당월", "기간": str_current_ym, "수출금액": "1,200,000"}, # 예시 데이터
            {"구분": "전월", "기간": str_prev_ym, "수출금액": "1,150,000"}    # 예시 데이터
        ]
        
        return pd.DataFrame(scraped_data)

    except Exception as e:
        st.error(f"크롤링 중 에러 발생: {e}")
        return pd.DataFrame()
    finally:
        driver.quit()

# ---------------------------------------------------------
# 2. 웹사이트 화면 구성 (Frontend)
# ---------------------------------------------------------
st.set_page_config(page_title="무역 통계 수집기", layout="centered")

st.title("🚢 K-Stat 데이터 자동 수집기")
st.markdown("입력한 HSK 코드를 기반으로 **당월/전월 수출금액**을 가져옵니다.")

# 입력 폼 생성
with st.form("input_form"):
    col1, col2 = st.columns(2)
    with col1:
        item_name = st.text_input("품목명 (참고용)", value="산업용 로봇")
        hsk_code = st.text_input("HSK 코드", value="847950")
    with col2:
        unit_level = st.selectbox("HSK 단위", ["2단위", "4단위", "6단위", "10단위"], index=2)
        
    submit_btn = st.form_submit_button("🔍 데이터 수집 시작")

# 버튼 클릭 시 동작
if submit_btn:
    with st.spinner(f"'{item_name}({hsk_code})' 데이터를 K-Stat에서 수집 중입니다..."):
        # 크롤링 실행
        df_result = crawl_kstat(hsk_code, unit_level)
        
        if not df_result.empty:
            st.success("수집 완료!")
            
            # 결과 표 보여주기
            st.dataframe(df_result)
            
            # 엑셀 다운로드 준비
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_result.to_excel(writer, index=False)
            output.seek(0)
            
            st.download_button(
                label="📥 엑셀 파일 다운로드",
                data=output,
                file_name=f"TradeData_{hsk_code}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("데이터를 찾지 못했습니다. HSK 코드나 사이트 상태를 확인해주세요.")