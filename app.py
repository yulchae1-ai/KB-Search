import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 무역통계 끝장판", layout="centered")
st.title("🚢 K-STAT 데이터 정밀 추출기")
st.info("HSK 입력 -> 매크로 이동 -> 연도/월별 데이터 '핀셋' 추출")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 데이터 '핀셋' 추출 함수 (핵심 로직)
# --------------------------------------------------------------------------
def extract_exact_data(driver, year, month_str):
    """
    특정 연도 탭을 클릭하고, 특정 월(month_str)이 있는 행을 찾아 수출금액을 가져옵니다.
    """
    try:
        # 1. 연도 탭 클릭 (2025년, 2026년 등)
        # 텍스트로 찾아서 강제 클릭
        xpath_year = f"//*[contains(text(), '{year}')]"
        try:
            year_tab = driver.find_element(By.XPATH, xpath_year)
            driver.execute_script("arguments[0].click();", year_tab)
            time.sleep(2) # 테이블 바뀌는 시간 대기
        except:
            return "연도 탭 없음"
        
        # 2. 테이블의 모든 행(tr)을 가져옴
        # K-Stat 팝업 내의 데이터 테이블 식별
        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        
        target_amount = "데이터 없음"
        
        # 3. 한 줄씩 검사
        for row in rows:
            text = row.text.strip()
            # 해당 월(예: "12월")이 이 줄에 있는가?
            if month_str in text:
                # 4. 데이터 추출 (컬럼 순서 기반)
                # 보통 구조: [체크박스] [년월] [수출금액] [수출증감률] ...
                cols = row.find_elements(By.TAG_NAME, "td")
                
                # 데이터가 있는 td들을 순서대로 검사
                for col in cols:
                    val = col.text.strip()
                    # 숫자가 포함되어 있고, 콤마(,)가 포함된 숫자를 찾음 (금액 특징)
                    # "12월" 글자랑 똑같은건 제외
                    if val and (val != month_str) and (any(char.isdigit() for char in val)):
                         # 수출 금액은 보통 콤마가 있거나 그냥 숫자임
                         target_amount = val
                         break # 금액 찾았으면 루프 종료
                break # 행 찾았으면 루프 종료
                
        return target_amount

    except Exception as e:
        return f"에러: {str(e)}"

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
        
        # 메뉴 이동 (JS 강제 클릭)
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

        # [2] Iframe 찾기
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

        # [3] 매크로 입력 (HSK 클릭 -> TAB 2 -> 입력 -> TAB 11 -> 엔터)
        status.write(f"⏳ 조회 매크로 실행 중...")
        
        try:
            hsk_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'HSK')]")))
            hsk_label.click()
            time.sleep(1) 
            
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(target_hsk)
            actions.perform()
            time.sleep(0.5)

            status.write("⏳ 조회 실행 (TAB 11회)...")
            for _ in range(11): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(5) 

            # [4] 상세 페이지 진입 매크로 (TAB 8 -> DOWN -> ENTER)
            status.write("⏳ 상세 페이지 진입 (TAB 8회)...")
            actions = ActionChains(driver) 
            for _ in range(8): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.DOWN)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
            status.write("✅ 상세 진입 명령 완료. 팝업 대기...")
            time.sleep(5)
            
        except Exception as e:
            status.error(f"매크로 실행 실패: {e}")
            return None

        # [5] 팝업 창 전환
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            status.write("✅ 팝업창 포착! 데이터 정밀 추출 시작...")
        else:
            status.warning("⚠️ 팝업창이 뜨지 않았습니다.")
            return None

        # [6] 데이터 정밀 추출 (여기가 핵심!)
        
        # 1. 2026년 1월 데이터
        status.write("👉 2026년 1월 데이터 찾는 중...")
        amt_2026 = extract_exact_data(driver, "2026", "1월")
        results.append({"연도": "2026", "월": "1월", "수출금액": amt_2026})
        
        # 2. 2025년 12월 데이터
        status.write("👉 2025년 12월 데이터 찾는 중...")
        amt_2025 = extract_exact_data(driver, "2025", "12월")
        results.append({"연도": "2025", "월": "12월", "수출금액": amt_2025})

    except Exception as e:
        st.error(f"오류 발생: {e}")
        st.image(driver.get_screenshot_as_png())
        return None
    finally:
        driver.quit()
    
    return pd.DataFrame(results)

# 실행 및 결과 출력
if submit:
    df_result = run_crawler(hsk_code)
    
    if df_result is not None:
        st.success("🎉 데이터 추출 성공!")
        
        # 스타일링된 표로 결과 보여주기
        st.write("### 📊 수집 결과")
        st.dataframe(df_result, use_container_width=True)
