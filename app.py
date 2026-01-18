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
st.set_page_config(page_title="K-STAT 최종 해결", layout="centered")
st.title("🚢 K-STAT 데이터 수집기 (Parent Node)")
st.info("TAB 이동 -> 투명 Input 감지 시 -> 부모(Parent) 요소의 텍스트 강제 추출")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 핵심 함수: 투명 Input의 '부모'에게서 데이터 뺏어오기
# --------------------------------------------------------------------------
def extract_data_from_parent(driver):
    """
    현재 포커스가 'tmpinput'(빈 껍데기)에 있다면,
    그 부모 요소(TD/DIV)로 거슬러 올라가서 진짜 텍스트를 가져옵니다.
    """
    try:
        elem = driver.switch_to.active_element
        
        # 1. 우선 현재 요소에서 텍스트 시도
        text = elem.text
        value = elem.get_attribute("value")
        
        # 2. 만약 현재 요소가 비어있거나 'tmpinput'이라면 부모를 공략
        # (id에 'tmp'가 들어가거나 값이 비어있는 경우)
        elem_id = elem.get_attribute("id") or ""
        
        if (not text and not value) or "tmp" in elem_id:
            # ★ 핵심: 자바스크립트로 부모 요소(parentElement)의 텍스트를 가져옴
            # parentElement.innerText: 부모가 가진 눈에 보이는 텍스트
            # parentElement.textContent: 부모가 가진 모든 텍스트
            parent_text = driver.execute_script("""
                var el = arguments[0];
                var parent = el.parentElement;
                if (!parent) return "";
                return parent.innerText || parent.textContent;
            """, elem)
            
            if parent_text and parent_text.strip():
                return parent_text.strip()
        
        # 3. 부모도 없으면 기존 방식(Value/Text) 반환
        if value and value.strip(): return value.strip()
        if text and text.strip(): return text.strip()
        
        return "(데이터 없음)"

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
            # [4] 데이터 추출 (부모 요소 공략)
            # -------------------------------------------------------
            
            # (A) TAB 10번 이동 -> 첫 번째 데이터
            status.write("👉 TAB 10회 이동 중...")
            actions = ActionChains(driver) 
            for _ in range(10):
                actions.send_keys(Keys.TAB)
            actions.perform()
            time.sleep(1)
            
            # ★ 부모 요소에서 텍스트 뺏어오기
            cell_a1 = extract_data_from_parent(driver)
            status.write(f"✅ 추출 성공 (A1): {cell_a1}")
            
            # (B) TAB 5번 추가 이동 -> 두 번째 데이터
            status.write("👉 TAB 5회 추가 이동 중...")
            actions = ActionChains(driver) 
            for _ in range(5):
                actions.send_keys(Keys.TAB)
            actions.perform()
            time.sleep(1)
            
            # ★ 부모 요소에서 텍스트 뺏어오기
            cell_b1 = extract_data_from_parent(driver)
            status.write(f"✅ 추출 성공 (B1): {cell_b1}")
            
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
        st.write("### 🔍 최종 결과")
        st.write(f"**A1:** {val1}")
        st.write(f"**B1:** {val2}")
