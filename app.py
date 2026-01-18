import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup 
import time

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 정밀 수집기", layout="centered")
st.title("🚢 K-STAT 정밀 수집기 (Source Parsing)")
st.info("블로그 방식 적용: HTML 소스를 직접 가져와서 표(Table)를 정밀 분해합니다.")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 핵심 함수: BeautifulSoup으로 표 뜯어보기
# --------------------------------------------------------------------------
def parse_table_manually(driver, year, month_keyword):
    """
    1. 현재 화면의 소스코드(HTML)를 통째로 가져온다.
    2. BeautifulSoup으로 표(table) 태그를 찾는다.
    3. 행(tr)을 하나씩 돌면서 '월'과 '수출금액' 위치를 찾는다.
    """
    try:
        # [1] 연도 클릭 (데이터 펼치기)
        # 이미 펼쳐져 있을 수도 있으니 try-except로 가볍게 처리
        try:
            xpath_year = f"//*[contains(text(), '{year}')]"
            year_elem = driver.find_element(By.XPATH, xpath_year)
            driver.execute_script("arguments[0].click();", year_elem)
            time.sleep(2) # 데이터 로딩 대기
        except:
            pass # 이미 펼쳐져 있거나 해당 연도가 없을 수 있음

        # [2] 소스코드 가져오기 (가장 확실한 방법)
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')

        # [3] 데이터가 있는 테이블 찾기
        # K-STAT 팝업에는 보통 데이터용 테이블이 하나 크게 있음
        # 모든 행(tr)을 가져와서 검사
        rows = soup.find_all('tr')
        
        target_amount = "데이터 없음"
        
        for row in rows:
            # 각 행의 텍스트를 가져옴 (공백 제거)
            row_text = row.get_text(strip=True)
            
            # 해당 '월'(예: 12월)이 포함된 행인지 확인
            if month_keyword in row_text:
                # 4. 해당 행의 칸(td)들을 모두 가져옴
                cols = row.find_all('td')
                
                # 칸이 여러개여야 데이터 행임 (제목 행 제외)
                if len(cols) > 1:
                    # 보통 순서: [체크박스] [년월] [수출금액] [수출증감률] ...
                    # 수출금액은 '수출' 섹션의 첫 번째 숫자 컬럼임.
                    # 우리는 "오른쪽에서부터 찾거나" "숫자 패턴"으로 찾음
                    
                    for col in cols:
                        text = col.get_text(strip=True)
                        # 콤마(,)가 포함된 숫자라면 수출금액일 확률 99%
                        # "12월"이라는 글자가 아니면서, 숫자가 포함된 것
                        if text and (text != month_keyword) and any(c.isdigit() for c in text):
                            # 불필요한 공백 제거
                            clean_text = text.replace(',', '').strip()
                            # 진짜 숫자인지 확인
                            if clean_text.isdigit():
                                return text # 원본 텍스트(콤마 포함) 반환
                                
        return target_amount

    except Exception as e:
        return f"파싱 에러: {str(e)}"

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
    wait = WebDriverWait(driver, 15)
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

        # [3] 조회 매크로 실행
        status.write(f"⏳ 조회 중 ({target_hsk})...")
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
            for _ in range(11): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
            status.write("⏳ 데이터 로딩 대기 (6초)...")
            time.sleep(6) 
            
            # 상세 팝업 진입 (TAB 8 -> DOWN -> ENTER)
            status.write("⏳ 상세 페이지 진입...")
            actions = ActionChains(driver) 
            for _ in range(8): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.DOWN)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(5)

        except Exception as e:
            status.error(f"매크로 실패: {e}")
            return None

        # [4] 팝업 창 전환
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            status.write("✅ 팝업창 포착! 소스코드 정밀 분석 시작...")
        else:
            status.warning("⚠️ 팝업창 없음")
            return None

        # -------------------------------------------------------
        # [5] 데이터 추출 (블로그 방식: BeautifulSoup 파싱)
        # -------------------------------------------------------
        
        # (A) 2026년 1월
        status.write("👉 2026년 데이터 분석 중...")
        val_2026 = parse_table_manually(driver, "2026", "1월")
        results.append({"연도": "2026", "월": "1월", "수출금액": val_2026})
        
        # (B) 2025년 12월
        status.write("👉 2025년 데이터 분석 중...")
        val_2025 = parse_table_manually(driver, "2025", "12월")
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
