import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup  # ★ 핵심 도구: 소스코드 해부기
import time

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 데이터 정밀 분석기", layout="centered")
st.title("🚢 K-STAT 데이터 정밀 분석기 (BS4)")
st.info("화면 동작(키보드) 대신, 페이지 소스(HTML)를 직접 분석하여 데이터를 추출합니다.")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 핵심 함수: BeautifulSoup을 이용한 데이터 정밀 타격
# --------------------------------------------------------------------------
def parse_data_from_html(page_source, year, month_keyword):
    """
    브라우저의 현재 화면(HTML)을 통째로 가져와서
    BeautifulSoup으로 '연도'와 '월'에 맞는 숫자를 찾아냅니다.
    """
    soup = BeautifulSoup(page_source, 'html.parser')
    
    # 1. K-STAT의 데이터 테이블 찾기 (보통 gridBody 등으로 되어 있음)
    # 테이블 행(tr)을 모두 가져옵니다.
    rows = soup.find_all('tr')
    
    target_amount = "찾지 못함"
    
    for row in rows:
        text = row.get_text(strip=True)
        
        # 2. 해당 '월'(예: 12월)이 포함된 행인지 확인
        if month_keyword in text:
            # 3. 그 행의 모든 칸(td)을 가져옴
            cols = row.find_all('td')
            
            # 4. 칸을 순회하면서 '수출금액' 패턴(숫자와 콤마)을 찾음
            for col in cols:
                val = col.get_text(strip=True)
                
                # 조건: "12월" 글자가 아니고, 숫자와 콤마로만 구성된 데이터
                # (수출금액은 보통 256,598 처럼 생겼으므로)
                if val and val != month_keyword:
                    # 콤마 제거 후 숫자인지 확인
                    clean_val = val.replace(',', '').replace('.', '')
                    if clean_val.isdigit():
                        return val # 찾았다! (256,598)
                        
    return target_amount

# --------------------------------------------------------------------------
# 3. 크롤링 메인 함수
# --------------------------------------------------------------------------
def run_crawler(target_hsk):
    status = st.empty()
    status.write("⏳ 브라우저 초기화 중...")

    # 옵션 설정
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={ua}")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    actions = ActionChains(driver)

    results = []

    try:
        # [1] 접속 및 메뉴 이동
        status.write("⏳ K-STAT 접속...")
        driver.get("https://stat.kita.net/")
        time.sleep(2)
        
        # 메뉴 이동
        try:
            btn1 = driver.find_element(By.XPATH, "//*[contains(text(), '국내통계')]")
            driver.execute_script("arguments[0].click();", btn1)
            time.sleep(1)
            btn2 = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
            driver.execute_script("arguments[0].click();", btn2)
            time.sleep(3)
        except:
            status.error("메뉴 이동 실패")
            return None

        # [2] Iframe 진입
        status.write("⏳ 입력 화면 진입...")
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_frame = False
        for i in range(len(iframes)):
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(iframes[i])
                if len(driver.find_elements(By.XPATH, "//*[contains(text(), 'HSK')]")) > 0:
                    found_frame = True
                    break 
            except:
                continue
        if not found_frame: driver.switch_to.default_content()

        # [3] 조회 (매크로 사용)
        status.write(f"⏳ 조회 실행 중...")
        try:
            hsk_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'HSK')]")))
            hsk_label.click()
            time.sleep(1) 
            
            # 입력
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(target_hsk)
            actions.perform()
            time.sleep(0.5)

            # 조회 (TAB 11 -> ENTER)
            status.write("⏳ 조회 버튼 타격 (TAB 11회)...")
            for _ in range(11): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
            # ★ 데이터 로딩 대기 (충분히)
            status.write("⏳ 데이터 집계 중 (8초 대기)...")
            time.sleep(8) 
            
            # 상세 페이지 진입 (TAB 8 -> DOWN -> ENTER)
            status.write("⏳ 상세 팝업 진입 시도...")
            actions = ActionChains(driver) 
            for _ in range(8): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.DOWN)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(5)

        except Exception as e:
            status.error(f"조회 실패: {e}")
            return None

        # [4] 팝업 창 전환
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            status.write("✅ 팝업창 포착! 소스코드 분석 시작...")
        else:
            status.warning("⚠️ 팝업창 없음")
            return None

        # -------------------------------------------------------
        # [5] 데이터 추출 (BeautifulSoup 사용)
        # -------------------------------------------------------
        
        # 전략: 연도를 클릭해서 펼쳐야 HTML 안에 '월' 데이터가 생김.
        # 따라서 2026년 클릭 -> 소스 가져오기 -> 2025년 클릭 -> 소스 가져오기
        
        # (A) 2026년 1월 데이터
        status.write("👉 2026년 데이터 추출 중...")
        try:
            # 2026년 클릭 (데이터 펼치기)
            year_btn = driver.find_element(By.XPATH, "//*[contains(text(), '2026년')]")
            driver.execute_script("arguments[0].click();", year_btn)
            time.sleep(2) # 펼쳐질 시간
        except:
            pass # 2026년이 없을 수도 있음
            
        # ★ 현재 화면의 HTML 소스를 통째로 긁어옴
        html_2026 = driver.page_source
        val_2026 = parse_data_from_html(html_2026, "2026", "1월")
        results.append({"연도": "2026", "월": "1월", "수출금액": val_2026})
        
        # (B) 2025년 12월 데이터
        status.write("👉 2025년 데이터 추출 중...")
        try:
            # 2025년 클릭 (데이터 펼치기)
            year_btn = driver.find_element(By.XPATH, "//*[contains(text(), '2025년')]")
            driver.execute_script("arguments[0].click();", year_btn)
            time.sleep(2)
        except:
            pass
            
        # ★ 현재 화면의 HTML 소스를 통째로 긁어옴
        html_2025 = driver.page_source
        val_2025 = parse_data_from_html(html_2025, "2025", "12월")
        results.append({"연도": "2025", "월": "12월", "수출금액": val_2025})

    except Exception as e:
        st.error(f"오류: {e}")
        st.image(driver.get_screenshot_as_png())
        return None
    finally:
        driver.quit()
    
    return pd.DataFrame(results)

# 실행 및 결과 출력
if submit:
    df_result = run_crawler(hsk_code)
    
    if df_result is not None:
        st.success("🎉 분석 완료!")
        st.write("### 📊 수집 결과")
        st.dataframe(df_result, use_container_width=True)
