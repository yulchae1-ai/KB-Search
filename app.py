import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
from datetime import datetime
import io

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 무역통계 수집기", layout="centered")
st.title("🚢 K-STAT 데이터 수집기")
st.info("국내통계 → 품목 수출입 → 총괄 → Tab 4번 → HSK 코드 입력")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드 (예: 847950)", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 헬퍼 함수
# --------------------------------------------------------------------------
def safe_click(driver, element):
    """JavaScript로 안전하게 클릭"""
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", element)
        return True
    except:
        try:
            element.click()
            return True
        except:
            return False

def wait_and_click(driver, wait, xpaths, description="요소"):
    """여러 XPATH 중 하나를 찾아서 클릭"""
    for xpath in xpaths:
        try:
            element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            if safe_click(driver, element):
                return True
        except:
            continue
    return False

# --------------------------------------------------------------------------
# 3. 크롤링 함수
# --------------------------------------------------------------------------
def run_crawler(target_hsk):
    status = st.empty()
    debug_area = st.expander("🔍 디버그 정보", expanded=False)
    
    status.write("⏳ 브라우저 초기화 중...")

    # 브라우저 옵션
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={ua}")

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    wait = WebDriverWait(driver, 15)
    actions = ActionChains(driver)
    results = []

    try:
        # ============================================================
        # [단계 1] K-STAT 메인 페이지 접속
        # ============================================================
        status.write("⏳ K-STAT 메인 페이지 접속 중...")
        driver.get("https://stat.kita.net/")
        time.sleep(3)
        
        with debug_area:
            st.image(driver.get_screenshot_as_png(), caption="1. 메인 페이지")

        # ============================================================
        # [단계 2] '국내통계' 메뉴 클릭
        # ============================================================
        status.write("⏳ '국내통계' 메뉴 클릭 중...")
        
        domestic_xpaths = [
            "//a[contains(text(), '국내통계')]",
            "//span[contains(text(), '국내통계')]",
            "//*[contains(text(), '국내통계')]",
            "//li[contains(@class, 'menu')]//a[contains(text(), '국내')]",
        ]
        
        if not wait_and_click(driver, wait, domestic_xpaths, "국내통계"):
            status.error("❌ '국내통계' 메뉴를 찾지 못했습니다.")
            st.image(driver.get_screenshot_as_png())
            return None
        
        time.sleep(2)
        
        with debug_area:
            st.image(driver.get_screenshot_as_png(), caption="2. 국내통계 클릭 후")

        # ============================================================
        # [단계 3] '품목 수출입' 클릭
        # ============================================================
        status.write("⏳ '품목 수출입' 메뉴 클릭 중...")
        
        item_xpaths = [
            "//a[contains(text(), '품목 수출입')]",
            "//a[contains(text(), '품목수출입')]",
            "//a[contains(text(), '품목별')]",
            "//span[contains(text(), '품목 수출입')]",
            "//*[contains(text(), '품목 수출입')]",
            "//li//a[contains(@href, 'item') or contains(@href, 'Item')]",
        ]
        
        if not wait_and_click(driver, wait, item_xpaths, "품목 수출입"):
            status.error("❌ '품목 수출입' 메뉴를 찾지 못했습니다.")
            st.image(driver.get_screenshot_as_png())
            return None
        
        time.sleep(3)
        
        with debug_area:
            st.image(driver.get_screenshot_as_png(), caption="3. 품목 수출입 클릭 후")

        # ============================================================
        # [단계 4] '총괄' 탭 클릭
        # ============================================================
        status.write("⏳ '총괄' 탭 클릭 중...")
        
        # iframe 확인 및 전환
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        for iframe in iframes:
            try:
                driver.switch_to.frame(iframe)
                # 총괄 탭이 있는지 확인
                if len(driver.find_elements(By.XPATH, "//*[contains(text(), '총괄')]")) > 0:
                    break
                driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
                continue
        
        total_xpaths = [
            "//a[contains(text(), '총괄')]",
            "//span[contains(text(), '총괄')]",
            "//li[contains(text(), '총괄')]",
            "//button[contains(text(), '총괄')]",
            "//*[@class='tab' or contains(@class, 'tab')]//a[contains(text(), '총괄')]",
            "//*[contains(@class, 'tab')]//*[contains(text(), '총괄')]",
            "//div[contains(@class, 'tab')]//a[1]",  # 첫 번째 탭
        ]
        
        if not wait_and_click(driver, wait, total_xpaths, "총괄"):
            status.warning("⚠️ '총괄' 탭을 명시적으로 찾지 못함. 계속 진행...")
        
        time.sleep(2)
        
        with debug_area:
            st.image(driver.get_screenshot_as_png(), caption="4. 총괄 탭 클릭 후")

        # ============================================================
        # [단계 5] Tab 4번 눌러서 HSK 코드 입력란으로 이동
        # ============================================================
        status.write("⏳ Tab 키로 HSK 코드 입력란 이동 중...")
        
        # 먼저 페이지 body에 포커스
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            body.click()
        except:
            pass
        
        time.sleep(0.5)
        
        # Tab 키 4번 누르기
        for i in range(4):
            actions.send_keys(Keys.TAB).perform()
            time.sleep(0.3)
        
        time.sleep(0.5)
        
        # 현재 포커스된 요소 가져오기
        try:
            active_element = driver.switch_to.active_element
            
            with debug_area:
                st.write(f"포커스된 요소 태그: {active_element.tag_name}")
                st.write(f"포커스된 요소 ID: {active_element.get_attribute('id')}")
                st.write(f"포커스된 요소 Name: {active_element.get_attribute('name')}")
        except Exception as e:
            with debug_area:
                st.write(f"활성 요소 확인 오류: {e}")

        # ============================================================
        # [단계 6] HSK 코드 입력
        # ============================================================
        status.write(f"⏳ HSK 코드 '{target_hsk}' 입력 중...")
        
        try:
            active_element = driver.switch_to.active_element
            
            # 입력창 초기화 및 입력
            active_element.clear()
            time.sleep(0.2)
            active_element.send_keys(target_hsk)
            time.sleep(0.5)
            
            # 입력 확인
            entered_value = active_element.get_attribute('value')
            with debug_area:
                st.write(f"✅ 입력된 값: {entered_value}")
            
            if entered_value != target_hsk:
                # JavaScript로 직접 입력 시도
                driver.execute_script(f"arguments[0].value = '{target_hsk}';", active_element)
                driver.execute_script("""
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, active_element)
                
        except Exception as e:
            status.error(f"❌ HSK 코드 입력 실패: {e}")
            st.image(driver.get_screenshot_as_png())
            return None
        
        with debug_area:
            st.image(driver.get_screenshot_as_png(), caption="5. HSK 코드 입력 후")

        # ============================================================
        # [단계 7] '조회' 버튼 클릭
        # ============================================================
        status.write("⏳ '조회' 버튼 클릭 중...")
        
        search_xpaths = [
            "//button[contains(text(), '조회')]",
            "//a[contains(text(), '조회')]",
            "//input[@value='조회']",
            "//span[contains(text(), '조회')]/parent::button",
            "//span[contains(text(), '조회')]/parent::a",
            "//*[contains(@class, 'btn')][contains(text(), '조회')]",
            "//*[contains(@class, 'search')][contains(text(), '조회')]",
            "//img[contains(@alt, '조회')]/parent::*",
            "//*[@id='btnSearch']",
            "//*[@id='searchBtn']",
        ]
        
        search_clicked = False
        for xpath in search_xpaths:
            try:
                search_btn = driver.find_element(By.XPATH, xpath)
                safe_click(driver, search_btn)
                search_clicked = True
                with debug_area:
                    st.write(f"✅ 조회 버튼 클릭 성공: {xpath}")
                break
            except:
                continue
        
        if not search_clicked:
            # Enter 키로 조회 시도
            try:
                active_element.send_keys(Keys.ENTER)
                with debug_area:
                    st.write("✅ Enter 키로 조회 시도")
            except:
                status.warning("⚠️ 조회 버튼을 찾지 못했습니다.")
        
        status.write("⏳ 검색 결과 로딩 대기 중...")
        time.sleep(5)
        
        with debug_area:
            st.image(driver.get_screenshot_as_png(), caption="6. 조회 버튼 클릭 후")

        # ============================================================
        # [단계 8] 결과 링크 클릭 (상세 페이지 이동)
        # ============================================================
        status.write("⏳ 검색 결과에서 상세 링크 클릭 중...")
        
        result_xpaths = [
            f"//a[contains(text(), '{target_hsk}')]",
            f"//td[contains(text(), '{target_hsk}')]//a",
            f"//tr[contains(., '{target_hsk}')]//a",
            "//table//tbody//tr[1]//td//a",
            "//table//tr[2]//td//a",  # 헤더 제외 첫 번째 행
        ]
        
        for xpath in result_xpaths:
            try:
                result_link = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                safe_click(driver, result_link)
                with debug_area:
                    st.write(f"✅ 결과 링크 클릭: {xpath}")
                break
            except:
                continue
        
        time.sleep(3)
        
        # 새 창 확인
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(2)
        
        with debug_area:
            st.image(driver.get_screenshot_as_png(), caption="7. 상세 페이지")

        # ============================================================
        # [단계 9] 데이터 추출
        # ============================================================
        status.write("⏳ 데이터 추출 중...")
        
        now = datetime.now()
        cur_year = str(now.year)
        cur_month = f"{now.month:02d}"
        
        if now.month == 1:
            prev_year = str(now.year - 1)
            prev_month = "12"
        else:
            prev_year = str(now.year)
            prev_month = f"{now.month - 1:02d}"

        try:
            html = driver.page_source
            dfs = pd.read_html(html, encoding='utf-8')
            
            with debug_area:
                st.write(f"📊 발견된 테이블 수: {len(dfs)}")
                for i, df in enumerate(dfs[:3]):
                    st.write(f"테이블 {i}:")
                    st.dataframe(df.head(10))
            
            # 수출 데이터 추출 로직
            found_data = False
            for df in dfs:
                cols = [str(c).lower() for c in df.columns]
                if any('수출' in c or 'export' in c for c in cols):
                    found_data = True
                    
                    # 당월/전월 데이터 찾기
                    for idx, row in df.iterrows():
                        row_str = ' '.join([str(v) for v in row.values])
                        
                        if cur_month in row_str or f"{cur_year}.{cur_month}" in row_str:
                            export_val = "확인 필요"
                            for col in df.columns:
                                if '수출' in str(col) and '금액' in str(col):
                                    export_val = row[col]
                                    break
                            results.append({
                                "구분": "당월",
                                "기간": f"{cur_year}-{cur_month}",
                                "수출금액": export_val
                            })
                            
            if not found_data:
                results.append({
                    "구분": "당월",
                    "기간": f"{cur_year}-{cur_month}",
                    "수출금액": "테이블에서 수출 데이터 확인 필요"
                })
                results.append({
                    "구분": "전월",
                    "기간": f"{prev_year}-{prev_month}",
                    "수출금액": "테이블에서 수출 데이터 확인 필요"
                })
                    
        except Exception as e:
            with debug_area:
                st.write(f"테이블 파싱 오류: {e}")
            results.append({
                "구분": "오류",
                "기간": "N/A",
                "수출금액": str(e)
            })

        if not results:
            results.append({
                "구분": "N/A",
                "기간": "N/A",
                "수출금액": "데이터를 찾지 못했습니다"
            })

    except Exception as e:
        st.error(f"❌ 오류 발생: {str(e)}")
        try:
            st.image(driver.get_screenshot_as_png(), caption="오류 발생 시점")
        except:
            pass
        return None

    finally:
        driver.quit()
    
    return pd.DataFrame(results)

# --------------------------------------------------------------------------
# 4. 실행
# --------------------------------------------------------------------------
if submit:
    df_res = run_crawler(hsk_code)
    
    if df_res is not None:
        st.success("✅ 수집 완료!")
        st.table(df_res)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_res.to_excel(writer, index=False)
            
        st.download_button("📥 엑셀 다운로드", data=buffer, file_name="result.xlsx")
