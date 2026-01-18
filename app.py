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
from datetime import datetime

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 무역통계 수집기", layout="centered")
st.title("🚢 K-STAT 키보드 정밀 타격")
st.info("HSK 입력 -> 키보드 화살표 이동(DOWN/RIGHT) -> 데이터 낚아채기")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 키보드 네비게이션 함수 (핵심: DOWN N번 -> RIGHT 1번)
# --------------------------------------------------------------------------
def get_data_by_arrow_keys(driver, year, month_int):
    """
    1. 해당 연도(year) 텍스트를 클릭 (트리 펼치기 & 포커스 잡기)
    2. 월 숫자만큼 DOWN 키 입력 (1월=1번, 12월=12번)
    3. RIGHT 키 1번 입력 (수출금액 칸으로 이동)
    4. 현재 포커스된 요소의 텍스트 추출
    """
    try:
        # [1] 연도 클릭 (포커스 시작점)
        try:
            xpath_year = f"//*[contains(text(), '{year}년')]"
            year_elem = driver.find_element(By.XPATH, xpath_year)
            # 확실하게 클릭해서 포커스를 둡니다
            driver.execute_script("arguments[0].click();", year_elem)
            time.sleep(1) # 펼쳐지는 시간 대기
        except:
            return "연도 없음"

        # [2] 화살표 이동 매크로
        actions = ActionChains(driver)
        
        # (A) DOWN 키: 월 숫자만큼 반복
        # 예: 1월 -> 1번, 12월 -> 12번
        for _ in range(month_int):
            actions.send_keys(Keys.DOWN)
        
        # (B) RIGHT 키: 1번 (금액 칸으로 이동)
        actions.send_keys(Keys.RIGHT)
        
        # 액션 실행
        actions.perform()
        time.sleep(0.5) # 커서 이동 대기

        # [3] 현재 포커스 잡힌 데이터 가져오기 (핵심!)
        # switch_to.active_element는 현재 커서가 깜빡이는 곳의 정보를 가져옵니다.
        active_element = driver.switch_to.active_element
        result_text = active_element.text.strip()

        if result_text:
            return result_text
        else:
            return "빈 값"

    except Exception as e:
        return f"에러: {str(e)}"

# --------------------------------------------------------------------------
# 3. 메인 크롤링 함수
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

        # [3] 초기 매크로 (HSK 조회)
        status.write(f"⏳ 조회 매크로 실행 중...")
        try:
            hsk_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'HSK')]")))
            hsk_label.click()
            time.sleep(1) 
            
            # HSK 입력
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(target_hsk)
            actions.perform()
            time.sleep(0.5)

            # 조회 (TAB 11 -> ENTER)
            status.write("⏳ 조회 (TAB 11회)...")
            for _ in range(11): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(5) 

            # 상세 진입 (TAB 8 -> DOWN -> ENTER)
            status.write("⏳ 상세 진입 (TAB 8회)...")
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
            status.write("✅ 팝업창에서 키보드 정밀 타격 시작!")
        else:
            status.warning("⚠️ 팝업창 없음")
            return None

        # [5] 화살표 이동으로 데이터 추출 (사용자 요청 로직)
        
        now = datetime.now()
        # 현재: 2026-01 (예시)
        cur_year = now.year
        cur_month = now.month
        
        # 전월 계산
        if cur_month == 1:
            prev_year = cur_year - 1
            prev_month = 12
        else:
            prev_year = cur_year
            prev_month = cur_month - 1

        # 1. 당월 데이터 (예: 2026년 1월 -> Click 2026, DOWN 1, RIGHT 1)
        status.write(f"👉 {cur_year}년 {cur_month}월 데이터 위치로 이동 중...")
        val_curr = get_data_by_arrow_keys(driver, cur_year, cur_month)
        results.append({"연도": str(cur_year), "월": f"{cur_month}월", "수출금액": val_curr})
        
        # 2. 전월 데이터 (예: 2025년 12월 -> Click 2025, DOWN 12, RIGHT 1)
        status.write(f"👉 {prev_year}년 {prev_month}월 데이터 위치로 이동 중...")
        val_prev = get_data_by_arrow_keys(driver, prev_year, prev_month)
        results.append({"연도": str(prev_year), "월": f"{prev_month}월", "수출금액": val_prev})

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
        st.success("🎉 추출 성공!")
        st.write("### 📊 키보드 추출 결과")
        st.dataframe(df_result, use_container_width=True)
