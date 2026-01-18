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

# --------------------------------------------------------------------------
# 1. 페이지 설정
# --------------------------------------------------------------------------
st.set_page_config(page_title="K-STAT 무역통계 수집기", layout="centered")
st.title("🚢 K-STAT 데이터 수집기 (안정화 버전)")
st.info("iframe 자동 탐색 + 클릭 가능 상태 대기 방식")

with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드 (예: 847950)", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --------------------------------------------------------------------------
# 2. 크롤링 함수
# --------------------------------------------------------------------------
def run_crawler(target_hsk):
    status = st.empty()
    status.write("⏳ 브라우저 초기화 중...")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    results = []

    try:
        # ------------------------------------------------------------------
        # [1] 사이트 접속 및 메뉴 이동
        # ------------------------------------------------------------------
        status.write("⏳ K-STAT 접속 중...")
        driver.get("https://stat.kita.net/")
        time.sleep(3)

        # 국내통계
        try:
            btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(),'국내통계')]")
            ))
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
        except:
            pass

        # 품목 수출입
        try:
            btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[contains(text(),'품목 수출입') or contains(text(),'품목수출입')]")
            ))
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(3)
        except:
            status.warning("⚠️ 메뉴 클릭 일부 실패 – 계속 진행")

        # ------------------------------------------------------------------
        # [2] iframe 자동 탐색
        # ------------------------------------------------------------------
        status.write("⏳ HSK 입력 iframe 탐색 중...")
        driver.switch_to.default_content()

        found = False
        for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
            driver.switch_to.default_content()
            driver.switch_to.frame(iframe)

            if driver.find_elements(By.XPATH, "//input[contains(@id,'hsk')]"):
                found = True
                break

        if not found:
            driver.switch_to.default_content()
            status.error("❌ HSK 입력 iframe을 찾지 못했습니다.")
            st.image(driver.get_screenshot_as_png())
            return None

        status.write("✅ 입력 iframe 진입 성공")

        # ------------------------------------------------------------------
        # [3] HSK 코드 입력 및 조회
        # ------------------------------------------------------------------
        status.write(f"⏳ HSK 코드 입력 중: {target_hsk}")

        input_box = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//input[contains(@id,'hsk')]"))
        )

        driver.execute_script("arguments[0].scrollIntoView(true);", input_box)
        time.sleep(0.5)

        input_box.click()
        input_box.clear()
        input_box.send_keys(target_hsk)

        search_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'조회')]"))
        )
        driver.execute_script("arguments[0].click();", search_btn)

        time.sleep(5)

        # ------------------------------------------------------------------
        # [4] 검색 결과 클릭
        # ------------------------------------------------------------------
        status.write("⏳ 검색 결과 클릭 중...")

        link = wait.until(
            EC.element_to_be_clickable((By.XPATH, f"//a[contains(text(),'{target_hsk}')]"))
        )
        driver.execute_script("arguments[0].click();", link)

        time.sleep(4)

        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])

        # ------------------------------------------------------------------
        # [5] 데이터 추출
        # ------------------------------------------------------------------
        status.write("⏳ 데이터 추출 중...")

        now = datetime.now()
        targets = [
            ("당월", now.year, f"{now.month:02d}"),
            ("전월",
             now.year if now.month > 1 else now.year - 1,
             f"{now.month-1 if now.month > 1 else 12:02d}")
        ]

        for label, y, m in targets:
            html = driver.page_source
            dfs = pd.read_html(html)
            value = "데이터 없음"

            for df in dfs:
                for _, row in df.iterrows():
                    txt = " ".join(row.astype(str).values)
                    if f"{int(m)}월" in txt or f"{y}.{m}" in txt:
                        if "수출금액" in df.columns:
                            value = row["수출금액"]
                        elif "수출" in df.columns:
                            value = row["수출"]
                        else:
                            value = txt
                        break

            results.append({
                "구분": label,
                "기간": f"{y}-{m}",
                "수출금액": value
            })

        return pd.DataFrame(results)

    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")
        st.image(driver.get_screenshot_as_png())
        return None

    finally:
        driver.quit()

# --------------------------------------------------------------------------
# 3. 실행
# --------------------------------------------------------------------------
if submit:
    df = run_crawler(hsk_code)

    if df is not None:
        st.success("✅ 수집 완료")
        st.table(df)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)

        st.download_button(
            "📥 엑셀 다운로드",
            data=buffer,
            file_name="kstat_result.xlsx"
        )
