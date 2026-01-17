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
st.title("🚢 K-STAT 데이터 수집기 (TAB 네비게이션)")
st.info("Iframe 내부로 정확히 진입하여 '총괄' 탭 클릭 후 TAB 키로 이동합니다.")

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
    
    # 한글 폰트 미설치시에도 동작하도록 User-Agent 설정
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
            pass 
        time.sleep(1)

        # '품목 수출입' 클릭 (JS 강제 클릭)
        try:
            btn_2 = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
            driver.execute_script("arguments[0].click();", btn_2)
        except:
            status.warning("메뉴 이동 중 문제 발생, 계속 진행합니다.")
        time.sleep(3) 

        # [단계 2] '총괄' 탭이 있는 올바른 Iframe 찾기 (가장 중요!)
        status.write("⏳ 데이터 입력 화면(Iframe) 진입 시도...")
        
        # 화면상의 모든 iframe 수집
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        target_iframe_index = -1
        
        # '시작코드'라는 텍스트가 있는 iframe을 찾음 (이게 진짜임)
        for i, iframe in enumerate(iframes):
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(iframe)
                # '시작코드' 혹은 '총괄' 텍스트가 있는지 확인
                if len(driver.find_elements(By.XPATH, "//*[contains(text(), '시작코드')]")) > 0:
                    target_iframe_index = i
                    break
                if len(driver.find_elements(By.XPATH, "//*[contains(text(), '총괄')]")) > 0:
                    target_iframe_index = i
                    break
            except:
                continue
        
        # 찾은 iframe으로 최종 진입
        if target_iframe_index != -1:
            driver.switch_to.default_content()
            driver.switch_to.frame(iframes[target_iframe_index])
            status.write("✅ 올바른 입력 화면(Iframe)을 찾았습니다!")
        else:
            # 못 찾았으면 메인 프레임에서 시도
            driver.switch_to.default_content()
            status.warning("⚠️ Iframe을 특정하지 못해 메인 화면에서 시도합니다.")

        # [단계 3] '총괄' 클릭 및 TAB 이동
        status.write("⏳ '총괄' 클릭 후 TAB 4회 입력...")
        
        # '총괄' 버튼 찾기
        try:
            summary_tab = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '총괄')]")))
            # JS로 강제 클릭 (포커스 잡기)
            driver.execute_script("arguments[0].click();", summary_tab)
            time.sleep(1)
            
            # 여기서부터 TAB 4번
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(target_hsk)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
            status.write(f"⏳ HSK {target_hsk} 입력 완료. 결과 대기...")
            
        except Exception as e:
            status.error(f"❌ '총괄' 버튼을 찾거나 클릭하는 데 실패했습니다: {e}")
            st.image(driver.get_screenshot_as_png())
            return None
        
        time.sleep(5) 

        # [단계 4] 상세 정보 클릭 (파란색 링크)
        status.write("⏳ 검색 결과(파란색 링크) 클릭...")
        
        link_clicked = False
        try:
            # 현재 프레임에서 링크 찾기
            link_xpath = f"//a[contains(text(), '{target_hsk}')]"
            link_element = wait.until(EC.presence_of_element_located((By.XPATH, link_xpath)))
            driver.execute_script("arguments[0].click();", link_element)
            link_clicked = True
        except:
            status.error("❌ 결과 링크(파란색 글씨)를 찾지 못했습니다. 입력이 제대로 안 되었을 수 있습니다.")
            st.image(driver.get_screenshot_as_png())
            return None

        time.sleep(5) 

        # 새 창 전환 (팝업)
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
            
            # 연도 버튼 클릭 (JS 강제 클릭)
            try:
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
                    # 날짜 패턴 확인
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
