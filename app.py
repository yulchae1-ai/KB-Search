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
st.title("🚢 K-STAT 데이터 수집기 (키보드 매크로)")
st.info("사용자 정의: [HSK 클릭] -> [TAB 2] -> [입력] -> [TAB 11+엔터] -> [TAB 8+DOWN+엔터]")

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
    
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={ua}")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)
    actions = ActionChains(driver)

    results = []

    try:
        # [1] 접속 및 메뉴 이동
        status.write("⏳ K-STAT 접속...")
        driver.get("https://stat.kita.net/")
        time.sleep(2)
        
        # 메뉴 이동 (JS 강제 클릭)
        try:
            # 국내통계
            btn1 = driver.find_element(By.XPATH, "//*[contains(text(), '국내통계')]")
            driver.execute_script("arguments[0].click();", btn1)
            time.sleep(1)
            
            # 품목 수출입
            btn2 = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
            driver.execute_script("arguments[0].click();", btn2)
            time.sleep(3)
        except:
            status.error("메뉴 이동 실패")
            return None

        # [2] 'HSK' 글자가 있는 Iframe 찾기
        status.write("⏳ 입력 화면(Iframe) 찾는 중...")
        
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_frame = False
        
        for i in range(len(iframes)):
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(iframes[i])
                
                # 'HSK' 텍스트가 있는지 확인
                if len(driver.find_elements(By.XPATH, "//*[contains(text(), 'HSK')]")) > 0:
                    found_frame = True
                    break 
            except:
                continue
        
        if not found_frame:
            driver.switch_to.default_content()

        # [3] 복합 키보드 액션 (사용자 요청 로직)
        status.write(f"⏳ 키보드 매크로 실행 중...")
        
        try:
            # 1. 'HSK' 라벨 클릭 (시작점)
            hsk_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'HSK')]")))
            hsk_label.click()
            time.sleep(1) 
            
            # 2. [TAB 2번] -> [입력]
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(target_hsk)
            actions.perform()
            time.sleep(0.5)

            # 3. [TAB 11번] -> [엔터] (조회 실행)
            status.write("⏳ TAB 11회 -> 엔터 (조회)...")
            for _ in range(11):
                actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
            status.write("⏳ 조회 결과 로딩 중 (5초 대기)...")
            time.sleep(5) # 결과가 뜰 때까지 충분히 대기

            # 4. [TAB 8번] -> [아래 화살표] -> [엔터] (상세 진입)
            # 파란 글씨 찾는 대신 키보드로 이동
            status.write("⏳ TAB 8회 -> DOWN -> 엔터 (상세 진입)...")
            
            # 액션 체인 초기화 후 다시 실행
            actions = ActionChains(driver) 
            
            for _ in range(8):
                actions.send_keys(Keys.TAB)
            
            actions.send_keys(Keys.DOWN)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
            status.write("✅ 상세 진입 명령 완료! 팝업 대기...")
            time.sleep(5)
            
        except Exception as e:
            status.error(f"키보드 입력 실패: {e}")
            st.image(driver.get_screenshot_as_png())
            return None

        # [4] 팝업 창 전환
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            status.write("✅ 상세 팝업창 감지 성공!")
        else:
            status.warning("⚠️ 팝업창이 뜨지 않았을 수 있습니다. (TAB 횟수 재확인 필요)")
            st.image(driver.get_screenshot_as_png())

        # [5] 데이터 추출
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
            
            # 연도 탭 클릭 (JS 강제 클릭)
            try:
                year_btn = driver.find_element(By.XPATH, f"//*[contains(text(), '{y}')]")
                driver.execute_script("arguments[0].click();", year_btn)
                time.sleep(2)
            except:
                pass
            
            # 테이블 데이터 읽기
            dfs = pd.read_html(driver.page_source)
            val = "데이터 없음"
            found = False
            
            for df in dfs:
                if found: break
                for idx, row in df.iterrows():
                    txt = " ".join(row.astype(str).values)
                    # "01월" 또는 "2026.01" 형식 찾기
                    if f"{int(m)}월" in txt or f"{y}.{m}" in txt:
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
