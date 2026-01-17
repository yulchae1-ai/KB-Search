import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
from datetime import datetime
import io

# --- 1. 페이지 기본 설정 ---
st.set_page_config(page_title="K-STAT 데이터 수집기", layout="centered")
st.title("🚢 K-STAT 수출입 상세 데이터 조회")
st.info("K-Stat > 품목수출입 > 상세정보 페이지를 자동으로 탐색하여 데이터를 가져옵니다.")

# --- 2. 입력 UI ---
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드 (예: 847950)", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --- 3. 크롤링 함수 ---
def run_crawler(target_hsk):
    status = st.empty()
    status.write("⏳ 브라우저 초기화 중...")

    # 브라우저 옵션
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    # 봇 탐지 회피
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20) # 대기 시간 20초로 넉넉하게

    results = []

    try:
        # [단계 1] 메인 페이지 접속 및 메뉴 이동
        status.write("⏳ K-STAT 접속 및 메뉴 이동 중...")
        driver.get("https://stat.kita.net/")
        
        # '국내통계' 클릭
        dom_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '국내통계')]")))
        dom_menu.click()
        time.sleep(1)

        # '품목 수출입' 클릭 (또는 품목수출입)
        item_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
        item_menu.click()
        time.sleep(3) # 페이지 로딩 대기

        # [단계 2] 입력창 찾기 (가장 중요한 부분)
        status.write("⏳ '시작코드' 입력창 찾는 중...")
        
        # iframe 처리: 화면에 iframe이 있으면 하나씩 들어가보며 입력창을 찾음
        input_found = False
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        
        # 메인 프레임 포함, 모든 프레임 순회
        for i in range(len(iframes) + 1):
            try:
                if i > 0: # 0번은 메인, 1번부터 iframe 진입
                    driver.switch_to.default_content()
                    driver.switch_to.frame(iframes[i-1])
                
                # 전략 1: ID로 찾기 (s_st_hsk_no)
                try:
                    input_box = driver.find_element(By.ID, "s_st_hsk_no")
                    input_found = True
                except:
                    # 전략 2: '시작코드' 라벨 근처의 input 찾기 (XPath)
                    try:
                        input_box = driver.find_element(By.XPATH, "//td[contains(text(), '시작코드')]/following-sibling::td//input[@type='text']")
                        input_found = True
                    except:
                        pass
                
                if input_found:
                    break # 찾았으면 루프 종료
            except:
                continue

        if not input_found:
            raise Exception("❌ '시작코드' 입력창을 찾을 수 없습니다. (Iframe 탐색 실패)")

        # [단계 3] 데이터 입력 및 조회
        status.write(f"⏳ HSK {target_hsk} 입력 및 조회 클릭...")
        input_box.clear()
        input_box.send_keys(target_hsk)
        
        # 조회 버튼 클릭
        search_btn = driver.find_element(By.XPATH, "//*[contains(text(), '조회')]")
        search_btn.click()
        time.sleep(3)

        # [단계 4] 파란색 HSK 코드 링크 클릭 (상세 진입)
        status.write("⏳ 상세 정보로 진입합니다...")
        
        # 링크가 있는 프레임을 다시 맞춰줘야 할 수도 있음 (보통 같은 프레임)
        try:
            # 텍스트가 정확히 HSK코드인 링크(a 태그) 찾기
            link_xpath = f"//a[contains(text(), '{target_hsk}')]"
            detail_link = wait.until(EC.element_to_be_clickable((By.XPATH, link_xpath)))
            detail_link.click()
        except TimeoutException:
            # 혹시 링크가 바로 안 보이면, 결과 프레임이 따로 있는지 확인 필요하나, 일단 에러 처리
            raise Exception(f"결과 목록에서 {target_hsk} 링크를 클릭할 수 없습니다. 조회 결과가 없나요?")

        time.sleep(5) # 상세 팝업/페이지 로딩 대기

        # 윈도우가 새로 뜨는지 확인
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            status.write("⏳ 팝업창으로 전환되었습니다.")

        # [단계 5] 연도별 데이터 추출 (당월, 전월)
        # 목표: 2026년 1월, 2025년 12월
        # 상세 페이지는 보통 연도 탭이나 드롭다운이 있음.
        # 혹은 그냥 최근 데이터가 표에 나와있을 수 있음.
        
        target_dates = [
            {"year": "2026", "month": "01", "label": "당월"},
            {"year": "2025", "month": "12", "label": "전월"}
        ]

        status.write("⏳ 상세 데이터 테이블 스캔 중...")

        # 현재 페이지의 모든 텍스트를 일단 가져와서 파싱 시도
        # 연도 탭이 있다면 클릭하는 로직 추가
        
        for target in target_dates:
            target_year = target["year"]
            target_month = target["month"] # 01, 12 등
            
            # 연도 선택 시도 (만약 연도 버튼이 있다면)
            try:
                # '2026' 이라는 텍스트를 가진 버튼/링크가 있다면 클릭
                year_btn = driver.find_element(By.XPATH, f"//*[contains(text(), '{target_year}') and (self::a or self::button or self::span)]")
                year_btn.click()
                time.sleep(2) # 데이터 로딩
            except:
                pass # 버튼 없으면 이미 표에 있겠거니 하고 진행

            # 테이블 읽기
            html = driver.page_source
            dfs = pd.read_html(html)
            
            found_amount = "데이터 없음"
            
            # 모든 테이블을 뒤져서 해당 날짜(예: 2026.01, 01월 등) 찾기
            for df in dfs:
                # 데이터프레임을 문자열로 변환해서 검색
                # K-Stat 상세표는 보통 [기간] [수출금액] ... 형식
                # 월 컬럼이 '01월', '1월', '2026.01' 등으로 다양할 수 있음
                
                # 행 단위로 순회
                for index, row in df.iterrows():
                    row_str = " ".join(row.astype(str
