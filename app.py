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
import io

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 무역통계 수집기", layout="centered")
st.title("🚢 K-STAT 데이터 수집기 (강제클릭 Ver)")
st.info("한글 폰트 적용 완료. 자바스크립트 강제 클릭으로 조회합니다.")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드 (예: 847950)", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 크롤링 함수
# --------------------------------------------------------------------------
def run_crawler(target_hsk):
    status = st.empty()
    status.write("⏳ 브라우저 초기화 중...")

    # 브라우저 옵션
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
        # [단계 1] 메인 접속 및 메뉴 이동
        status.write("⏳ K-STAT 접속 및 메뉴 이동...")
        driver.get("https://stat.kita.net/")
        time.sleep(2)
        
        # '국내통계' 클릭 (JS 강제 클릭)
        try:
            btn_1 = driver.find_element(By.XPATH, "//*[contains(text(), '국내통계')]")
            driver.execute_script("arguments[0].click();", btn_1)
        except:
            pass # 이미 열려있거나 못 찾으면 패스
        time.sleep(1)

        # '품목 수출입' 클릭 (JS 강제 클릭)
        try:
            btn_2 = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
            driver.execute_script("arguments[0].click();", btn_2)
        except:
            status.warning("메뉴 이동 중 문제 발생, 계속 진행합니다.")
        time.sleep(3) 

        # [단계 2] Iframe 탐색 및 '총괄' 클릭
        status.write("⏳ '총괄' 버튼 찾는 중...")
        
        # 1. 화면에 있는 모든 iframe을 찾음
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        frame_found = False
        
        # 2. 하나씩 들어가서 '총괄' 버튼이 있는지 확인
        for i in range(len(iframes)):
            try:
                driver.switch_to.default_content() # 초기화
                driver.switch_to.frame(iframes[i]) # 프레임 진입
                
                # 총괄 버튼이 보이나요? (클릭 가능 여부 상관없이 존재만 확인)
                if len(driver.find_elements(By.XPATH, "//*[contains(text(), '총괄')]")) > 0:
                    frame_found = True
                    break 
            except:
                continue
        
        if not frame_found:
            driver.switch_to.default_content()

        # 3. '총괄' 버튼 클릭 (JS 강제 클릭 사용)
        try:
            summary_tab = driver.find_element(By.XPATH, "//*[contains(text(), '총괄')]")
            # ★ 핵심: 화면 가림 무시하고 자바스크립트로 눌러버리기
            driver.execute_script("arguments[0].click();", summary_tab)
            status.write("✅ '총괄' 탭 강제 클릭 성공")
        except Exception as e:
            status.warning(f"'총괄' 탭 클릭 실패 (이미 활성화 되었을 수 있음): {e}")
        
        time.sleep(1)
        
        # [단계 3] TAB 키 네비게이션
        status.write(f"⏳ HSK {target_hsk} 입력 (TAB 이동)...")
        
        # 총괄 탭을 한 번 더 포커스(클릭) 하고 시작
        actions.send_keys(Keys.TAB)
        actions.send_keys(Keys.TAB)
        actions.send_keys(Keys.TAB)
        actions.send_keys(Keys.TAB)
        actions.send_keys(target_hsk)
        actions.send_keys(Keys.ENTER)
        actions.perform()
        
        time.sleep(5) 

        # [단계 4] 상세 정보 클릭 (파란색 링크)
        status.write("⏳ 검색 결과(파란색 링크) 클릭...")
        
        link_clicked = False
        
        # 현재 프레임에서 링크 찾기 시도
        try:
            link_xpath = f"//a[contains(text(), '{target_hsk}')]"
            link_element = driver.find_element(By.XPATH, link_xpath)
            driver.execute_script("arguments[0].click();", link_element) # 강제 클릭
            link_clicked = True
        except:
            # 안 되면 다시 iframe 뒤지기
            driver.switch_to.default_content()
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                try:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(frame)
                    link_element = driver.find_element(By.XPATH, f"//a[contains(text(), '{target_hsk}')]")
                    driver.execute_script("arguments[0].click();", link_element) # 강제 클릭
                    link_clicked = True
                    break
                except:
                    pass
        
        if not link_clicked:
            status.error("❌ 결과 링크를 찾지 못했습니다.")
            st.image(driver.get_screenshot_as_png())
            return None

        time.sleep(5) 

        # 새 창 전환
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

        # [단계 5] 데이터 추출
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

        targets = [
            {"label": "당월", "year": cur_year, "month": cur_month},
            {"label": "전월", "year": prev_year, "month": prev_month}
        ]

        for t in targets:
            y = t['year']
            m = t['month']
            
            try:
                # 연도 버튼도 강제 클릭
                year_btn = driver.find_element(By.XPATH, f"//*[contains(text(), '{y}')]")
                driver.execute_script("arguments[0].click();", year_btn)
                time.sleep(2)
            except:
                pass

            html = driver.page_source
            dfs = pd.read_html(html)
            val = "데이터 없음"
            
            found = False
            for df in dfs:
                if found: break
                for idx, row in df.iterrows():
                    row_txt = " ".join(row.astype(str).values)
                    if f"{int(m)}월" in row_txt or f"{y}.{m}" in row_txt:
                        if '수출금액' in df.columns: val = row['수출금액']
                        elif '수출' in df.columns: val = row['수출']
                        else: val = row_txt 
                        found = True
                        break
            
            results.append({"구분": t['label'], "기간": f"{y}-{m}", "수출금액": val})

    except Exception as e:
        st.error("오류 발생")
        st.write(e)
        try: st.image(driver.get_screenshot_as_png())
        except: pass
        return None

    finally:
        driver.quit()
    
    return pd.DataFrame(results)

if submit:
    df_res = run_crawler(hsk_code)
    
    if df_res is not None:
        st.success("✅ 수집 완료!")
        st.table(df_res)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_res.to_excel(writer, index=False)
            
        st.download_button("📥 엑셀 다운로드", data=buffer, file_name="result.xlsx")
