import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
import io

# --- 1. 페이지 설정 ---
st.set_page_config(page_title="K-STAT 무역통계 조회", layout="centered")

st.title("🚢 K-STAT 수출입 데이터 조회")
st.info("K-STAT 메인에서 '국내통계 > 품목수출입' 메뉴로 이동하여 데이터를 수집합니다.")

# 입력 폼
with st.form("search_form"):
    hsk_code = st.text_input("HSK 코드 (6~10단위)", value="847950")
    submit = st.form_submit_button("데이터 조회 시작 🚀")

# --- 2. 크롤링 로직 ---
if submit:
    status_area = st.empty()
    status_area.write("⏳ 브라우저 실행 중...")

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 15)

    try:
        # (1) K-STAT 메인 접속
        status_area.write("⏳ K-STAT 메인 페이지(stat.kita.net) 접속 중...")
        driver.get("https://stat.kita.net/")
        time.sleep(2)

        # (2) '국내통계' 메뉴 클릭
        status_area.write("⏳ '국내통계' 메뉴 찾는 중...")
        # 텍스트로 찾아서 클릭 (가장 확실한 방법)
        dom_stat_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '국내통계')]")))
        dom_stat_btn.click()
        time.sleep(2)

        # (3) '품목 수출입' 메뉴 클릭
        status_area.write("⏳ '품목 수출입' 메뉴로 이동 중...")
        item_trade_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
        item_trade_btn.click()
        time.sleep(3) # 페이지 이동 대기

        # (4) 입력창 찾기 (Iframe 대응 포함)
        status_area.write("⏳ HSK 입력창 찾는 중...")
        
        input_box = None
        
        # 메인 프레임에서 먼저 시도
        try:
            input_box = driver.find_element(By.ID, "s_st_hsk_no")
        except:
            pass
            
        # 없으면 Iframe 내부 탐색 (여기가 핵심)
        if not input_box:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for iframe in iframes:
                try:
                    driver.switch_to.frame(iframe)
                    input_box = driver.find_element(By.ID, "s_st_hsk_no") # K-STAT 표준 ID
                    if input_box:
                        break
                except:
                    driver.switch_to.default_content() # 다시 밖으로 나와서 다음 iframe 시도
                    continue
        
        if not input_box:
            # ID가 다를 경우를 대비해 텍스트박스(input type=text) 중 HSK와 관련된 것 찾기 시도
            try:
                # 'HSK'라는 글자 근처에 있는 input 박스 찾기 (최후의 수단)
                input_box = driver.find_element(By.XPATH, "//input[@type='text' and contains(@id, 'hsk')]")
            except:
                status_area.error("❌ HSK 입력창을 찾지 못했습니다. 현재 화면을 확인하세요.")
                st.image(driver.get_screenshot_as_png())
                raise Exception("Input box not found")

        # (5) 데이터 입력 및 조회
        input_box.clear()
        input_box.send_keys(hsk_code)
        
        # 조회 버튼 클릭
        status_area.write("⏳ 조회 버튼 누르는 중...")
        try:
            # 텍스트가 '조회'인 버튼 혹은 이미지를 찾음
            search_btn = driver.find_element(By.XPATH, "//*[contains(text(), '조회')]")
            search_btn.click()
        except:
            # 버튼을 못 찾으면 엔터키 입력 시도
            from selenium.webdriver.common.keys import Keys
            input_box.send_keys(Keys.RETURN)
            
        time.sleep(5) # 데이터 로딩 대기

        # (6) 데이터 추출
        status_area.write("⏳ 데이터 추출 중...")
        html = driver.page_source
        dfs = pd.read_html(html)
        
        if not dfs:
            raise Exception("테이블 데이터 없음")

        # 데이터가 가장 많은 테이블 선택
        df = max(dfs, key=lambda x: len(x))
        
        status_area.success("수집 성공!")
        st.write(f"### 📊 결과: {hsk_code}")
        st.dataframe(df.head(10))

        # 엑셀 다운로드
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
            
        st.download_button(
            label="📥 엑셀 다운로드",
            data=buffer,
            file_name=f"KSTAT_{hsk_code}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"오류: {e}")
        try:
            st.image(driver.get_screenshot_as_png(), caption="에러 발생 화면")
        except:
            pass
            
    finally:
        driver.quit()
