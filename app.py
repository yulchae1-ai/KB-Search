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
st.set_page_config(page_title="K-STAT 심층 채굴기", layout="centered")
st.title("🚢 K-STAT 심층 데이터 채굴기")
st.info("TAB 이동 -> 현재 포커스된 요소의 '속살(HTML/Text/Value/Title)'을 전부 뒤집니다.")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("채굴 시작 🚀")

# --------------------------------------------------------------------------
# 2. 핵심 함수: 잡은 놈은 절대 놓치지 않는다 (Deep Extraction)
# --------------------------------------------------------------------------
def extract_deep_data(driver):
    """
    현재 포커스된 요소가 가지고 있는 모든 정보를 긁어옵니다.
    1. 텍스트 (innerText)
    2. 숨겨진 텍스트 (textContent)
    3. 입력값 (value)
    4. 툴팁 (title)
    5. 그것도 없으면 태그 이름이라도 반환 (디버깅용)
    """
    try:
        elem = driver.switch_to.active_element
        
        # [1] JavaScript로 텍스트 강제 추출 (가장 강력)
        # textContent는 숨겨진 텍스트나 자식 태그의 텍스트까지 모두 가져옵니다.
        text_content = driver.execute_script("return arguments[0].textContent;", elem)
        if text_content and text_content.strip():
            return text_content.strip()

        # [2] innerText 확인
        inner_text = driver.execute_script("return arguments[0].innerText;", elem)
        if inner_text and inner_text.strip():
            return inner_text.strip()

        # [3] Value 확인 (input 태그)
        val = elem.get_attribute("value")
        if val and val.strip():
            return val.strip()
            
        # [4] Title 속성 확인 (가끔 그리드 데이터가 여기 숨어있음)
        title = elem.get_attribute("title")
        if title and title.strip():
            return title.strip()
            
        # [5] 그래도 없으면... 현재 잡고 있는 태그가 뭔지라도 알려줘!
        tag_name = elem.tag_name
        html_snippet = elem.get_attribute("outerHTML")[:50] # 너무 기니까 앞부분만
        return f"(데이터 없음 - 태그: <{tag_name}>, HTML: {html_snippet}...)"

    except Exception as e:
        return f"에러 발생: {str(e)}"

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
            return None, None

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
            # [4] 데이터 심층 추출
            # -------------------------------------------------------
            
            # (A) TAB 10번 이동 -> 첫 번째 데이터
            status.write("👉 TAB 10회 이동 중...")
            actions = ActionChains(driver) 
            for _ in range(10):
                actions.send_keys(Keys.TAB)
            actions.perform()
            time.sleep(1)
            
            # ★ 심층 추출
            cell_a1 = extract_deep_data(driver)
            status.write(f"✅ 추출된 값 (A1): {cell_a1}")
            
            # (B) TAB 5번 추가 이동 -> 두 번째 데이터
            status.write("👉 TAB 5회 추가 이동 중...")
            actions = ActionChains(driver) 
            for _ in range(5):
                actions.send_keys(Keys.TAB)
            actions.perform()
            time.sleep(1)
            
            # ★ 심층 추출
            cell_b1 = extract_deep_data(driver)
            status.write(f"✅ 추출된 값 (B1): {cell_b1}")
            
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
        st.success("🎉 작업 완료! 엑셀 생성을 시작합니다.")
        
        # 엑셀 생성
        df = pd.DataFrame([[val1, val2]])
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, header=False, sheet_name='Sheet1')
            
        st.download_button(
            label="📥 엑셀 파일 다운로드 (result.xlsx)",
            data=buffer,
            file_name="result.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.write("---")
        st.write("### 🔍 디버깅 결과 (봇이 본 것)")
        st.code(f"A1 (TAB 10): {val1}\nB1 (TAB +5): {val2}")
