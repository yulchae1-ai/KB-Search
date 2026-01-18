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
st.title("🚢 K-STAT 데이터 핀셋 추출기")
st.info("HSK 입력 -> 매크로 이동 -> '12월' 옆에 있는 숫자 바로 가져오기")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 핀셋 추출 함수 (핵심: 글자 옆에 있는 칸 찾기)
# --------------------------------------------------------------------------
def extract_neighbor_data(driver, year, month_text):
    """
    1. '2025년'을 클릭해서 펼친다.
    2. '12월' 글자가 보이면, 바로 옆(다음) 칸에 있는 데이터를 가져온다.
    """
    try:
        # [1] 연도 클릭 (2025년 등)
        # 이미 펼쳐져 있을 수도 있으니 try-except로 시도
        try:
            xpath_year = f"//*[contains(text(), '{year}년')]"
            year_elem = driver.find_element(By.XPATH, xpath_year)
            driver.execute_script("arguments[0].click();", year_elem)
            time.sleep(2) # 데이터 로딩 대기
        except:
            pass # 못 찾으면 이미 펼쳐져 있거나 데이터가 없는 것

        # [2] '12월' 옆집 데이터 찾기 (XPath의 following-sibling 기능)
        # 해석: 텍스트가 '12월'인 td 태그를 찾고 -> 그 뒤에 오는 첫번째 td 태그를 가져와라.
        xpath_target = f"//td[contains(text(), '{month_text}')]/following-sibling::td[1]"
        
        # 화면에 보이는 요소가 나올 때까지 대기
        wait = WebDriverWait(driver, 5)
        target_elem = wait.until(EC.visibility_of_element_located((By.XPATH, xpath_target)))
        
        value = target_elem.text.strip()
        
        if value:
            return value
        else:
            return "빈 값"

    except Exception as e:
        return f"찾지 못함 ({month_text})"

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

        # [3] 매크로 실행 (HSK -> TAB... -> 조회 -> TAB... -> 상세)
        status.write(f"⏳ 매크로 실행 중...")
        
        try:
            hsk_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'HSK')]")))
            hsk_label.click()
            time.sleep(1) 
            
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(target_hsk)
            actions.perform()
            time.sleep(0.5)

            status.write("⏳ 조회 (TAB 11회)...")
            for _ in range(11): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(5) 

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
            status.write("✅ 팝업창에서 데이터 핀셋 추출 시작!")
        else:
            status.warning("⚠️ 팝업창 없음")
            return None

        # [5] 데이터 정밀 추출 (옆집 데이터 가져오기)
        
        # 1. 2026년 1월
        status.write("👉 2026년 1월 데이터 찾는 중...")
        val_2026 = extract_neighbor_data(driver, "2026", "1월")
        results.append({"연도": "2026", "월": "1월", "수출금액": val_2026})
        
        # 2. 2025년 12월
        status.write("👉 2025년 12월 데이터 찾는 중...")
        val_2025 = extract_neighbor_data(driver, "2025", "12월")
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
        st.success("🎉 추출 성공!")
        st.write("### 📊 결과 확인")
        st.dataframe(df_result, use_container_width=True)
