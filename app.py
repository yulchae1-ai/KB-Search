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
st.set_page_config(page_title="K-STAT 무역통계", layout="centered")
st.title("🚢 K-STAT: 총괄 + TAB 4번 모드")
st.info("사용자 정의: '총괄' 버튼 클릭 후 TAB 4회 입력하여 조회합니다.")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 크롤링 함수
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
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    actions = ActionChains(driver)

    results = []

    try:
        # [1] 접속 및 메뉴 이동
        status.write("⏳ K-STAT 접속...")
        driver.get("https://stat.kita.net/")
        time.sleep(2)
        
        # 국내통계 -> 품목 수출입 (JS로 강제 클릭하여 오차 제거)
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

        # [2] '총괄' 버튼이 있는 Iframe 찾기 (가장 중요)
        status.write("⏳ '총괄' 버튼 찾는 중...")
        
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_frame = False
        
        for i in range(len(iframes)):
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(iframes[i])
                
                # '총괄'이라는 글자가 있는 버튼/탭 찾기
                if len(driver.find_elements(By.XPATH, "//*[contains(text(), '총괄')]")) > 0:
                    found_frame = True
                    # 찾았으면 그 상태(iframe 안) 유지
                    break 
            except:
                continue
        
        if not found_frame:
            # 못 찾았으면 메인 프레임에서 시도
            driver.switch_to.default_content()

        # [3] '총괄' 클릭 및 TAB 4번 (사용자 요청 로직)
        status.write(f"⏳ '총괄' 클릭 -> TAB 4번 -> {target_hsk} 입력...")
        
        try:
            # 1. 총괄 버튼을 찾음
            summary_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '총괄')]")))
            
            # 2. 클릭 (포커스 잡기)
            summary_btn.click()
            time.sleep(1) # 포커스 잡힐 시간 줌
            
            # 3. TAB 4번 + 입력 + 엔터 (ActionChains 사용)
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(target_hsk)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
            status.write("✅ 입력 및 엔터 완료! 결과 대기...")
            time.sleep(5)
            
        except Exception as e:
            status.error(f"입력 실패: {e}")
            st.image(driver.get_screenshot_as_png())
            return None

        # [4] 결과 링크(파란색) 클릭
        status.write("⏳ 결과 링크 클릭...")
        
        try:
            # 입력이 성공했다면 결과가 떴을 것임
            link_xpath = f"//a[contains(text(), '{target_hsk}')]"
            link_el = wait.until(EC.element_to_be_clickable((By.XPATH, link_xpath)))
            link_el.click()
            time.sleep(5)
        except:
            status.error("❌ 결과 링크를 찾지 못했습니다. TAB 횟수가 안 맞거나 데이터가 없습니다.")
            st.image(driver.get_screenshot_as_png())
            return None

        # 팝업 창 전환
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

        # [5] 데이터 추출 (당월/전월)
        status.write("⏳ 데이터 추출 중...")
        
        now = datetime.now()
        cur_y, cur_m = str(now.year), f"{now.month:02d}"
        
        if now.month == 1:
            prev_y, prev_m = str(now.year - 1), "12"
        else:
            prev_y, prev_m = str(now.year), f"{now.month - 1:02d}"

        targets = [
            {"label": "당월", "y": cur_y, "m": cur_m},
            {"label": "전월", "y": prev_y, "m": prev_m}
        ]

        for t in targets:
            y, m = t['y'], t['m']
            
            # 연도 탭 클릭 시도
            try:
                driver.find_element(By.XPATH, f"//*[contains(text(), '{y}')]").click()
                time.sleep(2)
            except:
                pass
            
            # 테이블 읽기
            dfs = pd.read_html(driver.page_source)
            val = "데이터 없음"
            found = False
            
            for df in dfs:
                if found: break
                for idx, row in df.iterrows():
                    txt = " ".join(row.astype(str).values)
                    if f"{int(m)}월" in txt or f"{y}.{m}" in txt:
                        # 수출 금액 찾기
                        if '수출금액' in df.columns: val = row['수출금액']
                        elif '수출' in df.columns: val = row['수출']
                        else: val = txt
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

# 실행
if submit:
    df = run_crawler(hsk_code)
    if df is not None:
        st.success("완료")
        st.table(df)
        
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        st.download_button("엑셀 다운로드", buf, "result.xlsx")
