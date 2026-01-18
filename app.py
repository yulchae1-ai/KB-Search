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
st.set_page_config(page_title="K-STAT 정밀 타격", layout="centered")
st.title("🚢 K-STAT 데이터 수집기 (Direct XPATH)")
st.info("투명 입력창(tmpinput)을 무시하고, 실제 데이터가 있는 셀(TD)을 직접 찾아냅니다.")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 핵심 함수: XPATH로 진짜 데이터 셀 찾기
# --------------------------------------------------------------------------
def find_data_row_and_extract(driver, year, month_text):
    """
    1. '2025년'을 찾아 클릭(펼치기)
    2. '12월'이 포함된 행(TR)을 찾기
    3. 그 행에서 '수출금액'에 해당하는 숫자 데이터를 추출
    """
    try:
        # [1] 연도 클릭 (데이터 펼치기)
        try:
            xpath_year = f"//*[contains(text(), '{year}년')]"
            # 2025년이 보이기를 기다렸다가 클릭
            year_elem = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, xpath_year))
            )
            driver.execute_script("arguments[0].click();", year_elem)
            time.sleep(2) # 데이터 로딩 대기
        except:
            return "(연도 없음)"

        # [2] '12월' 텍스트가 있는 셀(TD) 찾기
        # 그리드 구조상 '12월' 텍스트는 <span>12월</span> 형태일 수 있음
        try:
            xpath_month = f"//td[contains(., '{month_text}')]"
            month_elem = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, xpath_month))
            )
            
            # [3] '12월' 셀의 형제들(Sibling) 중에서 '수출금액' 찾기
            # '12월' 셀 바로 다음에 오는 셀들이 데이터임.
            # 보통 순서: [월] [수출금액] [수출증감률] [수출중량] ...
            # 따라서 '12월' 셀의 '다음 다음' 혹은 '바로 다음' 셀을 확인해야 함.
            
            # 해당 행(tr)의 모든 td를 가져옴
            parent_tr = month_elem.find_element(By.XPATH, "./ancestor::tr")
            tds = parent_tr.find_elements(By.TAG_NAME, "td")
            
            found_data = ""
            
            # td들을 순회하며 '숫자와 콤마'로 된 금액 데이터를 찾음
            for td in tds:
                text = td.text.strip() # text가 안되면 innerText 사용
                if not text:
                    text = td.get_attribute("innerText").strip()
                
                # 조건: "12월" 텍스트가 아니고, 숫자와 콤마(,)가 포함된 데이터
                # 예: "256,598"
                if text and (month_text not in text) and any(c.isdigit() for c in text):
                    # 수출 금액은 보통 콤마가 있음. 
                    # 확실하게 하기 위해 콤마 제거 후 숫자인지 체크
                    clean_val = text.replace(',', '').replace('.', '')
                    if clean_val.isdigit():
                        found_data = text
                        break # 첫 번째 나오는 숫자가 보통 '수출금액' (가장 왼쪽)
            
            if found_data:
                return found_data
            else:
                return "(데이터 패턴 불일치)"

        except Exception as e:
            return f"(월 데이터 못 찾음: {e})"

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
            
            # 상세 페이지 진입 (TAB 8 -> DOWN -> ENTER)
            status.write("⏳ 상세 페이지 진입 중...")
            actions = ActionChains(driver) 
            for _ in range(8): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.DOWN)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(5)
            
            # 팝업 창 전환
            if len(driver.window_handles) > 1:
                driver.switch_to.window(driver.window_handles[-1])
            
            # -------------------------------------------------------
            # [4] 데이터 정밀 추출 (Active Element 사용 안 함!)
            # -------------------------------------------------------
            
            # (A) 2026년 1월 데이터
            status.write("👉 2026년 1월 데이터 찾는 중...")
            cell_a1 = find_data_row_and_extract(driver, "2026", "1월")
            status.write(f"✅ 결과: {cell_a1}")
            
            # (B) 2025년 12월 데이터
            status.write("👉 2025년 12월 데이터 찾는 중...")
            cell_b1 = find_data_row_and_extract(driver, "2025", "12월")
            status.write(f"✅ 결과: {cell_b1}")
            
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
    
    if val1 or val2:
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
        st.write(f"**2026-01:** {val1}")
        st.write(f"**2025-12:** {val2}")
    else:
        st.error("데이터를 찾지 못했습니다.")
