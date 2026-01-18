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

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 무역통계 수집기", layout="centered")
st.title("🚢 K-STAT 데이터 조회 (매크로 Ver)")
st.info("HSK 입력 -> TAB 매크로 이동 -> 연도별 데이터 자동 추출")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드", value="847950")
    submit = st.form_submit_button("조회 시작 🚀")

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
            btn1 = driver.find_element(By.XPATH, "//*[contains(text(), '국내통계')]")
            driver.execute_script("arguments[0].click();", btn1)
            time.sleep(1)
            
            btn2 = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
            driver.execute_script("arguments[0].click();", btn2)
            time.sleep(3)
        except:
            status.error("메뉴 이동 실패")
            return None

        # [2] Iframe 찾기
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

        # [3] 키보드 매크로 실행
        status.write(f"⏳ 매크로 입력 중 ({target_hsk})...")
        
        try:
            # HSK 라벨 클릭
            hsk_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), 'HSK')]")))
            hsk_label.click()
            time.sleep(1) 
            
            # TAB 2번 -> 입력
            actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.TAB)
            actions.send_keys(target_hsk)
            actions.perform()
            time.sleep(0.5)

            # TAB 11번 -> 엔터 (조회)
            status.write("⏳ 조회 실행...")
            for _ in range(11): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            time.sleep(5) 

            # TAB 8번 -> DOWN -> 엔터 (상세 진입)
            status.write("⏳ 상세 페이지 진입 시도...")
            actions = ActionChains(driver) 
            for _ in range(8): actions.send_keys(Keys.TAB)
            actions.send_keys(Keys.DOWN)
            actions.send_keys(Keys.ENTER)
            actions.perform()
            
            status.write("✅ 상세 페이지 명령 전달 완료. 팝업 대기...")
            time.sleep(5)
            
        except Exception as e:
            status.error(f"매크로 실행 실패: {e}")
            return None

        # [4] 팝업 창 전환
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            status.write("✅ 상세 팝업창 진입 성공!")
        else:
            status.warning("⚠️ 팝업창이 뜨지 않았습니다. 결과를 확인하세요.")
            st.image(driver.get_screenshot_as_png())
            return None

        # [5] 데이터 추출 (2026년 1월, 2025년 12월)
        status.write("⏳ 연도별 데이터 탐색 중...")
        
        # 목표 설정
        targets = [
            {"year": "2026", "month_keyword": "1월", "full_date": "2026.01"},
            {"year": "2025", "month_keyword": "12월", "full_date": "2025.12"}
        ]

        for t in targets:
            y = t['year']
            m_key = t['month_keyword']
            
            # 1. 해당 연도(예: 2026년) 텍스트를 찾아서 클릭 시도
            try:
                # '2026년' 같은 텍스트가 포함된 요소를 찾아 클릭 (트리 확장)
                year_elem = driver.find_element(By.XPATH, f"//*[contains(text(), '{y}년')]")
                driver.execute_script("arguments[0].click();", year_elem)
                time.sleep(2) # 데이터 로딩 대기
            except:
                pass # 없으면 넘어감 (예: 2026년 데이터가 아직 없을 수 있음)

            # 2. 표 데이터 읽기 (lxml 필수!)
            try:
                dfs = pd.read_html(driver.page_source)
            except Exception as e:
                status.error(f"표 읽기 실패 (lxml 설치 확인 필요): {e}")
                return None

            val = "데이터 없음"
            
            # 3. 데이터프레임에서 값 찾기
            for df in dfs:
                # 행을 돌면서 날짜 확인
                for idx, row in df.iterrows():
                    row_txt = " ".join(row.astype(str).values)
                    
                    # "1월" 또는 "2026.01"이 포함되어 있는지 확인
                    if m_key in row_txt or t['full_date'] in row_txt:
                        # 수출금액 컬럼 찾기 (보통 '수출금액' 혹은 숫자가 있는 첫번째 컬럼)
                        if '수출금액' in df.columns:
                            val = row['수출금액']
                        elif '수출' in df.columns:
                             # 수출 컬럼이 멀티인덱스일 경우 처리
                             if isinstance(row['수출'], pd.Series):
                                 val = row['수출'].iloc[0] # 첫번째 값(보통 금액)
                             else:
                                 val = row['수출']
                        else:
                            # 컬럼명을 모를 땐, 날짜 옆에 있는 숫자를 가져옴 (간이 방식)
                            val = row_txt # 일단 전체 행을 보여줌
                        break
                if val != "데이터 없음":
                    break
            
            results.append({
                "연도": y,
                "월": m_key,
                "수출금액": val
            })

    except Exception as e:
        st.error(f"오류 발생: {e}")
        st.image(driver.get_screenshot_as_png())
        return None
    finally:
        driver.quit()
    
    return pd.DataFrame(results)

# 실행 및 결과 출력
if submit:
    df_result = run_crawler(hsk_code)
    
    if df_result is not None:
        st.success("🎉 데이터 수집 완료!")
        
        # 깔끔하게 표로 보여주기
        st.subheader(f"📊 {hsk_code} 수출 데이터")
        st.table(df_result)
        
        # (엑셀 다운로드 버튼은 삭제했습니다)
