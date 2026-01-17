import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime, timedelta
import io

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="K-STAT 무역통계 조회", layout="centered")

st.title("🚢 K-STAT 수출입 데이터 조회")
st.info("HSK 코드를 입력하면 최근 2개월치 데이터를 가져옵니다.")

# 입력 폼
with st.form("search_form"):
    hsk_code = st.text_input("HSK 코드 (6~10단위)", value="847950")
    submit = st.form_submit_button("데이터 조회 시작 🚀")

# --- 2. 크롤링 로직 ---
if submit:
    status_area = st.empty()
    status_area.write("⏳ 브라우저를 실행하고 K-STAT에 접속 중입니다...")

    # 브라우저 옵션 설정 (서버 환경에 최적화)
    options = Options()
    options.add_argument("--headless")  # 화면 없이 실행
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # 중요: 로봇으로 인식되지 않게 가짜 유저 에이전트 설정
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.60 Safari/537.36")

    driver = webdriver.Chrome(options=options)

    try:
        # (1) K-Stat 품목별 수출입 페이지 접속
        # 이 URL이 통계 조회 메인 화면입니다.
        url = "https://stat.kita.net/stat/kts/pum/PumExpImpList.screen"
        driver.get(url)
        
        status_area.write("⏳ 사이트 접속 성공! 입력창을 찾는 중...")

        # (2) 입력창 대기 및 입력
        wait = WebDriverWait(driver, 15) # 최대 15초 대기
        
        # K-STAT 실제 ID: s_hsk_no (HSK 코드 입력창)
        input_box = wait.until(EC.presence_of_element_located((By.ID, "s_st_hsk_no")))
        input_box.clear()
        input_box.send_keys(hsk_code)
        
        # (3) 조회 버튼 클릭
        status_area.write("⏳ 조회 버튼 클릭 중...")
        # 조회 버튼 ID: btn_query 또는 텍스트로 찾기
        search_btn = driver.find_element(By.XPATH, "//button[contains(text(), '조회')]")
        search_btn.click()

        # (4) 데이터 로딩 대기 (로딩바가 사라질 때까지 혹은 테이블 뜰 때까지)
        status_area.write("⏳ 데이터를 불러오는 중입니다...")
        time.sleep(5) # 데이터 로딩 충분히 대기

        # (5) 데이터 추출 (HTML 파싱)
        html = driver.page_source
        
        # pandas로 테이블 읽기 (첫 번째 테이블이 보통 데이터 테이블임)
        dfs = pd.read_html(html)
        
        if len(dfs) > 1:
            # 보통 K-Stat은 상단 요약 테이블(0번)과 상세 데이터 테이블(1번)이 있음
            # 데이터 형태를 보고 적절한 것 선택 (여기서는 가장 데이터 많은 것 선택 시도)
            df = dfs[1] 
        else:
            df = dfs[0]

        # 데이터 정제 (원하는 컬럼만 남기거나 포맷팅)
        status_area.success("수집 성공!")
        
        # 화면에 표시
        st.write("### 📊 조회 결과")
        st.dataframe(df.head(10)) # 상위 10개만 미리보기

        # (6) 엑셀 다운로드
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            
        st.download_button(
            label="📥 엑셀 파일 다운로드",
            data=buffer,
            file_name=f"KSTAT_{hsk_code}_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"오류가 발생했습니다.")
        st.code(str(e)) # 자세한 에러 메시지 출력
        
        # 디버깅용: 스크린샷 찍어서 에러 원인 보기 (서버에는 파일로 저장됨)
        # driver.save_screenshot("error_screenshot.png") 
        
    finally:
        driver.quit()
