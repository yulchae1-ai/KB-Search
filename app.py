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
import io

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 엑셀 생성기", layout="centered")
st.title("🚢 K-STAT 복사/붙여넣기 엑셀 생성기")
st.info("TAB 이동 -> Ctrl+A/C (복사) -> 엑셀 A1, B1 셀에 붙여넣기 -> 다운로드")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("엑셀 생성 시작 🚀")

# --------------------------------------------------------------------------
# 2. 핵심 함수: Ctrl+A 후 '복사'한 효과 내기
# --------------------------------------------------------------------------
def simulate_copy(driver):
    """
    현재 위치에서 Ctrl+A를 누르고, 선택된 내용을 가져옵니다.
    (마치 Ctrl+C를 한 것과 동일한 데이터를 메모리에 저장)
    """
    try:
        elem = driver.switch_to.active_element
        
        # 1. Ctrl + A (전체 선택)
        elem.send_keys(Keys.CONTROL, 'a')
        time.sleep(1) # 선택이 확실히 되도록 1초 대기
        
        # 2. 데이터 가져오기 (클립보드 복사 시뮬레이션)
        # 우선순위: 1.선택된 텍스트 -> 2.입력값(Value) -> 3.보이는 텍스트
        
        # (A) 드래그된 텍스트 확인
        copied_data = driver.execute_script("return window.getSelection().toString();")
        
        # (B) 만약 드래그된 게 없으면, input의 value 확인
        if not copied_data:
            copied_data = elem.get_attribute("value")
            
        # (C) 그래도 없으면, 해당 요소의 텍스트 확인
        if not copied_data:
            copied_data = elem.text
            
        return copied_data.strip() if copied_data else "(데이터 없음)"
        
    except Exception as e:
        return f"복사 실패"

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

    # 엑셀에 들어갈 변수
    cell_a1 = ""
    cell_b1 = ""

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
            
            # 데이터 로딩 대기
            status.write("⏳ 데이터 렌더링 대기 (8초)...")
            time.sleep(8) 
            
            # -------------------------------------------------------
            # [4] 복사 & 붙여넣기 로직
            # -------------------------------------------------------
            
            # (A) TAB 10번 이동 -> Ctrl+A -> 복사
            status.write("👉 TAB 10회 이동 -> [Ctrl+C] 복사 시도...")
            actions = ActionChains(driver) 
            for _ in range(10):
                actions.send_keys(Keys.TAB)
            actions.perform()
            time.sleep(1) # 커서 안착 대기
            
            # ★ 복사하기
            cell_a1 = simulate_copy(driver)
            status.write(f"✅ 메모리에 복사된 값 (A1): {cell_a1}")
            
            # (B) TAB 5번 추가 이동 -> Ctrl+A -> 복사
            status.write("👉 TAB 5회 추가 이동 -> [Ctrl+C] 복사 시도...")
            actions = ActionChains(driver) 
            for _ in range(5):
                actions.send_keys(Keys.TAB)
            actions.perform()
            time.sleep(1) # 커서 안착 대기
            
            # ★ 복사하기
            cell_b1 = simulate_copy(driver)
            status.write(f"✅ 메모리에 복사된 값 (B1): {cell_b1}")
            
        except Exception as e:
            status.error(f"매크로 실패: {e}")
            return None, None

    except Exception as e:
        st.error(f"오류: {e}")
        st.image(driver.get_screenshot_as_png())
        return None, None
    finally:
        driver.quit()
    
    return cell_a1, cell_b1

# 실행 및 결과 출력
if submit:
    val1, val2 = run_crawler(hsk_code)
    
    if val1 is not None:
        st.success("🎉 복사 완료! 엑셀 생성을 시작합니다.")
        
        # 엑셀 생성 (A1, B1 셀에 값 넣기)
        # pandas DataFrame을 만들어서 엑셀로 변환 (Header 없이)
        df = pd.DataFrame([[val1, val2]]) # 1행 2열 데이터
        
        # 엑셀 파일 버퍼 생성
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
        # 다운로드 버튼 생성
        st.download_button(
            label="📥 엑셀 파일 다운로드 (result.xlsx)",
            data=buffer,
            file_name="result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.write("---")
        st.write("### 📋 미리보기")
        st.write(f"**A1 셀:** {val1}")
        st.write(f"**B1 셀:** {val2}")
