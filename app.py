import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
from datetime import datetime
import io

# --------------------------------------------------------------------------
# 1. 스트림릿 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 무역통계 수집기", layout="centered")
st.title("🚢 K-STAT 수출입 상세 데이터 조회")
st.info("K-Stat > 품목수출입 > 상세정보 페이지를 탐색하여 [당월/전월] 데이터를 수집합니다.")

# 입력 폼
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드 (예: 847950)", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 크롤링 함수 (문법 에러 방지를 위해 구조 단순화)
# --------------------------------------------------------------------------
def run_crawler(target_hsk):
    status = st.empty()
    status.write("⏳ 브라우저 초기화 중...")

    # [설정] 브라우저 옵션
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 봇 탐지 방지용 User-Agent (한 줄로 작성)
    ua_str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={ua_str}")

    driver = webdriver.Chrome(options=options)
    # [수정] 괄호 닫기 확실하게 처리
    wait = WebDriverWait(driver, 20)

    results = []

    try:
        # -----------------------------------------------------------
        # [단계 1] 메인 접속 및 메뉴 이동
        # -----------------------------------------------------------
        status.write("⏳ K-STAT 접속 및 메뉴 이동 중...")
        driver.get("https://stat.kita.net/")
        
        # '국내통계' 클릭
        btn_1 = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '국내통계')]")))
        btn_1.click()
        time.sleep(1)

        # '품목 수출입' 클릭
        btn_2 = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(), '품목 수출입') or contains(text(), '품목수출입')]")))
        btn_2.click()
        time.sleep(3) 

        # -----------------------------------------------------------
        # [단계 2] '시작코드' 입력창 찾기 (Iframe 대응)
        # -----------------------------------------------------------
        status.write("⏳ '시작코드' 입력창 찾는 중...")
        
        input_box = None
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        
        # 메인 프레임(0) + 하위 프레임들 순회
        for i in range(len(iframes) + 1):
            try:
                if i > 0:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(iframes[i-1])
                
                # 시도 1: ID로 찾기
                try:
                    input_box = driver.find_element(By.ID, "s_st_hsk_no")
                except:
                    # 시도 2: XPath로 찾기 (시작코드 옆 input)
                    try:
                        xpath_str = "//td[contains(text(), '시작코드')]/following-sibling::td//input[@type='text']"
                        input_box = driver.find_element(By.XPATH, xpath_str)
                    except:
                        pass
                
                if input_box:
                    break # 찾았으면 루프 탈출
            except:
                continue

        if not input_box:
            status.error("❌ 입력창을 찾을 수 없습니다.")
            st.image(driver.get_screenshot_as_png())
            return None

        # -----------------------------------------------------------
        # [단계 3] 데이터 입력 및 조회
        # -----------------------------------------------------------
        status.write(f"⏳ HSK {target_hsk} 조회 중...")
        input_box.clear()
        input_box.send_keys(target_hsk)
        
        # 조회 버튼 클릭
        search_btn = driver.find_element(By.XPATH, "//*[contains(text(), '조회')]")
        search_btn.click()
        time.sleep(3)

        # -----------------------------------------------------------
        # [단계 4] 파란색 HSK 코드 링크 클릭 (상세 페이지 진입)
        # -----------------------------------------------------------
        status.write("⏳ 상세 정보(파란색 링크) 클릭 중...")
        
        # 847950 등 코드 숫자가 적힌 링크 찾기
        link_xpath = f"//a[contains(text(), '{target_hsk}')]"
        detail_link = wait.until(EC.element_to_be_clickable((By.XPATH, link_xpath)))
        detail_link.click()
        
        time.sleep(5) # 팝업/페이지 로딩 대기

        # 새 창이 떴다면 전환
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

        # -----------------------------------------------------------
        # [단계 5] 날짜별 데이터 추출 (당월/전월)
        # -----------------------------------------------------------
        status.write("⏳ 상세 데이터 분석 중...")

        # 현재 연도/월 계산
        now = datetime.now()
        # 예: 2026-01 (당월), 2025-12 (전월)
        
        # 당월 설정
        cur_year = str(now.year)
        cur_month = f"{now.month:02d}" # 01, 02...
        
        # 전월 설정
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

        # 데이터 추출 루프
        for t in targets:
            y = t['year']
            m = t['month']
            
            # 1. 연도 버튼 클릭 시도 (해당 연도가 화면에 있다면)
            try:
                # 2025, 2026 같은 연도 텍스트 클릭
                year_btn = driver.find_element(By.XPATH, f"//*[contains(text(), '{y}')]")
                year_btn.click()
                time.sleep(2)
            except:
                pass # 없으면 이미 해당 연도이거나 표에 있겠거니 함

            # 2. 표 데이터 읽기
            html = driver.page_source
            dfs = pd.read_html(html)
            
            val = "데이터 없음"
            
            # 모든 표를 순회하며 날짜와 금액 찾기
            found_in_table = False
            for df in dfs:
                if found_in_table: break
                
                # [수정] 지난번 에러난 부분: 괄호 완벽하게 닫음
                for idx, row in df.iterrows():
                    # 데이터프레임 행을 문자열로 합침
                    row_text = " ".join(row.astype(str).values)
                    
                    # '01월' 또는 '2026.01' 같은 패턴 찾기
                    pattern1 = f"{int(m)}월"
                    pattern2 = f"{y}.{m}"
                    
                    if pattern1 in row_text or pattern2 in row_text:
                        # 수출 금액 찾기 시도
                        if '수출금액' in df.columns:
                            val = row['수출금액']
                        elif '수출' in df.columns:
                            val = row['수출']
                        else:
                            # 컬럼 못 찾으면 행 전체 저장
                            val = row_text
                        found_in_table = True
                        break
            
            results.append({
                "구분": t['label'],
                "기간": f"{y}-{m}",
                "수출금액": val
            })

    except Exception as e:
        st.error("오류가 발생했습니다.")
        st.write(e)
        # 에러 발생 시 화면 캡처
        try:
            st.image(driver.get_screenshot_as_png())
        except:
            pass
        return None

    finally:
        driver.quit()
    
    return pd.DataFrame(results)

# --------------------------------------------------------------------------
# 3. 메인 실행 로직
# --------------------------------------------------------------------------
if submit:
    df_res = run_crawler(hsk_code)
    
    if df_res is not None:
        st.success("✅ 수집 완료!")
        st.table(df_res)
        
        # 엑셀 다운로드
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_res.to_excel(writer, index=False)
            
        st.download_button(
            label="📥 결과 엑셀 다운로드",
            data=buffer,
            file_name=f"KSTAT_{hsk_code}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
