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
st.set_page_config(page_title="K-STAT 강력 수집기", layout="centered")
st.title("🚢 K-STAT 데이터 수집기 (Robust Wait)")
st.info("TAB 이동 후, Text / Value / InnerText 모든 속성을 뒤져서 데이터를 찾아냅니다.")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 핵심 함수: 모든 속성 뒤져서 데이터 나오면 리턴
# --------------------------------------------------------------------------
def wait_and_extract_any_data(driver, timeout=10):
    """
    현재 포커스된 요소(active_element)에서
    Text, Value, innerText 중 하나라도 데이터가 있으면 가져옵니다.
    """
    end_time = time.time() + timeout
    
    while time.time() < end_time:
        try:
            elem = driver.switch_to.active_element
            
            # 1. 일반 텍스트 확인
            txt = elem.text.strip()
            if txt: return txt
            
            # 2. 입력값(Value) 확인 (input 태그일 경우)
            val = elem.get_attribute("value")
            if val and val.strip(): return val.strip()
            
            # 3. 숨겨진 텍스트(innerText) 확인 (div/span 등)
            inner = elem.get_attribute("innerText")
            if inner and inner.strip(): return inner.strip()
            
            # 4. JavaScript로 강제 추출 (최후의 수단)
            js_txt = driver.execute_script("return arguments[0].textContent", elem)
            if js_txt and js_txt.strip(): return js_txt.strip()
            
            # 데이터 없으면 0.5초 대기
            time.sleep(0.5)
            
        except:
            time.sleep(0.5)
            
    return "(데이터 없음)"

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

        # [3] 조회 매크로 실행
        status.write(f"⏳ HSK {target_hsk} 조회 중...")
        
        try:
            # HSK 클릭
            hsk_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'HSK')]")))
            hsk_label.click()
            time.sleep(1) 
            
            # 입력 (TAB 2번 -> 입력)
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(target_hsk)
            actions.perform()
            time.sleep(0.5)

            # 조회 (TAB 11번 -> 엔터)
            status.write("⏳ 조회 버튼 타격 (TAB 11회)...")
            for _ in range(11): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
            # ★ 동적 로딩 대기
            status.write("⏳ 데이터 렌더링 대기 (8초)...")
            time.sleep(8) 
            
            # -------------------------------------------------------
            # [4] 데이터 추출 (TAB 이동 + 모든 속성 검사)
            # -------------------------------------------------------
            
            # (A) TAB 10번 이동 -> 첫 번째 데이터
            status.write("👉 TAB 10회 이동 중...")
            actions = ActionChains(driver) 
            for _ in range(10):
                actions.send_keys(Keys.TAB)
            actions.perform()
            time.sleep(1) # 커서 안착 대기
            
            # ★ 핵심: 텍스트든 밸류든 뭐든 가져와!
            data_1 = wait_and_extract_any_data(driver)
            status.write(f"✅ 첫 번째 데이터: {data_1}")
            
            # (B) TAB 5번 추가 이동 -> 두 번째 데이터
            status.write("👉 TAB 5회 추가 이동 중...")
            actions = ActionChains(driver) 
            for _ in range(5):
                actions.send_keys(Keys.TAB)
            actions.perform()
            time.sleep(1) # 커서 안착 대기
            
            # ★ 핵심: 텍스트든 밸류든 뭐든 가져와!
            data_2 = wait_and_extract_any_data(driver)
            status.write(f"✅ 두 번째 데이터: {data_2}")
            
            # 결과 저장
            results.append({
                "구분": "첫 번째 데이터 (TAB 10)",
                "값": data_1
            })
            results.append({
                "구분": "두 번째 데이터 (+TAB 5)",
                "값": data_2
            })
            
        except Exception as e:
            status.error(f"매크로 실패: {e}")
            return None

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
        st.success("🎉 동적 데이터 수집 완료!")
        st.write("### 📊 수집 결과")
        st.dataframe(df_result, use_container_width=True)
