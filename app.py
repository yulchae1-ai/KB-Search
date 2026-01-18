import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
import time
from datetime import datetime
import io

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 무역통계 수집기", layout="centered")
st.title("🚢 K-STAT 데이터 수집기 (개선판)")
st.info("시작코드 입력창을 직접 찾아 클릭하여 데이터를 조회합니다.")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드 (예: 847950)", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 헬퍼 함수들
# --------------------------------------------------------------------------
def safe_find_element(driver, by, value, timeout=10):
    """안전하게 요소를 찾는 함수"""
    try:
        wait = WebDriverWait(driver, timeout)
        element = wait.until(EC.presence_of_element_located((by, value)))
        return element
    except:
        return None

def safe_click(driver, element):
    """안전하게 클릭하는 함수"""
    try:
        driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.3)
        driver.execute_script("arguments[0].click();", element)
        return True
    except:
        return False

def find_input_in_all_frames(driver, input_selectors, timeout=15):
    """모든 프레임을 탐색하여 입력창 찾기"""
    
    # 1. 메인 프레임에서 먼저 시도
    driver.switch_to.default_content()
    for selector_type, selector_value in input_selectors:
        try:
            element = WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((selector_type, selector_value))
            )
            if element:
                return element, "main"
        except:
            continue
    
    # 2. 모든 iframe 탐색
    driver.switch_to.default_content()
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    
    for idx, iframe in enumerate(iframes):
        try:
            driver.switch_to.default_content()
            
            # iframe이 보이고 상호작용 가능한지 확인
            WebDriverWait(driver, 5).until(EC.frame_to_be_available_and_switch_to_it(iframe))
            
            for selector_type, selector_value in input_selectors:
                try:
                    element = WebDriverWait(driver, 2).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    if element:
                        return element, f"iframe_{idx}"
                except:
                    continue
                    
        except Exception as e:
            continue
    
    # 3. 중첩 iframe 탐색
    driver.switch_to.default_content()
    for idx, iframe in enumerate(iframes):
        try:
            driver.switch_to.default_content()
            driver.switch_to.frame(iframe)
            
            nested_iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for nested_idx, nested_iframe in enumerate(nested_iframes):
                try:
                    driver.switch_to.frame(nested_iframe)
                    
                    for selector_type, selector_value in input_selectors:
                        try:
                            element = WebDriverWait(driver, 2).until(
                                EC.presence_of_element_located((selector_type, selector_value))
                            )
                            if element:
                                return element, f"iframe_{idx}_nested_{nested_idx}"
                        except:
                            continue
                    
                    driver.switch_to.parent_frame()
                except:
                    try:
                        driver.switch_to.parent_frame()
                    except:
                        pass
                    continue
        except:
            continue
    
    return None, None

# --------------------------------------------------------------------------
# 3. 크롤링 함수
# --------------------------------------------------------------------------
def run_crawler(target_hsk):
    status = st.empty()
    debug_area = st.expander("🔍 디버그 정보", expanded=False)
    status.write("⏳ 브라우저 초기화 중...")

    # 브라우저 옵션
    options = Options()
    options.add_argument("--headless=new")  # 새로운 headless 모드
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 자동화 탐지 우회
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={ua}")

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    wait = WebDriverWait(driver, 20)
    results = []

    try:
        # ============================================================
        # [단계 1] 직접 품목별 수출입 페이지로 이동
        # ============================================================
        status.write("⏳ K-STAT 품목별 수출입 페이지 접속 중...")
        
        # 직접 URL로 접근 시도 (메뉴 클릭 대신)
        direct_urls = [
            "https://stat.kita.net/stat/kts/ctr/CtrItemImpExpList.screen",
            "https://stat.kita.net/stat/kts/prod/ProdItemImpExpList.screen",
            "https://stat.kita.net/stat/istat/item/ItemDetailImpExpList.screen"
        ]
        
        page_loaded = False
        for url in direct_urls:
            try:
                driver.get(url)
                time.sleep(3)
                
                # 페이지가 올바르게 로드되었는지 확인
                if "품목" in driver.page_source or "HSK" in driver.page_source or "코드" in driver.page_source:
                    page_loaded = True
                    with debug_area:
                        st.write(f"✅ 접속 성공: {url}")
                    break
            except:
                continue
        
        # 직접 URL 실패시 메인에서 시작
        if not page_loaded:
            status.write("⏳ 메인 페이지에서 메뉴 이동 중...")
            driver.get("https://stat.kita.net/")
            time.sleep(3)
            
            # 메뉴 클릭 시도
            menu_clicked = False
            menu_xpaths = [
                "//a[contains(text(), '국내통계')]",
                "//span[contains(text(), '국내통계')]",
                "//*[@id='menu']//a[contains(@href, 'item')]"
            ]
            
            for xpath in menu_xpaths:
                try:
                    menu = driver.find_element(By.XPATH, xpath)
                    safe_click(driver, menu)
                    time.sleep(2)
                    menu_clicked = True
                    break
                except:
                    continue
            
            # 품목 수출입 서브메뉴 클릭
            submenu_xpaths = [
                "//a[contains(text(), '품목별')]",
                "//a[contains(text(), '품목 수출입')]",
                "//a[contains(text(), '품목수출입')]"
            ]
            
            for xpath in submenu_xpaths:
                try:
                    submenu = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    safe_click(driver, submenu)
                    time.sleep(3)
                    break
                except:
                    continue

        # 스크린샷 저장 (디버그용)
        with debug_area:
            st.image(driver.get_screenshot_as_png(), caption="현재 화면")

        # ============================================================
        # [단계 2] 입력창 찾기 (다양한 선택자 시도)
        # ============================================================
        status.write("⏳ HSK 코드 입력창 찾는 중...")
        
        # 다양한 선택자 목록 (우선순위 순)
        input_selectors = [
            (By.ID, "s_st_hsk_no"),
            (By.ID, "st_hsk_no"),
            (By.ID, "hsk_no"),
            (By.ID, "hskCd"),
            (By.ID, "hs_cd"),
            (By.NAME, "s_st_hsk_no"),
            (By.NAME, "st_hsk_no"),
            (By.NAME, "hsk_no"),
            (By.CSS_SELECTOR, "input[id*='hsk']"),
            (By.CSS_SELECTOR, "input[id*='hs_']"),
            (By.CSS_SELECTOR, "input[name*='hsk']"),
            (By.CSS_SELECTOR, "input[name*='hs_']"),
            (By.XPATH, "//input[contains(@id, 'hsk')]"),
            (By.XPATH, "//input[contains(@id, 'hs_')]"),
            (By.XPATH, "//input[contains(@name, 'hsk')]"),
            (By.XPATH, "//td[contains(text(), '시작코드')]/following-sibling::td//input"),
            (By.XPATH, "//th[contains(text(), '시작코드')]/following-sibling::td//input"),
            (By.XPATH, "//label[contains(text(), 'HSK')]/following::input[1]"),
            (By.XPATH, "//span[contains(text(), '시작')]/ancestor::td/following-sibling::td//input"),
            (By.CSS_SELECTOR, ".search_box input[type='text']"),
            (By.CSS_SELECTOR, ".srch_box input[type='text']"),
            (By.XPATH, "//input[@type='text'][1]"),  # 첫 번째 텍스트 입력창
        ]
        
        input_box, frame_location = find_input_in_all_frames(driver, input_selectors)
        
        if input_box is None:
            status.error("❌ 입력창을 찾지 못했습니다.")
            
            # 페이지 소스에서 input 태그 분석
            with debug_area:
                st.write("📋 페이지 내 input 요소 분석:")
                driver.switch_to.default_content()
                page_html = driver.page_source
                
                # 간단한 input 태그 추출
                import re
                inputs = re.findall(r'<input[^>]*>', page_html, re.IGNORECASE)
                for inp in inputs[:20]:  # 처음 20개만
                    st.code(inp)
                
                st.image(driver.get_screenshot_as_png(), caption="오류 발생 시점 화면")
            
            return None
        
        with debug_area:
            st.write(f"✅ 입력창 발견 위치: {frame_location}")

        # ============================================================
        # [단계 3] HSK 코드 입력 및 조회
        # ============================================================
        status.write(f"⏳ HSK 코드 '{target_hsk}' 입력 중...")
        
        try:
            # 입력창이 상호작용 가능할 때까지 대기
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable(input_box))
            
            # 기존 값 지우고 입력
            input_box.click()
            time.sleep(0.5)
            input_box.clear()
            time.sleep(0.3)
            
            # send_keys 대신 JavaScript로 값 설정
            driver.execute_script("arguments[0].value = '';", input_box)
            time.sleep(0.2)
            driver.execute_script(f"arguments[0].value = '{target_hsk}';", input_box)
            
            # 이벤트 트리거 (React/Vue 등 SPA 대응)
            driver.execute_script("""
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """, input_box)
            
            time.sleep(0.5)
            
            # 입력 확인
            entered_value = input_box.get_attribute('value')
            with debug_area:
                st.write(f"입력된 값: {entered_value}")
            
        except Exception as e:
            status.error(f"❌ 코드 입력 실패: {str(e)}")
            with debug_area:
                st.image(driver.get_screenshot_as_png())
            return None

        # ============================================================
        # [단계 4] 조회 버튼 클릭
        # ============================================================
        status.write("⏳ 조회 버튼 클릭 중...")
        
        search_btn_selectors = [
            (By.XPATH, "//button[contains(text(), '조회')]"),
            (By.XPATH, "//a[contains(text(), '조회')]"),
            (By.XPATH, "//input[@value='조회']"),
            (By.XPATH, "//*[contains(@class, 'btn')][contains(text(), '조회')]"),
            (By.XPATH, "//span[contains(text(), '조회')]/parent::*"),
            (By.CSS_SELECTOR, ".btn_search"),
            (By.CSS_SELECTOR, "button.search"),
            (By.CSS_SELECTOR, "a.search"),
            (By.ID, "btnSearch"),
            (By.ID, "searchBtn"),
            (By.NAME, "search"),
        ]
        
        search_clicked = False
        for selector_type, selector_value in search_btn_selectors:
            try:
                search_btn = driver.find_element(selector_type, selector_value)
                safe_click(driver, search_btn)
                search_clicked = True
                with debug_area:
                    st.write(f"✅ 조회 버튼 클릭 성공: {selector_value}")
                break
            except:
                continue
        
        if not search_clicked:
            # Enter 키로 시도
            try:
                input_box.send_keys(Keys.ENTER)
                search_clicked = True
                with debug_area:
                    st.write("✅ Enter 키로 조회 시도")
            except:
                pass
        
        if not search_clicked:
            status.warning("⚠️ 조회 버튼을 찾지 못했습니다. Enter 키로 시도합니다.")
        
        status.write("⏳ 검색 결과 대기 중...")
        time.sleep(5)
        
        with debug_area:
            st.image(driver.get_screenshot_as_png(), caption="조회 후 화면")

        # ============================================================
        # [단계 5] 결과 링크 클릭
        # ============================================================
        status.write("⏳ 검색 결과 링크 찾는 중...")
        
        result_link_selectors = [
            (By.XPATH, f"//a[contains(text(), '{target_hsk}')]"),
            (By.XPATH, f"//td[contains(text(), '{target_hsk}')]/a"),
            (By.XPATH, f"//a[contains(@href, '{target_hsk}')]"),
            (By.XPATH, "//table//tbody//tr[1]//a"),  # 첫 번째 결과 링크
            (By.CSS_SELECTOR, "table tbody tr td a"),
        ]
        
        link_clicked = False
        for selector_type, selector_value in result_link_selectors:
            try:
                result_link = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((selector_type, selector_value))
                )
                safe_click(driver, result_link)
                link_clicked = True
                with debug_area:
                    st.write(f"✅ 결과 링크 클릭: {selector_value}")
                break
            except:
                continue
        
        if not link_clicked:
            status.warning("⚠️ 결과 링크를 찾지 못했습니다. 현재 페이지에서 데이터 추출 시도...")
        
        time.sleep(3)
        
        # 새 창/탭 확인
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            time.sleep(2)

        # ============================================================
        # [단계 6] 데이터 추출
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

        # 테이블 데이터 추출
        try:
            html = driver.page_source
            dfs = pd.read_html(html, encoding='utf-8')
            
            with debug_area:
                st.write(f"📊 발견된 테이블 수: {len(dfs)}")
                for i, df in enumerate(dfs[:5]):
                    st.write(f"테이블 {i}:")
                    st.dataframe(df.head())
            
            # 수출 데이터 찾기
            for df in dfs:
                df_str = df.to_string()
                if '수출' in df_str or '금액' in df_str:
                    results.append({
                        "구분": "당월",
                        "기간": f"{cur_year}-{cur_month}",
                        "수출금액": "테이블 데이터 확인 필요"
                    })
                    results.append({
                        "구분": "전월", 
                        "기간": f"{prev_year}-{prev_month}",
                        "수출금액": "테이블 데이터 확인 필요"
                    })
                    break
                    
        except Exception as e:
            with debug_area:
                st.write(f"테이블 파싱 오류: {e}")
            
            results.append({
                "구분": "당월",
                "기간": f"{cur_year}-{cur_month}",
                "수출금액": "데이터 추출 실패"
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
