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

# --- 1. 페이지 기본 설정 ---
st.set_page_config(page_title="K-STAT 데이터 수집기", layout="centered")
st.title("🚢 K-STAT 수출입 상세 데이터 조회")
st.info("K-Stat > 품목수출입 > 상세정보 페이지를 자동으로 탐색하여 데이터를 가져옵니다.")

# --- 2. 입력 UI ---
with st.form("input_form"):
    hsk_code = st.text_input("HSK 코드 (예: 847950)", value="847950")
    submit = st.form_submit_button("데이터 수집 시작 🚀")

# --- 3. 크롤링 함수 ---
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
    # 봇 탐지 회피
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(
