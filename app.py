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
st.title("🚢 K-STAT 키보드 제어 모드")
st.info("TAB 키를 이용해 입력창을 찾아가는 '키보드 네비게이션' 방식으로 작동합니다.")

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
    wait = WebDriverWait(driver, 20)
    actions = ActionChains(driver)

    results = []

    try:
        # [단계 1] 메인 접속 및 메뉴 이동
        status.write("⏳ K-STAT 접속 및 메뉴 이동...")
        driver.get("https://stat.kita.net/")
        time.sleep(2)
        
        # '국내통계' 클릭
        btn_1 = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '국내통계')]")))
        btn_1.click()
        time.sleep(1)

        # '품목 수출입' 클릭
        btn_2 = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
        btn_2.click()
        time.sleep(3) 

        # [단계 2] '총괄' 탭 클릭 후 TAB 이동 (핵심 로직)
        status.write("⏳ '총괄' 클릭 후 TAB 키 4번 입력 중...")
        
        # iframe 처리 (혹시 모르니 메인 프레임으로 복귀)
        driver.switch_to.default_content()
        
        # 1. '총괄' 버튼 찾아서 클릭 (포커스 잡기)
        summary_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '총괄')]")))
        summary_tab.click()
        time.sleep(1)
        
        # 2. TAB 4번 누르고 HSK 입력 후 엔터
        # (총괄 버튼에서 TAB 4번 -> 입력창 도착 -> 입력 -> 엔터)
        actions.send_keys(Keys.TAB)
        actions.send_keys(Keys.TAB)
        actions.send_keys(Keys.TAB)
        actions.send_keys(Keys.TAB)
        actions.send_keys(target_hsk)
        actions.send_keys(Keys.ENTER)
        actions.perform()
        
        status.write(f"⏳ HSK {target_hsk} 입력 및 엔터 입력 완료! 결과 로딩 대기...")
        time.sleep(5) # 조회 결과 로딩 대기

        # [단계 3] 결과 확인 및 상세 진입 (파란색 링크)
        status.write("⏳ 상세 정보(파란색 링크) 클릭 시도...")
        
        # 입력이 제대로 되었다면 결과 화면에 링크가 떴을 것임
        # iframe 안에 결과가 있을 수 있으므로 iframe 탐색
        link_clicked = False
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        
        for i in range(len(iframes) + 1):
            try:
                if i > 0:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(iframes[i-1])
                
                # 링크 클릭 시도
                link_xpath = f"//a[contains(text(), '{target_hsk}')]"
                detail_link = driver.find_element(By.XPATH, link_xpath)
                detail_link.click()
                link_clicked = True
                break
            except:
                continue
        
        if not link_clicked:
            # 혹시 메인 프레임에 있을 수도 있으니 다시 시도
            driver.switch_to.default_content()
            try:
                link_xpath = f"//a[contains(text(), '{target_hsk}')]"
                driver.find_element(By.XPATH, link_xpath).click()
                link_clicked = True
            except:
                pass

        if not link_clicked:
            status.error("❌ 결과 링크를 클릭하지 못했습니다. (TAB 입력이 빗나갔거나 조회가 안됨)")
            st.image(driver.get_screenshot_as_png()) # 화면 확인
            return None
            
        time.sleep(5) # 팝업 로딩

        # 새 창 전환
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

        # [단계 4] 데이터 추출 (당월/전월)
        status.write("⏳ 상세 데이터 분석 중...")

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
            
            # 연도 클릭
            try:
                driver.find_element(By.XPATH, f"//*[contains(text(), '{y}')]").click()
                time.sleep(2)
            except:
                pass

            html = driver.page_source
            dfs = pd.read_html(html)
            val = "데이터 없음"
            
            # 표 데이터 찾기
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

# --------------------------------------------------------------------------
# 3. 실행
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
