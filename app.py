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

    # 브라우저 옵션 설정
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # [수정] 긴 User-Agent 문자열을 변수로 분리하여 안전하게 넣음
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20) # 대기 시간 20초

    results = []

    try:
        # [단계 1] 메인 페이지 접속 및 메뉴 이동
        status.write("⏳ K-STAT 접속 및 메뉴 이동 중...")
        driver.get("https://stat.kita.net/")
        
        # '국내통계' 클릭
        dom_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '국내통계')]")))
        dom_menu.click()
        time.sleep(1)

        # '품목 수출입' 클릭
        item_menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
        item_menu.click()
        time.sleep(3) 

        # [단계 2] 입력창 찾기
        status.write("⏳ '시작코드' 입력창 찾는 중...")
        
        input_found = False
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        
        # iframe 탐색 루프
        for i in range(len(iframes) + 1):
            try:
                if i > 0: 
                    driver.switch_to.default_content()
                    driver.switch_to.frame(iframes[i-1])
                
                # ID로 찾기 시도
                try:
                    input_box = driver.find_element(By.ID, "s_st_hsk_no")
                    input_found = True
                except:
                    # XPath로 찾기 시도
                    try:
                        input_box = driver.find_element(By.XPATH, "//td[contains(text(), '시작코드')]/following-sibling::td//input[@type='text']")
                        input_found = True
                    except:
                        pass
                
                if input_found:
                    break 
            except:
                continue

        if not input_found:
            raise Exception("❌ '시작코드' 입력창을 찾을 수 없습니다. (Iframe 탐색 실패)")

        # [단계 3] 데이터 입력 및 조회
        status.write(f"⏳ HSK {target_hsk} 입력 및 조회 클릭...")
        input_box.clear()
        input_box.send_keys(target_hsk)
        
        search_btn = driver.find_element(By.XPATH, "//*[contains(text(), '조회')]")
        search_btn.click()
        time.sleep(3)

        # [단계 4] 파란색 HSK 코드
